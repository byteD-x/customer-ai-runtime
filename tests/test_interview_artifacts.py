from __future__ import annotations

import json
from pathlib import Path

from customer_ai_runtime.evaluation import evaluate_rag_results
from examples.interview_demo import render_markdown_report, run_demo
from scripts.check_external_readiness import run_checks


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
    assert report["summary"]["labeled_case_count"] == 1
    assert report["summary"]["reviewed_case_count"] == 0
    assert report["summary"]["offline_accuracy"] == 0.0
    assert report["summary"]["citation_accuracy"] == 0.0
    assert report["summary"]["context_precision"] == 0.0
    assert report["summary"]["context_recall"] == 0.0
    assert report["summary"]["badcase_breakdown"] == {
        "citation_keyword_missing": {
            "count": 1,
            "suggested_action": (
                "补充或改写知识片段，或调整切片与 rerank，让期望证据关键词能进入引用。"
            ),
        },
        "context_keyword_missing": {
            "count": 1,
            "suggested_action": (
                "检查返回引用是否覆盖标注上下文，必要时调整召回、重排或知识库内容。"
            ),
        },
    }
    assert report["failures"][0]["missing_keywords"] == ["seven day no reason refund"]
    assert report["failures"][0]["missing_context_keywords"] == ["seven day no reason refund"]
    assert report["failures"][0]["badcase_categories"] == [
        "citation_keyword_missing",
        "context_keyword_missing",
    ]
    assert report["failures"][0]["suggested_actions"] == [
        "补充或改写知识片段，或调整切片与 rerank，让期望证据关键词能进入引用。",
        "检查返回引用是否覆盖标注上下文，必要时调整召回、重排或知识库内容。",
    ]
    assert report["failures"][0]["route_ok"] is True
    assert report["failures"][0]["effective_hit_ok"] is True
    assert report["failures"][0]["citation_accuracy"] == 0.0
    assert report["failures"][0]["context_precision"] == 0.0
    assert report["failures"][0]["context_recall"] == 0.0


