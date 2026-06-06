from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from customer_ai_runtime.evaluation import evaluate_rag_results  # noqa: E402


def load_online_eval_payload(path: Path) -> dict[str, list[dict[str, Any]]]:
    raw_payload = _read_json_or_jsonl(path)
    if isinstance(raw_payload, dict):
        cases = raw_payload.get("cases")
        results = raw_payload.get("results")
        if isinstance(cases, list) and isinstance(results, list):
            return {
                "cases": [dict(item) for item in cases if isinstance(item, dict)],
                "results": [dict(item) for item in results if isinstance(item, dict)],
            }
        records = raw_payload.get("records")
        if isinstance(records, list):
            return _payload_from_records(records)
    if isinstance(raw_payload, list):
        return _payload_from_records(raw_payload)
    raise ValueError("online RAG eval input must be JSON/JSONL records or cases/results")


def run_online_eval(path: Path) -> dict[str, Any]:
    payload = load_online_eval_payload(path)
    report = evaluate_rag_results(payload["cases"], payload["results"])
    report["summary"]["accuracy_source"] = "online_labeled_sample"
    report["summary"]["online_accuracy"] = report["summary"]["offline_accuracy"]
    report["summary"]["input_path"] = str(path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate anonymized online RAG labeled samples.")
    parser.add_argument("path", type=Path, help="JSON or JSONL online sample export.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = run_online_eval(args.path)
    if args.json:
        print(json.dumps({"online_rag_eval_summary": report}, ensure_ascii=False, indent=2))
    else:
        print("online_rag_eval_summary")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        if report["failures"]:
            print("online_rag_eval_failures")
            print(json.dumps(report["failures"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["failed"] == 0 else 1


def _read_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def _payload_from_records(records: list[Any]) -> dict[str, list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        case = item.get("case")
        result = item.get("result")
        if isinstance(case, dict) and isinstance(result, dict):
            normalized_case = dict(case)
            normalized_result = dict(result)
        else:
            normalized_case = _case_from_flat_record(item)
            normalized_result = _result_from_flat_record(item)
        case_id = str(
            normalized_case.get("case_id")
            or normalized_result.get("case_id")
            or item.get("sample_id")
            or item.get("session_id")
            or f"online_{index + 1}"
        )
        normalized_case["case_id"] = case_id
        normalized_result["case_id"] = case_id
        normalized_case.setdefault("dataset_id", item.get("dataset_id") or "online")
        normalized_case.setdefault("cohort", item.get("cohort") or "online")
        normalized_case.setdefault("review_status", item.get("review_status") or "unreviewed")
        cases.append(normalized_case)
        results.append(normalized_result)
    return {"cases": cases, "results": results}


def _case_from_flat_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": record.get("case_id"),
        "dataset_id": record.get("dataset_id"),
        "cohort": record.get("cohort"),
        "review_status": record.get("review_status"),
        "question": record.get("question") or record.get("query"),
        "expected_route": record.get("expected_route") or record.get("label_route"),
        "expected_citation_keywords": record.get("expected_citation_keywords")
        or record.get("label_citation_keywords")
        or [],
        "expect_effective_hit": record.get("expect_effective_hit", True),
        "min_score": record.get("min_score", 0.0),
        "label": record.get("label"),
    }


def _result_from_flat_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": record.get("case_id"),
        "route": record.get("route") or record.get("actual_route"),
        "citations": record.get("citations") or record.get("retrieved_citations") or [],
        "refusal": record.get("refusal"),
        "refusal_reason": record.get("refusal_reason"),
        "hallucination_check": record.get("hallucination_check"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
