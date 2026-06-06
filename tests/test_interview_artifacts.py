from __future__ import annotations

import json
from pathlib import Path

from customer_ai_runtime.evaluation import evaluate_rag_results
from examples.interview_demo import run_demo


def test_rag_eval_reports_citation_keyword_failures() -> None:
    report = evaluate_rag_results(
        [
            {
                "case_id": "keyword_failure",
                "question": "What is refund policy?",
                "expected_route": "knowledge",
                "expected_citation_keywords": ["seven day no reason refund"],
                "min_score": 0.18,
                "expect_effective_hit": True,
            }
        ],
        [
            {
                "case_id": "keyword_failure",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "refund policy",
                        "excerpt": "Refunds are handled by the support team.",
                        "score": 0.42,
                    }
                ],
            }
        ],
    )

    assert report["summary"]["failed"] == 1
    assert report["failures"][0]["missing_keywords"] == ["seven day no reason refund"]
    assert report["failures"][0]["route_ok"] is True
    assert report["failures"][0]["effective_hit_ok"] is True


def test_rag_eval_cases_cover_hit_and_unrelated_miss() -> None:
    payload = json.loads(Path("examples/rag_eval_cases.json").read_text(encoding="utf-8"))
    cases = payload["cases"]
    case_ids = {case["case_id"] for case in cases}
    knowledge_base_ids = {
        knowledge_base["knowledge_base_id"] for knowledge_base in payload["knowledge_bases"]
    }

    assert "refund_payment_proof_hit" in case_ids
    assert "business_unrelated_miss" in case_ids
    assert "saas_scim_sync_hit" in case_ids
    assert "saas_audit_retention_hit" in case_ids
    assert "feedback_replay_refund_hit" in case_ids
    assert knowledge_base_ids == {"kb_support", "kb_saas"}

    report = evaluate_rag_results(
        [
            case
            for case in cases
            if case["case_id"]
            in {
                "refund_payment_proof_hit",
                "business_unrelated_miss",
                "saas_scim_sync_hit",
                "feedback_replay_refund_hit",
            }
        ],
        [
            {
                "case_id": "refund_payment_proof_hit",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "refund policy",
                        "excerpt": "Keep order id and payment proof for refund requests.",
                        "score": 0.42,
                    }
                ],
            },
            {
                "case_id": "business_unrelated_miss",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "refund policy",
                        "excerpt": "Refund policy supports seven day no reason refund.",
                        "score": 0.12,
                    }
                ],
            },
            {
                "case_id": "saas_scim_sync_hit",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "saas administration policy",
                        "excerpt": "SSO SCIM provisioning changes sync within 15 minutes.",
                        "score": 0.38,
                    }
                ],
            },
            {
                "case_id": "feedback_replay_refund_hit",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "feedback replay",
                        "excerpt": (
                            "Replay negative feedback with the session id and refund request."
                        ),
                        "score": 0.4,
                    }
                ],
            },
        ],
    )

    unrelated_case = next(
        item for item in report["cases"] if item["case_id"] == "business_unrelated_miss"
    )
    assert report["summary"]["failed"] == 0
    assert unrelated_case["effective_hit"] is False
    assert unrelated_case["effective_hit_ok"] is True


def test_interview_demo_returns_required_sections(tmp_path: Path) -> None:
    result = run_demo(storage_root=tmp_path / "demo-storage")

    assert result["route"]["knowledge_first"] == "knowledge"
    assert result["route"]["knowledge_cached"] == "knowledge"
    assert result["route"]["knowledge_cache_hit"] is True
    assert result["route"]["business"] == "business"
    assert result["route"]["risk"] == "risk"
    assert result["citations"]
    assert result["tool_result"]["status"] == "success"
    assert result["handoff_package"]["sentiment"] == "negative"
    assert result["handoff_package"]["related_business_objects"]["order_id"] == "ORD-1001"
    assert "ORD-1001" in result["handoff_package"]["issue_summary"]
    assert result["handoff_queue"]
    assert result["claimed_session"]["state"] == "human_in_service"
    assert result["cost_summary"]["sample_size"] >= 4
    assert result["cost_summary"]["cache_hits"] >= 1
    assert result["rag_eval_summary"]["failed"] == 0