def test_rag_eval_classifies_route_hit_and_refusal_badcases() -> None:
    report = evaluate_rag_results(
        [
            {
                "case_id": "mixed_failure",
                "question": "How do I refund?",
                "expected_route": "knowledge",
                "expected_citation_keywords": ["refund policy"],
                "expected_context_keywords": ["refund policy"],
                "min_score": 0.8,
                "expect_effective_hit": True,
                "expect_refusal": True,
            }
        ],
        [
            {
                "case_id": "mixed_failure",
                "status_code": 200,
                "route": "business",
                "citations": [
                    {
                        "title": "shipping policy",
                        "excerpt": "Shipment tracking is available after dispatch.",
                        "score": 0.2,
                    }
                ],
                "refusal": False,
            }
        ],
    )

    assert report["summary"]["failed"] == 1
    assert report["summary"]["badcase_breakdown"] == {
        "citation_keyword_missing": {
            "count": 1,
            "suggested_action": (
                "补充或改写知识片段，或调整切片与 rerank，让期望证据关键词能进入引用。"
            ),
        },
        "context_keyword_missing": {
            "count": 1,
            "suggested_action": (
                "检查返回引用是否覆盖标注上下文，必要时调整召回、重排或知识库内容。"
            ),
        },
        "effective_hit_mismatch": {
            "count": 1,
            "suggested_action": (
                "检查 min_score、top_k、切片质量和召回候选，避免把低分兜底片段当成有效命中。"
            ),
        },
        "refusal_mismatch": {
            "count": 1,
            "suggested_action": (
                "检查拒答阈值、有效引用判断和 hallucination check，"
                "确保无证据时拒答、有证据时不误拒。"
            ),
        },
        "route_mismatch": {
            "count": 1,
            "suggested_action": (
                "优先检查路由策略、意图关键词、页面上下文和业务对象信号是否足够明确。"
            ),
        },
    }
    assert report["failures"][0]["badcase_categories"] == [
        "route_mismatch",
        "effective_hit_mismatch",
        "citation_keyword_missing",
        "context_keyword_missing",
        "refusal_mismatch",
    ]


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
    assert "finance_expense_receipt_hit" in case_ids
    assert "finance_vendor_payment_hit" in case_ids
    assert "feedback_replay_refund_hit" in case_ids
    assert knowledge_base_ids == {"kb_support", "kb_saas", "kb_finance_ops"}
    assert all(case["dataset_id"] == "local_interview_v1" for case in cases)
    assert all(case["review_status"] == "reviewed" for case in cases)

    report = evaluate_rag_results(
        [
            case
            for case in cases
            if case["case_id"]
            in {
                "refund_payment_proof_hit",
                "business_unrelated_miss",
                "saas_scim_sync_hit",
                "finance_expense_receipt_hit",
                "finance_vendor_payment_hit",
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
                "citations": [],
                "refusal": True,
                "refusal_reason": "no_effective_citation",
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
                "case_id": "finance_expense_receipt_hit",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "finance operations policy",
                        "excerpt": (
                            "Finance expense reimbursement requires a valid invoice and "
                            "cost center before approval."
                        ),
                        "score": 0.41,
                    }
                ],
            },
            {
                "case_id": "finance_vendor_payment_hit",
                "route": "knowledge",
                "citations": [
                    {
                        "title": "finance operations policy",
                        "excerpt": (
                            "Vendor payment approval requires purchase order matching and "
                            "finance owner review before release."
                        ),
                        "score": 0.41,
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
    assert report["summary"]["labeled_case_count"] == 6
    assert report["summary"]["reviewed_case_count"] == 6
    assert report["summary"]["offline_accuracy"] == 1.0
    assert report["summary"]["citation_accuracy"] == 1.0
    assert report["summary"]["context_precision"] == 1.0
    assert report["summary"]["context_recall"] == 1.0
    assert report["summary"]["refusal_accuracy"] == 1.0
    assert report["summary"]["refusal_case_count"] == 1
    assert report["summary"]["cohort_breakdown"]["support_baseline"]["case_count"] == 1
    assert report["summary"]["cohort_breakdown"]["negative_control"]["case_count"] == 1
    assert report["summary"]["cohort_breakdown"]["saas_baseline"]["case_count"] == 1
    assert report["summary"]["cohort_breakdown"]["finance_ops"]["case_count"] == 2
    assert report["summary"]["cohort_breakdown"]["feedback_replay"]["case_count"] == 1
    assert unrelated_case["effective_hit"] is False
    assert unrelated_case["effective_hit_ok"] is True
    assert unrelated_case["expected_refusal"] is True
    assert unrelated_case["actual_refusal"] is True
    assert unrelated_case["refusal_ok"] is True
    assert unrelated_case["expected_context_keywords"] == []
    assert unrelated_case["context_precision"] is None
    assert unrelated_case["context_recall"] is None
    assert unrelated_case["dataset_id"] == "local_interview_v1"
    assert unrelated_case["cohort"] == "negative_control"
    assert unrelated_case["review_status"] == "reviewed"

    feedback_case = next(case for case in cases if case["case_id"] == "feedback_replay_refund_hit")
    noisy_feedback_report = evaluate_rag_results(
        [feedback_case],
        [
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
                    },
                    {
                        "title": "refund policy",
                        "excerpt": "Keep order id and payment proof for account verification.",
                        "score": 0.39,
                    },
                ],
            }
        ],
    )
    assert noisy_feedback_report["summary"]["context_precision"] == 0.5
    assert noisy_feedback_report["summary"]["context_recall"] == 1.0


