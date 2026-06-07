from __future__ import annotations

from scripts.select_fast_tests import select_targets, targets_for_suites


def test_selects_rag_suite_for_evaluation_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/evaluation.py"])

    assert selection.suites == ("rag",)
    assert selection.targets == (
        "tests/test_rag_quality.py",
        "tests/test_interview_artifacts.py",
    )


def test_selects_providers_suite_for_provider_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/providers/openai_provider.py"])

    assert selection.suites == ("providers",)
    assert "tests/test_provider_extensions.py" in selection.targets
    assert "tests/test_speech_provider_extensions.py" in selection.targets


def test_selects_agent_suite_for_workflow_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/application/agent_workflow.py"])

    assert selection.suites == ("agent",)
    assert selection.targets == ("tests/test_agent_workflow.py",)


def test_selects_api_suite_for_tool_catalog_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/application/tool_catalog.py"])

    assert selection.suites == ("api",)
    assert selection.targets == ("tests/test_runtime_api.py",)


def test_selects_api_and_costs_suites_for_admin_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/application/admin.py"])

    assert selection.suites == ("api", "costs")
    assert selection.targets == ("tests/test_runtime_api.py",)


def test_selects_handoff_suite_for_handoff_queue_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/application/handoff_queue.py"])

    assert selection.suites == ("handoff",)
    assert selection.targets == (
        "tests/test_runtime_api.py::test_handoff_flow",
        "tests/test_runtime_api.py::test_message_feedback_can_request_human_handoff",
        "tests/test_runtime_api.py::test_handoff_queue_orders_and_claims_by_skill_group",
        "tests/test_runtime_api.py::test_sqlite_handoff_queue_supports_shared_transaction_claim",
        "tests/test_runtime_api.py::test_handoff_queue_can_use_sqlite_backend_from_settings",
        "tests/test_runtime_api.py::test_handoff_service_uses_injected_queue_backend",
    )


def test_selects_api_and_providers_suites_for_container_change() -> None:
    selection = select_targets(["src/customer_ai_runtime/application/container.py"])

    assert selection.suites == ("api", "handoff", "providers")
    assert "tests/test_runtime_api.py" in selection.targets
    assert (
        "tests/test_runtime_api.py::test_handoff_queue_can_use_sqlite_backend_from_settings"
        not in selection.targets
    )
    assert "tests/test_provider_extensions.py" in selection.targets
    assert "tests/test_speech_provider_extensions.py" in selection.targets


def test_selects_smoke_suite_for_docs_change() -> None:
    selection = select_targets(["docs/testing.md"])

    assert selection.suites == ("smoke",)
    assert "tests/test_routing_enhancements.py" in selection.targets


def test_merges_direct_test_targets_and_suite_targets_without_duplicates() -> None:
    selection = select_targets(
        [
            "tests/test_rag_quality.py",
            "src/customer_ai_runtime/evaluation.py",
        ]
    )

    assert selection.suites == ("rag",)
    assert selection.targets.count("tests/test_rag_quality.py") == 1
    assert selection.targets == (
        "tests/test_rag_quality.py",
        "tests/test_interview_artifacts.py",
    )


def test_file_target_covers_node_targets_from_other_suites() -> None:
    targets = targets_for_suites(("api", "costs"))

    assert targets == ("tests/test_runtime_api.py",)


def test_directory_target_covers_nested_suite_targets() -> None:
    targets = targets_for_suites(("full", "api", "rag"))

    assert targets == ("tests",)


def test_unknown_runtime_change_falls_back_to_full_pytest() -> None:
    selection = select_targets(["src/customer_ai_runtime/new_runtime_module.py"])

    assert selection.suites == ("full",)
    assert selection.targets == ("tests",)


def test_selector_script_change_selects_selector_suite() -> None:
    selection = select_targets(["scripts/select_fast_tests.py"])

    assert selection.suites == ("selector",)
    assert selection.targets == ("tests/test_select_fast_tests.py",)


def test_empty_change_set_falls_back_to_full_pytest() -> None:
    selection = select_targets([])

    assert selection.suites == ("full",)
    assert selection.targets == ("tests",)
