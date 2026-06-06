from __future__ import annotations

import hashlib
import json
from time import perf_counter
from typing import Any

from customer_ai_runtime.application.business import (
    BusinessContextBuilder,
    KnowledgeDomainManager,
    ResponseEnhancementOrchestrator,
)
from customer_ai_runtime.application.handoff import HandoffService
from customer_ai_runtime.application.knowledge import KnowledgeService
from customer_ai_runtime.application.rag_quality import HallucinationCheckService
from customer_ai_runtime.application.routing import RoutingService
from customer_ai_runtime.application.runtime import (
    DiagnosticsService,
    MetricsService,
    RuntimeConfigService,
    zh,
)
from customer_ai_runtime.application.session import SessionService
from customer_ai_runtime.application.tooling import ToolService
from customer_ai_runtime.domain.models import (
    BusinessResult,
    DiagnosticLevel,
    LLMRequest,
    LLMUsage,
    MessageRole,
    RouteType,
)
from customer_ai_runtime.domain.platform import HostAuthContext
from customer_ai_runtime.providers.base import LLMProvider


class ChatService:
    def __init__(
        self,
        session_service: SessionService,
        knowledge_service: KnowledgeService,
        routing_service: RoutingService,
        runtime_config: RuntimeConfigService,
        business_context_builder: BusinessContextBuilder,
        knowledge_domain_manager: KnowledgeDomainManager,
        llm_provider: LLMProvider,
        tool_service: ToolService,
        handoff_service: HandoffService,
        response_enhancer: ResponseEnhancementOrchestrator,
        metrics: MetricsService,
        diagnostics: DiagnosticsService,
        model_price_map: dict[str, dict[str, float]] | None = None,
        default_input_cost_per_1k_cents: float = 0.1,
        default_output_cost_per_1k_cents: float = 0.1,
        llm_model_name: str | None = None,
        hallucination_checker: HallucinationCheckService | None = None,
    ) -> None:
        self.session_service = session_service
        self.knowledge_service = knowledge_service
        self.routing_service = routing_service
        self.runtime_config = runtime_config
        self.business_context_builder = business_context_builder
        self.knowledge_domain_manager = knowledge_domain_manager
        self.llm_provider = llm_provider
        self.tool_service = tool_service
        self.handoff_service = handoff_service
        self.response_enhancer = response_enhancer
        self.metrics = metrics
        self.diagnostics = diagnostics
        self.model_price_map = model_price_map or {}
        self.default_input_cost_per_1k_cents = default_input_cost_per_1k_cents
        self.default_output_cost_per_1k_cents = default_output_cost_per_1k_cents
        self.llm_model_name = llm_model_name
        self.hallucination_checker = hallucination_checker or HallucinationCheckService()

    async def process_message(
        self,
        tenant_id: str,
        session_id: str | None,
        channel: str,
        message: str,
        knowledge_base_id: str | None,
        integration_context: dict | None = None,
        host_auth_context: HostAuthContext | None = None,
        track_response_timing: bool = True,
    ) -> dict:
        started_at = perf_counter() if track_response_timing else None
        session = self.session_service.get_or_create(tenant_id, session_id, channel)
        self.session_service.add_message(session, MessageRole.USER, message)
        business_context = await self.business_context_builder.build(
            tenant_id=tenant_id,
            channel=channel,
            session=session,
            integration_context=integration_context,
            host_auth_context=host_auth_context,
            user_message=message,
        )
        route_decision = await self.routing_service.decide(message, business_context)
        business_context = self.routing_service.apply_context_snapshot(
            business_context, route_decision
        )
        self.diagnostics.record(
            DiagnosticLevel.INFO,
            "chat.route_decided",
            "chat route decision completed",
            {
                "tenant_id": tenant_id,
                "session_id": session.session_id,
                "route": route_decision.route.value,
                "intent": route_decision.intent,
                "route_confidence": route_decision.confidence,
                "confidence_band": route_decision.confidence_band,
                "channel": channel,
                "industry": business_context.industry,
            },
        )
        self.session_service.record_route_decision(
            session,
            route_decision,
            message,
            max_depth=self.runtime_config.get_policies().intent_stack_max_depth,
        )
        prompts = self.runtime_config.get_prompts()
        policies = self.runtime_config.get_policies()
        citations = []
        tool_result: BusinessResult | None = None
        knowledge_version_id: str | None = None
        effective_hit_count = 0
        retrieval_latency_ms: float | None = None
        tool_latency_ms: float | None = None
        llm_latency_ms: float | None = None

        if route_decision.route == RouteType.BUSINESS and route_decision.tool_name:
            parameters = self.routing_service.extract_tool_parameters(
                route_decision.tool_name, message
            )
            tool_started_at = perf_counter()
            tool_result = await self.tool_service.execute(
                business_context=business_context,
                tool_name=route_decision.tool_name,
                parameters=parameters,
            )
            tool_latency_ms = round((perf_counter() - tool_started_at) * 1000, 3)
            self.diagnostics.record(
                DiagnosticLevel.INFO,
                "chat.tool_executed",
                "business tool executed",
                {
                    "tenant_id": tenant_id,
                    "session_id": session.session_id,
                    "tool_name": route_decision.tool_name,
                    "status": tool_result.status,
                    "latency_ms": tool_latency_ms,
                },
            )
        elif route_decision.route == RouteType.KNOWLEDGE:
            knowledge_base_id = self.knowledge_domain_manager.resolve_primary(
                tenant_id=tenant_id,
                industry=business_context.industry,
                explicit=knowledge_base_id,
            )
            if knowledge_base_id:
                retrieval_started_at = perf_counter()
                citations = await self.knowledge_service.retrieve(
                    tenant_id=tenant_id,
                    knowledge_base_id=knowledge_base_id,
                    query=message,
                    top_k=policies.knowledge_top_k,
                )
                retrieval_latency_ms = round((perf_counter() - retrieval_started_at) * 1000, 3)
                knowledge_version_id = citations[0].version_id if citations else None
                filtered_citations = [
                    citation
                    for citation in citations
                    if citation.score >= policies.knowledge_min_score
                ]
                effective_hit_count = len(filtered_citations)
                if not filtered_citations:
                    top_score = None if not citations else round(citations[0].score, 4)
                    self.diagnostics.record(
                        DiagnosticLevel.WARNING,
                        "knowledge.retrieve_miss",
                        "knowledge retrieval missed effective citations",
                        {
                            "tenant_id": tenant_id,
                            "session_id": session.session_id,
                            "channel": channel,
                            "knowledge_base_id": knowledge_base_id,
                            "knowledge_version_id": knowledge_version_id,
                            "query": message,
                            "top_score": top_score,
                            "latency_ms": retrieval_latency_ms,
                        },
                    )
                citations = filtered_citations or citations[:1]
                knowledge_version_id = (
                    citations[0].version_id if citations else knowledge_version_id
                )
                self.diagnostics.record(
                    DiagnosticLevel.INFO,
                    "chat.knowledge_retrieved",
                    "knowledge retrieval completed",
                    {
                        "tenant_id": tenant_id,
                        "session_id": session.session_id,
                        "knowledge_base_id": knowledge_base_id,
                        "knowledge_version_id": knowledge_version_id,
                        "returned_hit_count": len(citations),
                        "effective_hit_count": effective_hit_count,
                        "effective_hit": effective_hit_count > 0,
                        "latency_ms": retrieval_latency_ms,
                    },
                )

        prompt_template = prompts.fallback_answer
        if route_decision.route == RouteType.KNOWLEDGE:
            prompt_template = prompts.knowledge_answer
        elif route_decision.route == RouteType.BUSINESS:
            prompt_template = prompts.business_answer
        selected_model = self._select_model(route_decision.route, message)
        model_route = {
            "strategy": "static_route",
            "route": route_decision.route.value,
            "selected_model": selected_model,
            "provider": self.runtime_config_provider_name(),
        }

        cache_key = self._build_response_cache_key(
            tenant_id=tenant_id,
            message=message,
            route=route_decision.route,
            knowledge_base_id=knowledge_base_id,
            knowledge_version_id=knowledge_version_id,
            selected_model=selected_model,
            prompt_template=prompt_template,
            citations=[citation.model_dump(mode="json") for citation in citations],
            host_auth_context=host_auth_context,
        )
        cached_response = (
            None if cache_key is None else self.runtime_config.get_cached_response(cache_key)
        )
        cache_hit = cached_response is not None
        if cache_hit:
            response_payload = dict(cached_response or {})
            response_payload["session_id"] = session.session_id
            response_payload["state"] = session.state.value
            response_payload["host_auth_context"] = (
                None if host_auth_context is None else host_auth_context.model_dump(mode="json")
            )
            response_payload["cache_hit"] = True
            response_payload["usage"] = LLMUsage().model_dump(mode="json")
            response_payload["latency_ms"] = self._latency_payload(
                retrieval_latency_ms=retrieval_latency_ms,
                tool_latency_ms=tool_latency_ms,
                llm_latency_ms=0.0,
            )
            response_payload["model_route"] = model_route
            response_payload["selected_model"] = selected_model
            self.metrics.increment("llm_cache_hits")
        else:
            llm_started_at = perf_counter()
            llm_response = await self.llm_provider.generate(
                LLMRequest(
                    tenant_id=tenant_id,
                    session_id=session.session_id,
                    route=route_decision.route,
                    user_message=message,
                    history=session.messages,
                    citations=citations,
                    tool_result=tool_result,
                    prompt_template=prompt_template,
                    business_context=business_context.model_dump(mode="json"),
                    model=selected_model,
                )
            )
            llm_latency_ms = round((perf_counter() - llm_started_at) * 1000, 3)
            usage = llm_response.usage or self._estimate_usage(
                prompt_template,
                message,
                llm_response.answer,
                " ".join(item.content for item in session.messages[-6:]),
            )

            response_payload = {
                "session_id": session.session_id,
                "state": session.state.value,
                "route": route_decision.route.value,
                "confidence": round(llm_response.confidence, 4),
                "route_confidence": round(route_decision.confidence, 4),
                "route_confidence_band": route_decision.confidence_band,
                "intent": route_decision.intent,
                "answer": llm_response.answer,
                "citations": [
                    citation.model_dump(mode="json") for citation in llm_response.citations
                ],
                "tool_result": None if tool_result is None else tool_result.model_dump(mode="json"),
                "handoff": None,
                "industry": business_context.industry,
                "host_auth_context": None
                if host_auth_context is None
                else host_auth_context.model_dump(mode="json"),
                "requires_handoff": route_decision.requires_handoff,
                "reason": route_decision.reason,
                "route_decision": {
                    "route": route_decision.route.value,
                    "confidence": round(route_decision.confidence, 4),
                    "confidence_band": route_decision.confidence_band,
                    "intent": route_decision.intent,
                    "tool_name": route_decision.tool_name,
                    "reason": route_decision.reason,
                    "matched_signals": list(route_decision.matched_signals),
                },
                "cache_hit": False,
                "usage": usage.model_dump(mode="json"),
                "latency_ms": self._latency_payload(
                    retrieval_latency_ms=retrieval_latency_ms,
                    tool_latency_ms=tool_latency_ms,
                    llm_latency_ms=llm_latency_ms,
                ),
                "model_route": model_route,
                "selected_model": selected_model,
            }
            if route_decision.route == RouteType.KNOWLEDGE:
                hallucination_check = self.hallucination_checker.check(
                    answer=llm_response.answer,
                    citations=llm_response.citations,
                    effective_hit_count=effective_hit_count,
                )
                response_payload["hallucination_check"] = hallucination_check.model_dump(
                    mode="json"
                )
                if hallucination_check.refusal:
                    response_payload["answer"] = self.hallucination_checker.refusal_answer()
                    response_payload["confidence"] = min(response_payload["confidence"], 0.35)
                    response_payload["citations"] = []
                    response_payload["refusal"] = True
                    response_payload["refusal_reason"] = hallucination_check.reason
                    self.diagnostics.record(
                        DiagnosticLevel.WARNING,
                        "rag.hallucination_check_failed",
                        "knowledge answer blocked by evidence gate",
                        {
                            "tenant_id": tenant_id,
                            "session_id": session.session_id,
                            "knowledge_base_id": knowledge_base_id,
                            "knowledge_version_id": knowledge_version_id,
                            "reason": hallucination_check.reason,
                            "faithfulness_score": hallucination_check.faithfulness_score,
                            "citation_count": hallucination_check.citation_count,
                            "effective_citation_count": (
                                hallucination_check.effective_citation_count
                            ),
                        },
                    )
                else:
                    response_payload["refusal"] = False

            should_handoff, handoff_reason = await self.handoff_service.should_handoff(
                business_context=business_context,
                route=route_decision.route.value,
                response=response_payload,
            )
            if should_handoff:
                handoff_package = await self.handoff_service.create_package(
                    session,
                    handoff_reason or route_decision.reason,
                    business_context,
                )
                response_payload["handoff"] = (
                    None if handoff_package is None else handoff_package.model_dump(mode="json")
                )
                response_payload["answer"] = zh(
                    "\\u5f53\\u524d\\u95ee\\u9898\\u5efa\\u8bae\\u7531\\u4eba\\u5de5\\u5ba2\\u670d"
                    "\\u7ee7\\u7eed\\u5904\\u7406\\uff0c\\u6211\\u5df2\\u6574\\u7406\\u4e0a\\u4e0b"
                    "\\u6587\\u5e76\\u53d1\\u8d77\\u8f6c\\u63a5\\u3002"
                )
                response_payload["confidence"] = max(response_payload["confidence"], 0.92)
                response_payload["state"] = session.state.value
                self.metrics.increment("handoff_count")
                self.diagnostics.record(
                    DiagnosticLevel.WARNING,
                    "chat.handoff_required",
                    "session routed to human handoff",
                    {
                        "tenant_id": tenant_id,
                        "session_id": session.session_id,
                        "route": route_decision.route.value,
                        "reason": handoff_reason,
                    },
                )

            response_payload = await self.response_enhancer.enhance(
                response_payload, business_context
            )
            response_payload["cache_hit"] = False
            response_payload["usage"] = usage.model_dump(mode="json")
            if (
                cache_key is not None
                and route_decision.route == RouteType.KNOWLEDGE
                and response_payload.get("handoff") is None
                and not response_payload.get("refusal")
            ):
                self.runtime_config.set_cached_response(cache_key, response_payload)

        usage_payload = response_payload.get("usage")
        usage = LLMUsage.model_validate(usage_payload or {})
        provider = self.runtime_config_provider_name()
        estimated_cost_cents = self._estimated_cost_cents(
            usage,
            provider=provider,
            model=selected_model,
        )
        budget_status = (
            "alert" if estimated_cost_cents >= policies.cost_alert_estimated_cents else "ok"
        )
        usage_source = "estimated" if usage.estimated else "provider"
        billing_currency = "USD"
        billing_period = "per_request"
        response_payload["estimated_cost_cents"] = estimated_cost_cents
        response_payload["budget_status"] = budget_status
        response_payload["usage_source"] = usage_source
        response_payload["billing_currency"] = billing_currency
        response_payload["billing_period"] = billing_period
        response_payload["tenant_budget_estimated_cents"] = policies.cost_alert_estimated_cents
        self._record_cost(
            tenant_id=tenant_id,
            session_id=session.session_id,
            route=route_decision.route,
            channel=channel,
            provider=provider,
            usage=usage,
            cache_hit=cache_hit,
            model=selected_model,
            estimated_cost_cents=estimated_cost_cents,
            budget_status=budget_status,
            usage_source=usage_source,
            billing_currency=billing_currency,
            billing_period=billing_period,
            tenant_budget_estimated_cents=policies.cost_alert_estimated_cents,
        )
        self.session_service.add_message(
            session,
            MessageRole.ASSISTANT,
            response_payload["answer"],
            metadata={
                "route": route_decision.route.value,
                "industry": business_context.industry,
                "intent": route_decision.intent,
                "route_confidence_band": route_decision.confidence_band,
                "knowledge_base_id": knowledge_base_id
                if route_decision.route == RouteType.KNOWLEDGE
                else None,
                "knowledge_version_id": knowledge_version_id,
                "knowledge_effective_hit": effective_hit_count > 0
                if route_decision.route == RouteType.KNOWLEDGE
                else None,
                "cache_hit": cache_hit,
                "estimated_cost_cents": estimated_cost_cents,
                "usage_source": usage_source,
                "selected_model": selected_model,
            },
        )
        duration_ms: int | None = None
        if started_at is not None:
            duration_ms = max(1, int((perf_counter() - started_at) * 1000))
            self.session_service.record_response_timing(session, duration_ms)
        self.session_service.save(session)
        self.metrics.increment("chat_requests")
        self.metrics.increment(f"route_{route_decision.route.value}")
        self.diagnostics.record(
            DiagnosticLevel.INFO,
            "chat.completed",
            "chat request completed",
            {
                "tenant_id": tenant_id,
                "session_id": session.session_id,
                "route": route_decision.route.value,
                "confidence": response_payload["confidence"],
                "industry": business_context.industry,
                "channel": channel,
                "duration_ms": duration_ms,
                "model": selected_model,
                "latency_ms": response_payload.get("latency_ms"),
            },
        )
        response_payload.pop("requires_handoff", None)
        response_payload.pop("reason", None)
        return response_payload

    def _build_response_cache_key(
        self,
        *,
        tenant_id: str,
        message: str,
        route: RouteType,
        knowledge_base_id: str | None,
        knowledge_version_id: str | None,
        selected_model: str | None,
        prompt_template: str,
        citations: list[dict[str, Any]],
        host_auth_context: HostAuthContext | None,
    ) -> str | None:
        if route != RouteType.KNOWLEDGE or host_auth_context is not None or not citations:
            return None
        citation_keys = [
            {
                "knowledge_base_id": citation.get("knowledge_base_id"),
                "version_id": citation.get("version_id"),
                "document_id": citation.get("document_id"),
                "chunk_id": citation.get("chunk_id"),
            }
            for citation in citations
        ]
        payload = {
            "tenant_id": tenant_id,
            "query": " ".join(message.lower().split()),
            "knowledge_base_id": knowledge_base_id,
            "knowledge_version_id": knowledge_version_id,
            "selected_model": selected_model,
            "prompt_hash": hashlib.sha256(prompt_template.encode("utf-8")).hexdigest()[:12],
            "citations": citation_keys,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _select_model(self, route: RouteType, message: str) -> str | None:
        return self.llm_model_name

    def _latency_payload(
        self,
        *,
        retrieval_latency_ms: float | None,
        tool_latency_ms: float | None,
        llm_latency_ms: float | None,
    ) -> dict[str, float | None]:
        return {
            "retrieval_ms": retrieval_latency_ms,
            "tool_ms": tool_latency_ms,
            "llm_ms": llm_latency_ms,
        }

    def _estimate_usage(self, *texts: str) -> LLMUsage:
        input_tokens = max(1, sum(max(1, len(text or "") // 2) for text in texts if text))
        output_tokens = max(16, min(256, input_tokens // 3))
        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated=True,
        )

    def _estimated_cost_cents(
        self,
        usage: LLMUsage,
        *,
        provider: str,
        model: str | None,
    ) -> float:
        if usage.input_tokens <= 0 and usage.output_tokens <= 0 and usage.total_tokens <= 0:
            return 0.0
        price = self._resolve_model_price(provider, model)
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        if input_tokens <= 0 and output_tokens <= 0:
            input_tokens = usage.total_tokens
        input_cost = input_tokens * price["input_per_1k_cents"] / 1000
        output_cost = output_tokens * price["output_per_1k_cents"] / 1000
        return round(input_cost + output_cost, 6)

    def _resolve_model_price(self, provider: str, model: str | None) -> dict[str, float]:
        candidates = []
        if model:
            candidates.append(f"{provider}:{model}")
            candidates.append(model)
        candidates.extend([provider, "default"])
        for candidate in candidates:
            price = self.model_price_map.get(candidate)
            if price:
                return price
        return {
            "input_per_1k_cents": self.default_input_cost_per_1k_cents,
            "output_per_1k_cents": self.default_output_cost_per_1k_cents,
        }

    def _record_cost(
        self,
        *,
        tenant_id: str,
        session_id: str,
        route: RouteType,
        channel: str,
        provider: str,
        usage: LLMUsage,
        cache_hit: bool,
        model: str | None,
        estimated_cost_cents: float,
        budget_status: str,
        usage_source: str,
        billing_currency: str,
        billing_period: str,
        tenant_budget_estimated_cents: float,
    ) -> None:
        self.diagnostics.record(
            DiagnosticLevel.INFO,
            "chat.cost_recorded",
            "chat cost and usage recorded",
            {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "route": route.value,
                "channel": channel,
                "cache_hit": cache_hit,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "usage_estimated": usage.estimated,
                "usage_source": usage_source,
                "estimated_cost_cents": estimated_cost_cents,
                "budget_status": budget_status,
                "billing_currency": billing_currency,
                "billing_period": billing_period,
                "tenant_budget_estimated_cents": tenant_budget_estimated_cents,
            },
        )

    def runtime_config_provider_name(self) -> str:
        provider_class = self.llm_provider.__class__.__name__.lower()
        if provider_class.startswith("local"):
            return "local"
        if provider_class.startswith("openai"):
            return "openai"
        return provider_class.removesuffix("provider")
