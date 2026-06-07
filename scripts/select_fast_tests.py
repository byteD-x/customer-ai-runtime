from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass

STREAM_TARGETS = (
    "tests/test_runtime_api.py::test_chat_knowledge_flow",
    "tests/test_runtime_api.py::test_chat_knowledge_stream_flow",
    "tests/test_runtime_api.py::test_chat_stream_returns_error_event_for_generation_errors",
)

SUITE_TARGETS = {
    "stream": STREAM_TARGETS,
    "api": ("tests/test_runtime_api.py",),
    "handoff": (
        "tests/test_runtime_api.py::test_handoff_flow",
        "tests/test_runtime_api.py::test_message_feedback_can_request_human_handoff",
        "tests/test_runtime_api.py::test_handoff_queue_orders_and_claims_by_skill_group",
        "tests/test_runtime_api.py::test_sqlite_handoff_queue_supports_shared_transaction_claim",
        "tests/test_runtime_api.py::test_handoff_queue_can_use_sqlite_backend_from_settings",
        "tests/test_runtime_api.py::test_handoff_service_uses_injected_queue_backend",
    ),
    "rag": (
        "tests/test_rag_quality.py",
        "tests/test_interview_artifacts.py",
    ),
    "agent": ("tests/test_agent_workflow.py",),
    "providers": (
        "tests/test_provider_extensions.py",
        "tests/test_speech_provider_extensions.py",
        "tests/test_openai_prompt_sanitization.py",
    ),
    "smoke": (
        "tests/test_builtin_plugins.py",
        "tests/test_routing_enhancements.py",
        "tests/test_response_enhancement.py",
        "tests/test_rate_limit_subject.py",
    ),
    "external": ("tests/test_external_readiness_and_online_eval.py",),
    "selector": ("tests/test_select_fast_tests.py",),
    "full": ("tests",),
}

SUITE_ORDER = (
    "selector",
    "stream",
    "api",
    "handoff",
    "rag",
    "agent",
    "providers",
    "smoke",
    "external",
    "full",
)

FULL_FALLBACK_PATHS = {
    ".github/workflows/ci.yml",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "pnpm-lock.yaml",
    "scripts/test.ps1",
}


@dataclass(frozen=True)
class FastTestSelection:
    changed_paths: tuple[str, ...]
    suites: tuple[str, ...]
    targets: tuple[str, ...]
    reason: str


def select_targets(changed_paths: Iterable[str]) -> FastTestSelection:
    normalized_paths = tuple(
        path for path in (_normalize_path(item) for item in changed_paths) if path
    )
    if not normalized_paths:
        return _selection(
            changed_paths=normalized_paths,
            suites=("full",),
            reason="未发现可用于选择的改动文件，保守回退完整 pytest。",
        )

    if any(path in FULL_FALLBACK_PATHS for path in normalized_paths):
        return _selection(
            changed_paths=normalized_paths,
            suites=("full",),
            reason="检测到测试门禁、依赖或 CI 配置变更，保守回退完整 pytest。",
        )

    direct_targets: list[str] = []
    suites: set[str] = set()
    unknown_runtime_change = False

    for path in normalized_paths:
        if path.startswith("tests/") and path.endswith(".py"):
            direct_targets.append(path)
            continue
        if path in {"scripts/select_fast_tests.py", "scripts/test-fast.ps1"}:
            suites.add("selector")
            continue
        if path == "scripts/eval_rag.py" or path.startswith("examples/"):
            suites.add("rag")
            continue
        if path in {"scripts/eval_online_rag.py", "scripts/check_external_readiness.py"}:
            suites.add("external")
            continue
        if path.startswith("docs/") or path in {"readme.md", "agents.md"}:
            suites.add("smoke")
            continue
        if path.startswith("src/customer_ai_runtime/"):
            matched_suites = _suites_for_source_path(path)
            if not matched_suites:
                unknown_runtime_change = True
            else:
                suites.update(matched_suites)
            continue
        unknown_runtime_change = True

    if unknown_runtime_change:
        return _selection(
            changed_paths=normalized_paths,
            suites=("full",),
            reason="存在无法安全归类的运行时代码或仓库文件变更，保守回退完整 pytest。",
        )

    ordered_suites = tuple(suite for suite in SUITE_ORDER if suite in suites)
    targets = _dedupe([*direct_targets, *targets_for_suites(ordered_suites)])
    if not targets:
        return _selection(
            changed_paths=normalized_paths,
            suites=("full",),
            reason="未能从改动文件推导出目标测试，保守回退完整 pytest。",
        )
    return FastTestSelection(
        changed_paths=normalized_paths,
        suites=ordered_suites,
        targets=tuple(targets),
        reason="根据当前改动文件自动选择目标化 pytest。",
    )


def targets_for_suites(suites: Iterable[str]) -> tuple[str, ...]:
    return tuple(_dedupe(target for suite in suites for target in SUITE_TARGETS[suite]))


def changed_paths_from_git() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        if path:
            paths.append(path)
    return tuple(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select fast pytest targets from changed files.")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Changed file path. Can be passed multiple times. Defaults to git status.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON selection.")
    args = parser.parse_args()

    changed_paths = tuple(args.changed_path) if args.changed_path else changed_paths_from_git()
    selection = select_targets(changed_paths)
    if args.json:
        print(json.dumps(asdict(selection), ensure_ascii=False))
    else:
        for target in selection.targets:
            print(target)
    return 0


def _suites_for_source_path(path: str) -> tuple[str, ...]:
    if path == "src/customer_ai_runtime/evaluation.py":
        return ("rag",)
    if path.startswith("src/customer_ai_runtime/providers/"):
        return ("providers",)
    if path in {
        "src/customer_ai_runtime/application/agent_workflow.py",
    }:
        return ("agent",)
    if path == "src/customer_ai_runtime/application/tool_catalog.py":
        return ("api",)
    if path == "src/customer_ai_runtime/application/container.py":
        return ("api", "handoff", "providers")
    if path.startswith("src/customer_ai_runtime/application/"):
        suite = _suite_for_application_path(path)
        return () if suite is None else (suite,)
    if path.startswith("src/customer_ai_runtime/api/"):
        return ("api",)
    if path.startswith("src/customer_ai_runtime/core/"):
        return ("api",)
    if path.startswith("src/customer_ai_runtime/domain/"):
        return ("api",)
    return ()


def _suite_for_application_path(path: str) -> str | None:
    if any(
        name in path
        for name in (
            "retrieval.py",
            "rag_quality.py",
            "knowledge.py",
        )
    ):
        return "rag"
    if any(
        name in path
        for name in (
            "plugins.py",
            "routing.py",
            "response_enhancement.py",
            "rate_limit.py",
        )
    ):
        return "smoke"
    if any(
        name in path
        for name in (
            "chat.py",
            "admin.py",
            "runtime.py",
            "auth.py",
            "business.py",
            "costs.py",
        )
    ):
        return "api"
    if any(
        name in path
        for name in (
            "handoff.py",
            "handoff_queue.py",
        )
    ):
        return "handoff"
    return None


def _selection(
    *,
    changed_paths: tuple[str, ...],
    suites: tuple[str, ...],
    reason: str,
) -> FastTestSelection:
    return FastTestSelection(
        changed_paths=changed_paths,
        suites=suites,
        targets=targets_for_suites(suites),
        reason=reason,
    )


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lower()


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


if __name__ == "__main__":
    raise SystemExit(main())
