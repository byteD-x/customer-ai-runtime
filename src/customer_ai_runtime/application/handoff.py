from __future__ import annotations

from typing import Any

from customer_ai_runtime.application.plugins import (
    HumanHandoffPlugin,
    PluginRegistry,
    context_to_plugin_context,
)
from customer_ai_runtime.application.runtime import zh
from customer_ai_runtime.domain.models import (
    HandoffPackage,
    MessageRole,
    Session,
    SessionState,
    utcnow,
)
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
                return self._enrich_package(package, session, reason, business_context)
        return None

    def _enrich_package(
        self,
        package: HandoffPackage,
        session: Session,
        reason: str,
        business_context: BusinessContext,
    ) -> HandoffPackage:
        last_user_message = self._last_user_message(session)
        related_objects = self._merge_dicts(
            business_context.integration_context.get("business_objects"),
            business_context.business_objects,
        )
        page_context = self._merge_dicts(
            business_context.integration_context.get("page_context"),
            business_context.page_context,
        )
        behavior_signals = self._merge_dicts(
            business_context.integration_context.get("behavior_signals"),
            business_context.behavior_signals,
        )
        issue_summary = self._issue_summary(last_user_message, reason, related_objects)
        sentiment = self._sentiment(reason, behavior_signals)
        return package.model_copy(
            update={
                "last_user_message": package.last_user_message or last_user_message,
                "related_business_objects": package.related_business_objects or related_objects,
                "page_context": package.page_context or page_context,
                "behavior_signals": package.behavior_signals or behavior_signals,
                "issue_summary": package.issue_summary or issue_summary,
                "sentiment": package.sentiment if package.sentiment != "neutral" else sentiment,
                "recommended_reply": self._recommended_reply(sentiment)
                if sentiment != "neutral"
                else package.recommended_reply or self._recommended_reply(sentiment),
            }
        )

    def _last_user_message(self, session: Session) -> str:
        for message in reversed(session.messages):
            if message.role == MessageRole.USER:
                return message.content
        return ""

    def _merge_dicts(self, *values: object) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for value in values:
            if isinstance(value, dict):
                merged.update(value)
        return merged

    def _issue_summary(
        self,
        last_user_message: str,
        reason: str,
        related_objects: dict[str, Any],
    ) -> str:
        object_hint = ", ".join(
            f"{key}={value}" for key, value in sorted(related_objects.items()) if value
        )
        source = last_user_message or reason
        if len(source) > 120:
            source = f"{source[:117]}..."
        if object_hint:
            return f"{source} | related: {object_hint}"
        return source

    def _sentiment(self, reason: str, behavior_signals: dict[str, Any]) -> str:
        lowered = reason.lower()
        if bool(behavior_signals.get("frustrated")) or any(
            keyword in lowered for keyword in ("risk", "complaint", "refund", "lawyer", "urgent")
        ):
            return "negative"
        repeat_contact = behavior_signals.get("repeat_contact_7d")
        if isinstance(repeat_contact, int) and repeat_contact >= 2:
            return "concerned"
        return "neutral"

    def _recommended_reply(self, sentiment: str) -> str:
        if sentiment == "negative":
            return zh(
                "\\u5148\\u5b89\\u629a\\u7528\\u6237\\u60c5\\u7eea\\uff0c"
                "\\u786e\\u8ba4\\u95ee\\u9898\\u5bf9\\u8c61\\u548c\\u8bc9\\u6c42\\uff0c"
                "\\u518d\\u7ed9\\u51fa\\u53ef\\u6267\\u884c\\u5904\\u7406\\u65b9\\u6848\\u3002"
            )
        return zh(
            "\\u5148\\u786e\\u8ba4\\u7528\\u6237\\u8bc9\\u6c42\\uff0c"
            "\\u518d\\u57fa\\u4e8e\\u5f53\\u524d\\u6458\\u8981\\u7ee7\\u7eed\\u5904\\u7406\\u3002"
        )

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
