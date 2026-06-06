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
    status: str
    summary: str
    error: str | None = None
    duration_ms: float


class ToolWorkflowResult(BaseModel):
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
        trace: list[ToolTraceItem] = []

        for step_index, raw_step in enumerate(steps):
            step = (
                raw_step
                if isinstance(raw_step, ToolWorkflowStep)
                else ToolWorkflowStep.model_validate(raw_step)
            )
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
            trace.append(
                ToolTraceItem(
                    step_index=step_index,
                    tool_name=step.tool_name,
                    status=result.status,
                    summary=result.summary,
                    error=None if result.status == "success" else result.summary,
                    duration_ms=duration_ms,
                )
            )
            if result.status != "success":
                break

        return ToolWorkflowResult(trace=trace)
