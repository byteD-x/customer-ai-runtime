from __future__ import annotations

import pytest

from customer_ai_runtime.application.agent_workflow import (
    AgentWorkflowService,
    ToolWorkflowStep,
)
from customer_ai_runtime.core.errors import AppError
from customer_ai_runtime.domain.models import BusinessResult


@pytest.mark.anyio
async def test_agent_workflow_runs_two_successful_steps() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_executor(*, context: dict[str, str], tool_name: str, parameters: dict[str, str]):
        calls.append((tool_name, parameters))
        return BusinessResult(
            tool_name=tool_name,
            status="success",
            summary=f"{context['tenant_id']}:{tool_name}",
        )

    service = AgentWorkflowService(fake_executor)

    result = await service.run(
        context={"tenant_id": "demo-tenant"},
        steps=[
            ToolWorkflowStep(tool_name="order_status", parameters={"order_id": "ORD-1"}),
            ToolWorkflowStep(tool_name="logistics_tracking", parameters={"tracking_no": "YT-1"}),
        ],
        allowed_tools={"order_status", "logistics_tracking"},
    )

    assert calls == [
        ("order_status", {"order_id": "ORD-1"}),
        ("logistics_tracking", {"tracking_no": "YT-1"}),
    ]
    assert [item.tool_name for item in result.trace] == ["order_status", "logistics_tracking"]
    assert [item.step_index for item in result.trace] == [0, 1]
    assert [item.status for item in result.trace] == ["success", "success"]
    assert all(item.error is None for item in result.trace)
    assert all(item.duration_ms >= 0 for item in result.trace)


@pytest.mark.anyio
async def test_agent_workflow_rejects_steps_over_max_steps() -> None:
    async def fake_executor(**_: object) -> BusinessResult:
        raise AssertionError("executor should not be called")

    service = AgentWorkflowService(fake_executor)

    with pytest.raises(AppError) as error:
        await service.run(
            context={},
            steps=[
                {"tool_name": "first", "parameters": {}},
                {"tool_name": "second", "parameters": {}},
            ],
            max_steps=1,
        )

    assert error.value.code == "validation_error"
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_agent_workflow_rejects_forbidden_tool() -> None:
    async def fake_executor(**_: object) -> BusinessResult:
        raise AssertionError("executor should not be called")

    service = AgentWorkflowService(fake_executor)

    with pytest.raises(AppError) as error:
        await service.run(
            context={},
            steps=[{"tool_name": "refund_status", "parameters": {}}],
            allowed_tools={"order_status"},
        )

    assert error.value.code == "forbidden"
    assert error.value.status_code == 403


@pytest.mark.anyio
async def test_agent_workflow_stops_after_first_business_failure() -> None:
    calls: list[str] = []

    async def fake_executor(*, context: object, tool_name: str, parameters: dict[str, str]):
        calls.append(tool_name)
        return BusinessResult(
            tool_name=tool_name,
            status="missing_parameter",
            summary="缺少 order_id",
            data={"error": "missing order_id"},
        )

    service = AgentWorkflowService(fake_executor)

    result = await service.run(
        context={},
        steps=[
            {"tool_name": "order_status", "parameters": {}},
            {"tool_name": "logistics_tracking", "parameters": {"tracking_no": "YT-1"}},
        ],
        allowed_tools={"order_status", "logistics_tracking"},
    )

    assert calls == ["order_status"]
    assert len(result.trace) == 1
    assert result.trace[0].step_index == 0
    assert result.trace[0].tool_name == "order_status"
    assert result.trace[0].status == "missing_parameter"
    assert result.trace[0].summary == "缺少 order_id"
    assert result.trace[0].error == "缺少 order_id"
