from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from inspect import isawaitable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from customer_ai_runtime.core.errors import AppError
from customer_ai_runtime.domain.models import BusinessResult


class ToolWorkflowStep(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolTraceItem(BaseModel):
    step_index: int
    tool_name: str
    phase: str = "execute"
    status: str
    summary: str
    error: str | None = None
    observation: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float


class ToolWorkflowResult(BaseModel):
    plan: list[str] = Field(default_factory=list)
    state: str = "final"
    final_answer: str = ""
    trace: list[ToolTraceItem] = Field(default_factory=list)


ToolExecutor = Callable[..., BusinessResult | Awaitable[BusinessResult]]


class AgentWorkflowService:
    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._tool_executor = tool_executor

    async def run(
        self,
        context: Any,
        steps: list[ToolWorkflowStep | dict[str, Any]],
        max_steps: int = 3,
        allowed_tools: Iterable[str] | None = None,
    ) -> ToolWorkflowResult:
        if len(steps) > max_steps:
            raise AppError(
                code="validation_error",
                message=f"工具步骤数量不能超过 {max_steps}",
                status_code=400,
            )

        allowed_tool_set = set(allowed_tools) if allowed_tools is not None else None
        normalized_steps = [
            raw_step
            if isinstance(raw_step, ToolWorkflowStep)
            else ToolWorkflowStep.model_validate(raw_step)
            for raw_step in steps
        ]
        plan = [step.tool_name for step in normalized_steps]
        trace: list[ToolTraceItem] = []
        state = "final"
        final_answer = ""

        for step_index, step in enumerate(normalized_steps):
            if allowed_tool_set is not None and step.tool_name not in allowed_tool_set:
                raise AppError(
                    code="forbidden",
                    message=f"不允许执行工具：{step.tool_name}",
                    status_code=403,
                )

            started_at = perf_counter()
            raw_result = self._tool_executor(
                context=context,
                tool_name=step.tool_name,
                parameters=step.parameters,
            )
            if isawaitable(raw_result):
                raw_result = await raw_result
            result = BusinessResult.model_validate(raw_result)
            duration_ms = (perf_counter() - started_at) * 1000
            final_answer = result.summary
            trace.append(
                ToolTraceItem(
                    step_index=step_index,
                    tool_name=step.tool_name,
                    phase="execute",
                    status=result.status,
                    summary=result.summary,
                    error=None if result.status == "success" else result.summary,
                    observation={
                        "data": result.data,
                        "requires_handoff": result.requires_handoff,
                        "integration_context": result.integration_context,
                    },
                    duration_ms=duration_ms,
                )
            )
            if result.status != "success":
                state = "repair_required"
                break

        return ToolWorkflowResult(
            plan=plan,
            state=state,
            final_answer=final_answer,
            trace=trace,
        )
