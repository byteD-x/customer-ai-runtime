from __future__ import annotations

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


def test_interview_demo_returns_required_sections(tmp_path: Path) -> None:
    result = run_demo(storage_root=tmp_path / "demo-storage")

    assert result["route"]["knowledge_first"] == "knowledge"
    assert result["route"]["knowledge_cached"] == "knowledge"
    assert result["route"]["knowledge_cache_hit"] is True
    assert result["route"]["business"] == "business"
    assert result["route"]["risk"] == "risk"
    assert result["citations"]
    assert result["tool_result"]["status"] == "success"
    assert result["handoff_queue"]
    assert result["claimed_session"]["state"] == "human_in_service"
    assert result["cost_summary"]["sample_size"] >= 4
    assert result["cost_summary"]["cache_hits"] >= 1
    assert result["rag_eval_summary"]["failed"] == 0