def test_interview_demo_returns_required_sections(tmp_path: Path) -> None:
    result = run_demo(storage_root=tmp_path / "demo-storage")

    assert result["route"]["knowledge_first"] == "knowledge"
    assert result["route"]["knowledge_cached"] == "knowledge"
    assert result["route"]["knowledge_cache_hit"] is True
    assert result["route"]["finance_knowledge"] == "knowledge"
    assert result["route"]["saas_knowledge"] == "knowledge"
    assert result["route"]["business"] == "business"
    assert result["route"]["risk"] == "risk"
    assert result["citations"]
    assert result["finance_knowledge"]["citations"]
    finance_citation = result["finance_knowledge"]["citations"][0]
    assert finance_citation["title"] == "finance operations policy"
    assert "valid invoice" in finance_citation["excerpt"]
    assert "cost center" in finance_citation["excerpt"]
    assert result["saas_knowledge"]["citations"]
    saas_citation = result["saas_knowledge"]["citations"][0]
    assert saas_citation["title"] == "saas administration policy"
    assert "scim provisioning" in saas_citation["excerpt"].lower()
    assert "15 minutes" in saas_citation["excerpt"]
    assert result["tool_result"]["status"] == "success"
    assert result["handoff_package"]["sentiment"] == "negative"
    assert result["handoff_package"]["related_business_objects"]["order_id"] == "ORD-1001"
    assert "ORD-1001" in result["handoff_package"]["issue_summary"]
    assert result["handoff_queue"]
    assert result["claimed_session"]["state"] == "human_in_service"
    agent_workflow = result["agent_workflow"]
    assert agent_workflow["plan"] == ["order_status", "logistics_tracking"]
    assert agent_workflow["state"] == "final"
    assert "YT-2001" in agent_workflow["final_answer"]
    assert [item["tool_name"] for item in agent_workflow["trace"]] == [
        "order_status",
        "logistics_tracking",
    ]
    assert [item["status"] for item in agent_workflow["trace"]] == ["success", "success"]
    assert agent_workflow["trace"][0]["observation"]["data"]["tracking_no"] == "YT-2001"
    assert result["cost_summary"]["sample_size"] >= 6
    assert result["cost_summary"]["cache_hits"] >= 1
    assert result["rag_eval_summary"]["failed"] == 0
    assert result["rag_eval_summary"]["offline_accuracy"] == 1.0
    assert result["rag_eval_summary"]["context_precision"] == 0.9375
    assert result["rag_eval_summary"]["context_recall"] == 1.0
    assert result["rag_eval_summary"]["reviewed_case_count"] == 10
    assert result["rag_eval_summary"]["cohort_breakdown"]["finance_ops"]["case_count"] == 2
    quality_gate = result["rag_quality_gate"]
    assert quality_gate["passed"] is True
    assert quality_gate["case_count"] == 10
    assert quality_gate["reviewed_case_count"] == 10
    assert quality_gate["labeled_case_count"] == 10
    assert quality_gate["offline_accuracy"] == 1.0
    assert quality_gate["context_precision"] == 0.9375
    assert quality_gate["context_recall"] == 1.0
    assert quality_gate["badcase_breakdown"] == {}
    assert quality_gate["failed_case_ids"] == []
    assert quality_gate["suggested_actions"] == []

    markdown_report = render_markdown_report(result)
    assert "# Customer AI Runtime 面试演示报告" in markdown_report
    assert "| RAG 质量门禁 | 通过 |" in markdown_report
    assert "offline_accuracy=1" in markdown_report
    assert "finance operations policy" in markdown_report
    assert "saas administration policy" in markdown_report
    assert "## 面试可讲点" in markdown_report


def test_external_readiness_skips_missing_optional_credentials() -> None:
    report = run_checks(env={}, timeout_seconds=0.1)

    assert report["overall_status"] == "skipped"
    assert report["status_counts"] == {"skipped": 10}
    assert report["audit"]["scope"] == "optional_external_integration_readiness"
    assert report["audit"]["timeout_seconds"] == 0.1
    assert report["audit"]["evidence_level"] == "configuration_and_probe"
    assert report["audit"]["generated_at"].endswith("Z")
    assert {check["name"] for check in report["checks"]} == {
        "openai_models",
        "openai_admin_usage",
        "openai_admin_costs",
        "qdrant_runtime_config",
        "qdrant_health",
        "qdrant_collections",
        "business_api",
        "ticket_api",
        "redis_queue",
        "postgres_queue",
    }
    assert all(check["status"] == "skipped" for check in report["checks"])
    openai_check = next(check for check in report["checks"] if check["name"] == "openai_models")
    assert openai_check["audit"]["category"] == "llm_provider"
    assert openai_check["audit"]["probe_type"] == "http_get"
    assert openai_check["audit"]["required_env"] == ["CUSTOMER_AI_OPENAI_API_KEY"]
    assert openai_check["audit"]["evidence"] == "missing_required_env"
    qdrant_config_check = next(
        check for check in report["checks"] if check["name"] == "qdrant_runtime_config"
    )
    assert qdrant_config_check["audit"]["category"] == "vector_store"
    assert qdrant_config_check["audit"]["probe_type"] == "configuration"
    assert qdrant_config_check["audit"]["evidence"] == "provider_not_enabled"
    postgres_check = next(check for check in report["checks"] if check["name"] == "postgres_queue")
    assert postgres_check["audit"]["category"] == "queue_dependency"
    assert postgres_check["audit"]["required_env"] == ["CUSTOMER_AI_POSTGRES_HOST"]
