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
EVAL_CASES_PATH = REPO_ROOT / "examples" / "rag_eval_cases.json"


def run_demo(storage_root: Path | None = None) -> dict[str, Any]:
    eval_payload = _load_eval_payload()
    with _storage_env(storage_root) as resolved_storage_root:
        get_settings.cache_clear()
        with TestClient(create_app()) as client:
            _seed_knowledge_base(client, eval_payload["knowledge_base"])
            knowledge_first = _chat(
                client,
                "What is refund policy?",
                knowledge_base_id="kb_support",
            )
            knowledge_cached = _chat(
                client,
                "What is refund policy?",
                knowledge_base_id="kb_support",
            )
            business = _chat(
                client,
                "订单 ORD-1001 发货了吗？",
                integration_context={"industry": "ecommerce"},
            )
            risk = _chat(client, "我要投诉监管处理")
            handoff_queue = _get_handoff_queue(client)
            claimed_session = _claim_next_handoff(client)
            cost_summary = _get_cost_summary(client)
            rag_eval = _run_rag_eval(client, eval_payload["cases"])
        get_settings.cache_clear()

    return {
        "storage_root": str(resolved_storage_root),
        "route": {
            "knowledge_first": knowledge_first["route"],
            "knowledge_cached": knowledge_cached["route"],
            "knowledge_cache_hit": knowledge_cached["cache_hit"],
            "business": business["route"],
            "risk": risk["route"],
        },
        "citations": knowledge_first["citations"],
        "tool_result": business["tool_result"],
        "handoff_queue": handoff_queue,
        "claimed_session": claimed_session,
        "cost_summary": cost_summary,
        "rag_eval_summary": rag_eval["summary"],
        "rag_eval_failures": rag_eval["failures"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local interview demo flow.")
    parser.add_argument("--storage-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_demo(storage_root=args.storage_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key in (
            "route",
            "citations",
            "tool_result",
            "handoff_queue",
            "claimed_session",
            "cost_summary",
            "rag_eval_summary",
        ):
            print(key)
            print(json.dumps(result[key], ensure_ascii=False, indent=2))
    return 0 if result["rag_eval_summary"]["failed"] == 0 else 1


def _load_eval_payload() -> dict[str, Any]:
    return json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))


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


def _chat(
    client: TestClient,
    message: str,
    *,
    knowledge_base_id: str | None = None,
    integration_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tenant_id": "demo-tenant",
        "channel": "web",
        "message": message,
    }
    if knowledge_base_id is not None:
        payload["knowledge_base_id"] = knowledge_base_id
    if integration_context is not None:
        payload["integration_context"] = integration_context
    response = client.post("/api/v1/chat/messages", headers=CUSTOMER_HEADERS, json=payload)
    response.raise_for_status()
    return dict(response.json()["data"])


def _get_handoff_queue(client: TestClient) -> list[dict[str, Any]]:
    response = client.get(
        "/api/v1/admin/handoff/queue",
        headers=ADMIN_HEADERS,
        params={"tenant_id": "demo-tenant"},
    )
    response.raise_for_status()
    return list(response.json()["data"])


def _claim_next_handoff(client: TestClient) -> dict[str, Any] | None:
    response = client.post(
        "/api/v1/admin/handoff/claim-next",
        headers=ADMIN_HEADERS,
        params={"tenant_id": "demo-tenant", "operator_id": "interview_op"},
    )
    response.raise_for_status()
    data = response.json()["data"]
    return None if data is None else dict(data)


def _get_cost_summary(client: TestClient) -> dict[str, Any]:
    response = client.get(
        "/api/v1/admin/costs/summary",
        headers=ADMIN_HEADERS,
        params={"tenant_id": "demo-tenant"},
    )
    response.raise_for_status()
    return dict(response.json()["data"])


def _run_rag_eval(client: TestClient, cases: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        response = client.put(
            "/api/v1/admin/policies",
            headers=ADMIN_HEADERS,
            json={"knowledge_min_score": float(case.get("min_score", 0.18))},
        )
        response.raise_for_status()
        data = _chat(
            client,
            str(case["question"]),
            knowledge_base_id=str(case.get("knowledge_base_id", "kb_support")),
        )
        data["case_id"] = case["case_id"]
        results.append(data)
    return evaluate_rag_results(cases, results)


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

    with TemporaryDirectory(prefix="customer-ai-interview-demo-") as temp_dir:
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
