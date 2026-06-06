from __future__ import annotations

import json
from pathlib import Path

from scripts.check_external_readiness import run_checks
from scripts.eval_online_rag import run_online_eval


def test_external_readiness_passes_with_mocked_dependencies() -> None:
    observed_tcp_endpoints: list[tuple[str, int]] = []

    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> int:
        assert timeout_seconds == 0.1
        assert url.startswith(("https://api.example.test", "http://qdrant", "http://api"))
        return 200

    def fake_tcp_connect(host: str, port: int, timeout_seconds: float) -> None:
        assert timeout_seconds == 0.1
        observed_tcp_endpoints.append((host, port))

    report = run_checks(
        env={
            "CUSTOMER_AI_OPENAI_API_KEY": "real-openai-key",
            "CUSTOMER_AI_OPENAI_BASE_URL": "https://api.example.test/v1",
            "CUSTOMER_AI_OPENAI_ADMIN_API_KEY": "real-admin-key",
            "CUSTOMER_AI_OPENAI_ADMIN_BASE_URL": "https://api.example.test/v1",
            "CUSTOMER_AI_QDRANT_URL": "http://qdrant:6333",
            "CUSTOMER_AI_QDRANT_API_KEY": "real-qdrant-key",
            "CUSTOMER_AI_BUSINESS_API_BASE_URL": "http://api/business",
            "CUSTOMER_AI_BUSINESS_API_KEY": "real-business-key",
            "CUSTOMER_AI_TICKET_API_BASE_URL": "http://api/tickets",
            "CUSTOMER_AI_TICKET_API_KEY": "real-ticket-key",
            "CUSTOMER_AI_REDIS_HOST": "redis",
            "CUSTOMER_AI_REDIS_PORT": "6379",
            "CUSTOMER_AI_POSTGRES_HOST": "postgres",
            "CUSTOMER_AI_POSTGRES_PORT": "5432",
        },
        timeout_seconds=0.1,
        http_get=fake_http_get,
        tcp_connect=fake_tcp_connect,
    )

    assert report["overall_status"] == "ready"
    assert report["status_counts"] == {"passed": 9}
    assert observed_tcp_endpoints == [("redis", 6379), ("postgres", 5432)]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "real-openai-key" not in serialized
    assert "real-admin-key" not in serialized
    assert "real-qdrant-key" not in serialized
    assert all(
        any("***" in value for value in check["headers"].values())
        for check in report["checks"]
        if check.get("headers")
    )


def test_external_readiness_fails_on_http_failure() -> None:
    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> int:
        return 403 if url.endswith("/models") else 200

    report = run_checks(
        env={"CUSTOMER_AI_OPENAI_API_KEY": "real-openai-key"},
        timeout_seconds=0.1,
        http_get=fake_http_get,
    )

    openai_check = next(check for check in report["checks"] if check["name"] == "openai_models")
    assert report["overall_status"] == "failed"
    assert openai_check["status"] == "failed"
    assert openai_check["message"] == "HTTP 403"


def test_online_rag_eval_reads_jsonl_labeled_samples(tmp_path: Path) -> None:
    sample_path = tmp_path / "online-rag.jsonl"
    sample_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "sample_id": "sample_1",
                        "dataset_id": "prod_2026w22",
                        "cohort": "gray_5p",
                        "review_status": "reviewed",
                        "question": "How long does SCIM sync take?",
                        "expected_route": "knowledge",
                        "expected_citation_keywords": ["15 minutes"],
                        "min_score": 0.2,
                        "route": "knowledge",
                        "citations": [
                            {
                                "title": "identity sync",
                                "excerpt": "SCIM provisioning syncs within 15 minutes.",
                                "score": 0.6,
                            }
                        ],
                    }
                ),
                json.dumps(
                    {
                        "sample_id": "sample_2",
                        "dataset_id": "prod_2026w22",
                        "cohort": "gray_5p",
                        "review_status": "reviewed",
                        "question": "Unrelated billing question",
                        "expected_route": "knowledge",
                        "expect_effective_hit": False,
                        "min_score": 0.5,
                        "route": "knowledge",
                        "citations": [],
                        "refusal": True,
                        "refusal_reason": "no_effective_citation",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    report = run_online_eval(sample_path)

    assert report["summary"]["case_count"] == 2
    assert report["summary"]["failed"] == 0
    assert report["summary"]["accuracy_source"] == "online_labeled_sample"
    assert report["summary"]["online_accuracy"] == 1.0
    assert report["summary"]["reviewed_case_count"] == 2
    assert report["summary"]["cohort_breakdown"]["gray_5p"]["case_count"] == 2


def test_online_rag_eval_reads_json_cases_and_results(tmp_path: Path) -> None:
    sample_path = tmp_path / "online-rag.json"
    sample_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "dataset_id": "prod_2026w22",
                        "cohort": "approved",
                        "review_status": "approved",
                        "question": "What is refund proof?",
                        "expected_route": "knowledge",
                        "expected_citation_keywords": ["payment proof"],
                        "min_score": 0.1,
                    }
                ],
                "results": [
                    {
                        "case_id": "case_1",
                        "route": "knowledge",
                        "citations": [
                            {
                                "title": "refund",
                                "excerpt": "Keep payment proof for refund requests.",
                                "score": 0.5,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = run_online_eval(sample_path)

    assert report["summary"]["case_count"] == 1
    assert report["summary"]["online_accuracy"] == 1.0
    assert report["cases"][0]["dataset_id"] == "prod_2026w22"


def test_online_rag_eval_does_not_treat_empty_citations_as_refusal(tmp_path: Path) -> None:
    sample_path = tmp_path / "online-rag.jsonl"
    sample_path.write_text(
        json.dumps(
            {
                "sample_id": "sample_no_refusal",
                "question": "Unrelated billing question",
                "expected_route": "knowledge",
                "expect_effective_hit": False,
                "route": "knowledge",
                "citations": [],
            }
        ),
        encoding="utf-8",
    )

    report = run_online_eval(sample_path)

    assert report["summary"]["failed"] == 1
    assert report["summary"]["online_accuracy"] == 0.0
    assert report["summary"]["refusal_accuracy"] == 0.0
    assert report["failures"][0]["actual_refusal"] is False
