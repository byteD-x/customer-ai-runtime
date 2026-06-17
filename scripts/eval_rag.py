from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from customer_ai_runtime.app import create_app  # noqa: E402
from customer_ai_runtime.core.config import get_settings  # noqa: E402
from customer_ai_runtime.evaluation import evaluate_rag_results  # noqa: E402

CUSTOMER_HEADERS = {"X-API-Key": "demo-public-key"}
ADMIN_HEADERS = {"X-API-Key": "demo-admin-key"}
DEFAULT_CASES_PATH = REPO_ROOT / "examples" / "rag_eval_cases.json"


def load_eval_payload(path: Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_eval(
    *,
    cases_path: Path = DEFAULT_CASES_PATH,
    storage_root: Path | None = None,
) -> dict[str, Any]:
    payload = load_eval_payload(cases_path)
    with _storage_env(storage_root) as resolved_storage_root:
        get_settings.cache_clear()
        with TestClient(create_app()) as client:
            _seed_knowledge_bases(client, payload)
            results = _run_cases(client, payload["cases"])
        get_settings.cache_clear()
    report = evaluate_rag_results(payload["cases"], results)
    report["storage_root"] = str(resolved_storage_root)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local RAG evaluation cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--storage-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", type=Path, default=None, help="Write the report to a UTF-8 file.")
    args = parser.parse_args()

    report = run_eval(cases_path=args.cases, storage_root=args.storage_root)
    output_text = _render_output(report, json_output=args.json)
    if args.output is not None:
        write_output_file(args.output, output_text)
        print(f"wrote_report: {args.output}")
    elif args.json:
        print(output_text, end="")
    else:
        print(output_text, end="")
    return 0 if report["summary"]["failed"] == 0 else 1


def write_output_file(output_path: Path, output_text: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")


def _render_output(report: dict[str, Any], *, json_output: bool) -> str:
    if json_output:
        return json.dumps({"rag_eval_summary": report}, ensure_ascii=False, indent=2) + "\n"
    lines = [
        "rag_eval_summary",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
    ]
    if report["failures"]:
        lines.extend(
            [
                "rag_eval_failures",
                json.dumps(report["failures"], ensure_ascii=False, indent=2),
            ]
        )
    return "\n".join(lines) + "\n"


def _seed_knowledge_bases(client: TestClient, payload: dict[str, Any]) -> None:
    knowledge_bases = payload.get("knowledge_bases")
    if isinstance(knowledge_bases, list):
        for knowledge_base in knowledge_bases:
            if isinstance(knowledge_base, dict):
                _seed_knowledge_base(client, knowledge_base)
        return
    _seed_knowledge_base(client, payload["knowledge_base"])


def _seed_knowledge_base(client: TestClient, knowledge_base: dict[str, Any]) -> None:
    tenant_id = str(knowledge_base["tenant_id"])
    knowledge_base_id = str(knowledge_base["knowledge_base_id"])
    response = client.post(
        "/api/v1/knowledge-bases",
        headers=CUSTOMER_HEADERS,
        json={
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "name": knowledge_base.get("name", knowledge_base_id),
            "description": knowledge_base.get("description", ""),
        },
    )
    response.raise_for_status()
    for document in knowledge_base.get("documents", []):
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            headers=CUSTOMER_HEADERS,
            json={
                "tenant_id": tenant_id,
                "title": document["title"],
                "content": document["content"],
                "metadata": document.get("metadata", {}),
            },
        )
        response.raise_for_status()


def _run_cases(client: TestClient, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        min_score = float(case.get("min_score", 0.18))
        policy_response = client.put(
            "/api/v1/admin/policies",
            headers=ADMIN_HEADERS,
            json={"knowledge_min_score": min_score},
        )
        policy_response.raise_for_status()
        response = client.post(
            "/api/v1/chat/messages",
            headers=CUSTOMER_HEADERS,
            json={
                "tenant_id": "demo-tenant",
                "channel": "web",
                "message": case["question"],
                "knowledge_base_id": case.get("knowledge_base_id", "kb_support"),
            },
        )
        payload: dict[str, Any] = {
            "case_id": case["case_id"],
            "status_code": response.status_code,
        }
        if response.status_code == 200:
            payload.update(response.json()["data"])
        else:
            payload["error"] = response.json().get("error")
        results.append(payload)
    return results


@contextmanager
def _storage_env(storage_root: Path | None) -> Iterator[Path]:
    previous_storage = os.environ.get("CUSTOMER_AI_STORAGE_ROOT")
    previous_log_level = os.environ.get("CUSTOMER_AI_LOG_LEVEL")
    os.environ.setdefault("CUSTOMER_AI_LOG_LEVEL", "WARNING")
    if storage_root is not None:
        resolved = storage_root
        resolved.mkdir(parents=True, exist_ok=True)
        os.environ["CUSTOMER_AI_STORAGE_ROOT"] = str(resolved)
        try:
            yield resolved
        finally:
            _restore_env(previous_storage, previous_log_level)
        return

    with TemporaryDirectory(prefix="customer-ai-rag-eval-") as temp_dir:
        resolved = Path(temp_dir) / "storage"
        os.environ["CUSTOMER_AI_STORAGE_ROOT"] = str(resolved)
        try:
            yield resolved
        finally:
            _restore_env(previous_storage, previous_log_level)


def _restore_env(previous_storage: str | None, previous_log_level: str | None) -> None:
    if previous_storage is None:
        os.environ.pop("CUSTOMER_AI_STORAGE_ROOT", None)
    else:
        os.environ["CUSTOMER_AI_STORAGE_ROOT"] = previous_storage
    if previous_log_level is None:
        os.environ.pop("CUSTOMER_AI_LOG_LEVEL", None)
    else:
        os.environ["CUSTOMER_AI_LOG_LEVEL"] = previous_log_level


if __name__ == "__main__":
    raise SystemExit(main())
