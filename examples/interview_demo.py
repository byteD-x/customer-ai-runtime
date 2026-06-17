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
            _seed_knowledge_bases(client, eval_payload)
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
            finance_knowledge = _chat(
                client,
                "What is required for finance expense reimbursement approval?",
                knowledge_base_id="kb_finance_ops",
            )
            saas_knowledge = _chat(
                client,
                "How long do SCIM provisioning changes take to sync?",
                knowledge_base_id="kb_saas",
            )
            business = _chat(
                client,
                "订单 ORD-1001 发货了吗？",
                integration_context={"industry": "ecommerce"},
            )
            risk = _chat(
                client,
                "我要投诉监管处理",
                integration_context={
                    "industry": "ecommerce",
                    "business_objects": {"order_id": "ORD-1001"},
                    "behavior_signals": {"frustrated": True, "repeat_contact_7d": 2},
                },
            )
            handoff_queue = _get_handoff_queue(client)
            claimed_session = _claim_next_handoff(client)
            agent_workflow = _run_agent_workflow(client)
            cost_summary = _get_cost_summary(client)
            rag_eval = _run_rag_eval(client, eval_payload["cases"])
            rag_quality_gate = _build_rag_quality_gate(rag_eval)
        get_settings.cache_clear()

    return {
        "storage_root": str(resolved_storage_root),
        "route": {
            "knowledge_first": knowledge_first["route"],
            "knowledge_cached": knowledge_cached["route"],
            "knowledge_cache_hit": knowledge_cached["cache_hit"],
            "finance_knowledge": finance_knowledge["route"],
            "saas_knowledge": saas_knowledge["route"],
            "business": business["route"],
            "risk": risk["route"],
        },
        "model_route": knowledge_first.get("model_route"),
        "citations": knowledge_first["citations"],
        "finance_knowledge": finance_knowledge,
        "saas_knowledge": saas_knowledge,
        "tool_result": business["tool_result"],
        "handoff_package": risk["handoff"],
        "handoff_queue": handoff_queue,
        "claimed_session": claimed_session,
        "agent_workflow": agent_workflow,
        "cost_summary": cost_summary,
        "rag_eval_summary": rag_eval["summary"],
        "rag_quality_gate": rag_quality_gate,
        "rag_eval_failures": rag_eval["failures"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local interview demo flow.")
    parser.add_argument("--storage-root", type=Path, default=None)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    output_group.add_argument(
        "--markdown",
        action="store_true",
        help="Print a human-readable Markdown report.",
    )
    args = parser.parse_args()

    result = run_demo(storage_root=args.storage_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(render_markdown_report(result))
    else:
        for key in (
            "route",
            "citations",
            "finance_knowledge",
            "saas_knowledge",
            "tool_result",
            "handoff_package",
            "handoff_queue",
            "claimed_session",
            "agent_workflow",
            "cost_summary",
            "rag_eval_summary",
            "rag_quality_gate",
        ):
            print(key)
            print(json.dumps(result[key], ensure_ascii=False, indent=2))
    return 0 if result["rag_eval_summary"]["failed"] == 0 else 1


def render_markdown_report(result: dict[str, Any]) -> str:
    route = dict(result.get("route") or {})
    cost_summary = dict(result.get("cost_summary") or {})
    rag_eval_summary = dict(result.get("rag_eval_summary") or {})
    rag_quality_gate = dict(result.get("rag_quality_gate") or {})
    finance_knowledge = dict(result.get("finance_knowledge") or {})
    saas_knowledge = dict(result.get("saas_knowledge") or {})
    tool_result = dict(result.get("tool_result") or {})
    handoff_package = dict(result.get("handoff_package") or {})
    agent_workflow = dict(result.get("agent_workflow") or {})

    lines: list[str] = [
        "# Customer AI Runtime 面试演示报告",
        "",
        "## 一句话结论",
        _markdown_table(
            [
                ("知识缓存", _yes_no(route.get("knowledge_cache_hit"))),
                (
                    "RAG 评测",
                    f"{rag_eval_summary.get('passed', 0)} / {rag_eval_summary.get('case_count', 0)} 通过",
                ),
                (
                    "RAG 质量门禁",
                    "通过" if rag_quality_gate.get("passed") else "未通过",
                ),
                (
                    "Agent 工具流",
                    str(agent_workflow.get("state") or "-"),
                ),
                (
                    "成本样本",
                    (
                        f"{cost_summary.get('sample_size', 0)} 条 / "
                        f"{_format_number(cost_summary.get('total_tokens'))} tokens / "
                        f"{_format_number(cost_summary.get('estimated_cost_cents'))}（美分）"
                    ),
                ),
            ]
        ),
        "",
        "## 关键链路",
        _markdown_table(
            [
                ("知识问答", _format_route_pair(route.get("knowledge_first"))),
                ("业务查询", _format_route_pair(route.get("business"))),
                ("风险接管", _format_route_pair(route.get("risk"))),
                ("模型路由", _format_model_route(result)),
                (
                    "RAG 指标",
                    (
                        f"offline_accuracy={_format_number(rag_eval_summary.get('offline_accuracy'))}, "
                        f"context_precision={_format_number(rag_eval_summary.get('context_precision'))}, "
                        f"context_recall={_format_number(rag_eval_summary.get('context_recall'))}"
                    ),
                ),
                (
                    "质量门禁",
                    f"failed_case_count={len(rag_quality_gate.get('failed_case_ids') or [])}",
                ),
            ]
        ),
        "",
        "## 业务证据",
        _bullet_line(
            "财务运营知识问答引用",
            _citation_summary(finance_knowledge),
        ),
        _bullet_line(
            "SaaS 管理知识问答引用",
            _citation_summary(saas_knowledge),
        ),
        _bullet_line(
            "业务工具结果",
            str(tool_result.get("summary") or "-"),
        ),
        _bullet_line(
            "人工接管摘要",
            str(handoff_package.get("issue_summary") or "-"),
        ),
        _bullet_line(
            "Agent 最终结果",
            str(agent_workflow.get("final_answer") or "-"),
        ),
        "",
        "## 成本与评测",
        _markdown_table(
            [
                (
                    "成本聚合",
                    (
                        f"sample_size={cost_summary.get('sample_size', 0)}, "
                        f"cache_hits={cost_summary.get('cache_hits', 0)}, "
                        f"estimated_cost_cents={_format_number(cost_summary.get('estimated_cost_cents'))}"
                    ),
                ),
                (
                    "按路由",
                    _summarize_cost_buckets(cost_summary.get("by_route") or {}),
                ),
                (
                    "按模型",
                    _summarize_cost_buckets(cost_summary.get("by_model") or {}),
                ),
            ]
        ),
        _bullet_line(
            "RAG 质量门禁通过",
            "是" if rag_quality_gate.get("passed") else "否",
        ),
        _bullet_line(
            "失败 case",
            _format_failed_cases(rag_quality_gate.get("failed_case_ids") or []),
        ),
        _bullet_line(
            "修复建议",
            _format_suggested_actions(rag_quality_gate.get("suggested_actions") or []),
        ),
    ]

    badcase_breakdown = rag_quality_gate.get("badcase_breakdown") or {}
    if badcase_breakdown:
        lines.extend(
            [
                "",
                "## Badcase Breakdown",
                "```json",
                json.dumps(badcase_breakdown, ensure_ascii=False, indent=2),
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## 面试可讲点",
            "- 知识问答、业务查询、风险转人工、Agent 工具流和成本治理已经串成一个可本地复现的闭环。",
            "- `rag_quality_gate` 可直接回答失败后如何定位路由、切片、召回和拒答阈值。",
            "- 该报告不宣称线上准确率、真实成本节省或外部 provider 联调通过，只代表当前本地样例。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _load_eval_payload() -> dict[str, Any]:
    return json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))


def _markdown_table(rows: list[tuple[str, str]]) -> str:
    lines = ["| 指标 | 值 |", "| --- | --- |"]
    for label, value in rows:
        lines.append(f"| {label} | {value} |")
    return "\n".join(lines)


def _bullet_line(label: str, value: str) -> str:
    return f"- {label}：{value}"


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    text = f"{number:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _yes_no(value: Any) -> str:
    return "是" if bool(value) else "否"


def _format_route_pair(route_name: Any) -> str:
    label = str(route_name or "-")
    return f"`{label}`"


def _format_model_route(result: dict[str, Any]) -> str:
    model_route = dict(result.get("model_route") or {})
    strategy = str(model_route.get("strategy") or "-")
    selected_model = str(model_route.get("selected_model") or "-")
    provider = str(model_route.get("provider") or "-")
    return f"{strategy} / {selected_model} / {provider}"


def _citation_summary(knowledge_payload: dict[str, Any]) -> str:
    citations = knowledge_payload.get("citations") or []
    if not isinstance(citations, list) or not citations:
        return "-"
    citation = citations[0]
    if not isinstance(citation, dict):
        return "-"
    title = str(citation.get("title") or "-")
    excerpt = str(citation.get("excerpt") or "-")
    return f"`{title}` - {excerpt}"


def _summarize_cost_buckets(buckets: dict[str, Any]) -> str:
    if not buckets:
        return "-"
    parts: list[str] = []
    for name, payload in sorted(buckets.items()):
        if not isinstance(payload, dict):
            continue
        request_count = payload.get("request_count", 0)
        estimated_cost_cents = _format_number(payload.get("estimated_cost_cents"))
        parts.append(f"`{name}` {request_count} 次 / {estimated_cost_cents}（美分）")
    return "；".join(parts) if parts else "-"


def _format_failed_cases(case_ids: list[str]) -> str:
    if not case_ids:
        return "无"
    return ", ".join(f"`{case_id}`" for case_id in case_ids)


def _format_suggested_actions(actions: list[str]) -> str:
    if not actions:
        return "无"
    return "；".join(actions)


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


def _run_agent_workflow(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents/tool-workflow",
        headers=ADMIN_HEADERS,
        json={
            "tenant_id": "demo-tenant",
            "channel": "web",
            "integration_context": {"industry": "ecommerce"},
            "allowed_tools": ["order_status", "logistics_tracking"],
            "max_steps": 2,
            "steps": [
                {
                    "tool_name": "order_status",
                    "parameters": {"order_id": "ORD-1001"},
                },
                {
                    "tool_name": "logistics_tracking",
                    "parameters": {"tracking_no": "YT-2001"},
                },
            ],
        },
    )
    response.raise_for_status()
    return dict(response.json()["data"])


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


def _build_rag_quality_gate(rag_eval: dict[str, Any]) -> dict[str, Any]:
    summary = dict(rag_eval.get("summary") or {})
    failures = list(rag_eval.get("failures") or [])
    badcase_breakdown = dict(summary.get("badcase_breakdown") or {})
    suggested_actions = [
        payload["suggested_action"]
        for _, payload in sorted(badcase_breakdown.items())
        if isinstance(payload, dict) and payload.get("suggested_action")
    ]
    failed_case_ids = [str(item.get("case_id")) for item in failures if item.get("case_id")]
    failed = int(summary.get("failed") or 0)
    reviewed_case_count = int(summary.get("reviewed_case_count") or 0)
    labeled_case_count = int(summary.get("labeled_case_count") or 0)
    case_count = int(summary.get("case_count") or 0)
    passed = (
        failed == 0
        and case_count > 0
        and reviewed_case_count == case_count
        and labeled_case_count == case_count
    )
    return {
        "passed": passed,
        "case_count": case_count,
        "reviewed_case_count": reviewed_case_count,
        "labeled_case_count": labeled_case_count,
        "offline_accuracy": summary.get("offline_accuracy"),
        "citation_accuracy": summary.get("citation_accuracy"),
        "context_precision": summary.get("context_precision"),
        "context_recall": summary.get("context_recall"),
        "refusal_accuracy": summary.get("refusal_accuracy"),
        "faithfulness_score": summary.get("faithfulness_score"),
        "badcase_breakdown": badcase_breakdown,
        "failed_case_ids": failed_case_ids,
        "suggested_actions": suggested_actions,
    }


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
