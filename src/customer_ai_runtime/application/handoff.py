from __future__ import annotations

from customer_ai_runtime.application.plugins import (
    HumanHandoffPlugin,
    PluginRegistry,
    context_to_plugin_context,
)
from customer_ai_runtime.domain.models import Session, SessionState, utcnow
from customer_ai_runtime.domain.platform import BusinessContext, PluginKind


class HandoffService:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    async def should_handoff(
        self,
        *,
        business_context: BusinessContext,
        route: str,
        response: dict,
    ) -> tuple[bool, str]:
        plugin_context = context_to_plugin_context(
            tenant_id=business_context.tenant_id,
            channel=business_context.channel,
            session_id=business_context.session_id,
            industry=business_context.industry,
            integration_context=business_context.integration_context,
            host_auth_context=business_context.host_auth_context,
            business_context=business_context,
            route=route,
            response=response,
        )
        best_reason = ""
        should_handoff = False
        best_priority = -1
        for plugin in self._registry.resolve(
            PluginKind.HUMAN_HANDOFF,
            tenant_id=business_context.tenant_id,
            industry=business_context.industry,
            channel=business_context.channel,
        ):
            if not isinstance(plugin, HumanHandoffPlugin):
                continue
            decision = await plugin.evaluate(plugin_context)
            if decision.should_handoff and decision.priority > best_priority:
                should_handoff = True
                best_reason = decision.reason
                best_priority = decision.priority
        return should_handoff, best_reason

    async def create_package(
        self,
        session: Session,
        reason: str,
        business_context: BusinessContext,
    ):
        session.state = SessionState.WAITING_HUMAN
        session.waiting_human = True
        session.handoff_reason = reason
        session.handoff_skill_group = self._resolve_skill_group(reason, business_context)
        session.handoff_priority = self._resolve_priority(reason, business_context)
        session.handoff_enqueued_at = session.handoff_enqueued_at or utcnow()
        session.assigned_operator_id = None
        for plugin in self._registry.resolve(
            PluginKind.HUMAN_HANDOFF,
            tenant_id=business_context.tenant_id,
            industry=business_context.industry,
            channel=business_context.channel,
        ):
            if not isinstance(plugin, HumanHandoffPlugin):
                continue
            package = await plugin.build_package(session, reason)
            if package is not None:
                return package
        return None

    def _resolve_skill_group(self, reason: str, business_context: BusinessContext) -> str:
        explicit = business_context.integration_context.get("skill_group")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        lowered = reason.lower()
        if business_context.industry == "ecommerce" and any(
            keyword in reason for keyword in ("退款", "售后", "退货")
        ):
            return "after_sales"
        if any(
            keyword in lowered for keyword in ("risk", "高风险", "投诉", "仲裁", "监管", "律师")
        ):
            return "risk"
        return business_context.industry or "general"

    def _resolve_priority(self, reason: str, business_context: BusinessContext) -> int:
        priority = 50
        lowered = reason.lower()
        if any(
            keyword in lowered for keyword in ("risk", "高风险", "投诉", "仲裁", "监管", "律师")
        ):
            priority = 90
        elif any(keyword in lowered for keyword in ("human", "人工", "转接")):
            priority = 80
        elif "confidence" in lowered or "置信" in reason:
            priority = 60
        behavior = business_context.behavior_signals
        if bool(behavior.get("frustrated")):
            priority += 10
        repeat_contact = behavior.get("repeat_contact_7d")
        if isinstance(repeat_contact, int) and repeat_contact >= 2:
            priority += 5
        return min(priority, 100)
