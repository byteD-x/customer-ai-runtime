from __future__ import annotations

import json
from pathlib import Path

from scripts.check_external_readiness import (
    _render_output as render_readiness_output,
)
from scripts.check_external_readiness import (
    run_checks,
    write_output_file as write_readiness_output_file,
)
from scripts.eval_online_rag import _render_output as render_online_eval_output
from scripts.eval_online_rag import run_online_eval
from scripts.eval_online_rag import write_output_file as write_online_eval_output_file


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
            "CUSTOMER_AI_VECTOR_PROVIDER": "qdrant",
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
    assert report["status_counts"] == {"passed": 10}
    assert report["audit"]["scope"] == "optional_external_integration_readiness"
    assert report["audit"]["timeout_seconds"] == 0.1
    assert report["audit"]["evidence_level"] == "configuration_and_probe"
    assert report["audit"]["generated_at"].endswith("Z")
    assert "end-to-end integration" in report["audit"]["disclaimer"]
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
    openai_check = next(check for check in report["checks"] if check["name"] == "openai_models")
    assert openai_check["audit"] == {
        "category": "llm_provider",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_OPENAI_API_KEY"],
        "optional_env": ["CUSTOMER_AI_OPENAI_BASE_URL"],
        "evidence": "http_status_code",
    }
    qdrant_config_check = next(
        check for check in report["checks"] if check["name"] == "qdrant_runtime_config"
    )
    assert qdrant_config_check["status"] == "passed"
    assert qdrant_config_check["vector_provider"] == "qdrant"
    assert qdrant_config_check["audit"] == {
        "category": "vector_store",
        "probe_type": "configuration",
        "required_env": [],
        "optional_env": [
            "CUSTOMER_AI_VECTOR_PROVIDER",
            "CUSTOMER_AI_QDRANT_URL",
        ],
        "evidence": "configuration_consistent",
    }
    redis_check = next(check for check in report["checks"] if check["name"] == "redis_queue")
    assert redis_check["audit"]["category"] == "queue_dependency"
    assert redis_check["audit"]["probe_type"] == "tcp_connect"
    assert redis_check["audit"]["evidence"] == "tcp_connection"


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
    assert openai_check["audit"]["required_env"] == ["CUSTOMER_AI_OPENAI_API_KEY"]
    assert openai_check["audit"]["evidence"] == "http_status_code"


def test_external_readiness_fails_when_qdrant_provider_lacks_url() -> None:
    report = run_checks(
        env={"CUSTOMER_AI_VECTOR_PROVIDER": "qdrant"},
        timeout_seconds=0.1,
    )

    qdrant_config_check = next(
        check for check in report["checks"] if check["name"] == "qdrant_runtime_config"
    )
    assert report["overall_status"] == "failed"
    assert qdrant_config_check["status"] == "failed"
    assert qdrant_config_check["message"] == (
        "missing CUSTOMER_AI_QDRANT_URL while CUSTOMER_AI_VECTOR_PROVIDER=qdrant"
    )
    assert qdrant_config_check["vector_provider"] == "qdrant"
    assert qdrant_config_check["audit"]["evidence"] == "configuration_mismatch"


def test_external_readiness_skips_qdrant_config_when_provider_is_local() -> None:
    report = run_checks(
        env={
            "CUSTOMER_AI_VECTOR_PROVIDER": "local",
            "CUSTOMER_AI_QDRANT_URL": "http://qdrant:6333",
        },
        timeout_seconds=0.1,
        http_get=lambda url, headers, timeout_seconds: 200,
    )

    qdrant_config_check = next(
        check for check in report["checks"] if check["name"] == "qdrant_runtime_config"
    )
    assert report["overall_status"] == "ready"
    assert qdrant_config_check["status"] == "skipped"
    assert qdrant_config_check["message"] == (
        "CUSTOMER_AI_VECTOR_PROVIDER=local does not enable Qdrant"
    )
    assert qdrant_config_check["audit"]["evidence"] == "provider_not_enabled"


def test_external_readiness_report_can_be_written_to_file(tmp_path: Path) -> None:
    report = run_checks(env={}, timeout_seconds=0.1)
    output_text = render_readiness_output(report, json_output=True)
    output_path = tmp_path / "reports" / "external-readiness.json"

    write_readiness_output_file(output_path, output_text)

    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["overall_status"] == "skipped"
    assert exported["audit"]["scope"] == "optional_external_integration_readiness"


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


def test_online_rag_eval_report_can_be_written_to_file(tmp_path: Path) -> None:
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
    output_text = render_online_eval_output(report, json_output=True)
    output_path = tmp_path / "reports" / "online-rag-eval.json"

    write_online_eval_output_file(output_path, output_text)

    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["online_rag_eval_summary"]["summary"]["online_accuracy"] == 1.0


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


def test_online_rag_eval_reads_utf8_bom_jsonl(tmp_path: Path) -> None:
    sample_path = tmp_path / "online-rag-bom.jsonl"
    payload = json.dumps(
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
    )
    sample_path.write_text(
        "\ufeff" + payload,
        encoding="utf-8-sig",
    )

    report = run_online_eval(sample_path)

    assert report["summary"]["case_count"] == 1
    assert report["summary"]["online_accuracy"] == 1.0
