from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from time import time
from typing import Any

from customer_ai_runtime.core.diagnostics_export import DiagnosticsJsonlExporter
from customer_ai_runtime.core.errors import AppError
from customer_ai_runtime.core.redaction import sanitize_context
from customer_ai_runtime.core.request_context import get_request_id
from customer_ai_runtime.domain.models import (
    AlertRuleConfig,
    DiagnosticEvent,
    DiagnosticLevel,
    PolicyConfig,
    PromptConfig,
    PromptTemplateRecord,
)
from customer_ai_runtime.repositories.base import DiagnosticsRepository


def zh(text: str) -> str:
    return text.encode("utf-8").decode("unicode_escape")


class RuntimeConfigService:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._storage_path = _config_file(storage_root)
        self._prompts = PromptConfig(
            knowledge_answer=zh(
                "\\u4f60\\u662f\\u4f01\\u4e1a\\u5ba2\\u670d\\u77e5\\u8bc6\\u95ee\\u7b54\\u52a9\\u624b\\uff0c"
                "\\u56de\\u7b54\\u5fc5\\u987b\\u4f18\\u5148\\u57fa\\u4e8e\\u77e5\\u8bc6\\u5e93\\u5f15\\u7528\\u3002"
            ),
            business_answer=zh(
                "\\u4f60\\u662f\\u4e1a\\u52a1\\u67e5\\u8be2\\u5ba2\\u670d\\u52a9\\u624b\\uff0c"
                "\\u5fc5\\u987b\\u53ea\\u57fa\\u4e8e\\u4e1a\\u52a1\\u5de5\\u5177\\u7ed3\\u679c\\u56de\\u590d\\uff0c"
                "\\u4e0d\\u5f97\\u731c\\u6d4b\\u3002"
            ),
            fallback_answer=zh(
                "\\u4f60\\u662f\\u5ba2\\u670d\\u5206\\u6d41\\u52a9\\u624b\\uff0c"
                "\\u5728\\u4fe1\\u606f\\u4e0d\\u8db3\\u65f6\\u5f15\\u5bfc\\u7528\\u6237\\u8865\\u5145\\u6807\\u8bc6"
                "\\u6216\\u8f6c\\u4eba\\u5de5\\u3002"
            ),
            handoff_summary=zh(
                "\\u8bf7\\u751f\\u6210\\u7b80\\u660e\\u4f1a\\u8bdd\\u6458\\u8981\\u3001\\u7528\\u6237\\u610f\\u56fe"
                "\\u548c\\u4eba\\u5de5\\u63a5\\u624b\\u5efa\\u8bae\\u3002"
            ),
        )
        self._policies = PolicyConfig()
        self._alerts = AlertRuleConfig()
        self._prompt_history: list[PromptTemplateRecord] = []
        self._plugin_states: dict[str, bool] = {}
        self._response_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._response_cache_stats: Counter[str] = Counter()
        self._load()
        if not self._prompt_history:
            self._append_prompt_version("initial prompts", flush=False)

    def get_prompts(self) -> PromptConfig:
        return self._prompts.model_copy(deep=True)

    def update_prompts(self, data: dict[str, Any]) -> PromptConfig:
        prompt_fields = {
            key: value for key, value in data.items() if key in PromptConfig.model_fields
        }
        self._prompts = self._prompts.model_copy(update=prompt_fields)
        self._append_prompt_version(str(data.get("change_summary") or "prompt update"))
        self._flush()
        return self.get_prompts()

    def list_prompt_versions(self) -> list[PromptTemplateRecord]:
        return [record.model_copy(deep=True) for record in self._prompt_history]

    def rollback_prompts(
        self,
        revision: int,
        change_summary: str | None = None,
    ) -> PromptConfig:
        target = next(
            (record for record in self._prompt_history if record.revision == revision),
            None,
        )
        if target is None:
            raise AppError(
                code="not_found",
                message=f"Prompt revision {revision} 不存在。",
                status_code=404,
            )
        self._prompts = target.prompts.model_copy(deep=True)
        self._append_prompt_version(change_summary or f"rollback to revision {revision}")
        self._flush()
        return self.get_prompts()

    def get_policies(self) -> PolicyConfig:
        return self._policies.model_copy(deep=True)

    def update_policies(self, data: dict[str, Any]) -> PolicyConfig:
        self._policies = self._policies.model_copy(update=data)
        if (
            not self._policies.response_cache_enabled
            or self._policies.response_cache_ttl_seconds <= 0
        ):
            self._clear_response_cache()
        self._flush()
        return self.get_policies()

    def get_cached_response(self, cache_key: str) -> dict[str, Any] | None:
        policies = self._policies
        if not policies.response_cache_enabled or policies.response_cache_ttl_seconds <= 0:
            self._response_cache_stats["misses"] += 1
            return None
        cached = self._response_cache.get(cache_key)
        if cached is None:
            self._response_cache_stats["misses"] += 1
            return None
        created_at, payload = cached
        if time() - created_at > policies.response_cache_ttl_seconds:
            self._response_cache.pop(cache_key, None)
            self._response_cache_stats["misses"] += 1
            self._response_cache_stats["expired"] += 1
            return None
        self._response_cache_stats["hits"] += 1
        return json.loads(json.dumps(payload))

    def set_cached_response(self, cache_key: str, payload: dict[str, Any]) -> None:
        policies = self._policies
        if not policies.response_cache_enabled or policies.response_cache_ttl_seconds <= 0:
            return
        self._response_cache[cache_key] = (time(), json.loads(json.dumps(payload)))
        self._response_cache_stats["writes"] += 1

    def get_response_cache_summary(self) -> dict[str, Any]:
        policies = self._policies
        return {
            "enabled": policies.response_cache_enabled and policies.response_cache_ttl_seconds > 0,
            "ttl_seconds": policies.response_cache_ttl_seconds,
            "size": len(self._response_cache),
            "hits": self._response_cache_stats["hits"],
            "misses": self._response_cache_stats["misses"],
            "writes": self._response_cache_stats["writes"],
            "expired": self._response_cache_stats["expired"],
            "clears": self._response_cache_stats["clears"],
        }

    def get_plugin_states(self) -> dict[str, bool]:
        return dict(self._plugin_states)

    def set_plugin_state(self, plugin_id: str, enabled: bool) -> dict[str, bool]:
        self._plugin_states[plugin_id] = enabled
        self._flush()
        return self.get_plugin_states()

    def get_alert_rules(self) -> AlertRuleConfig:
        return self._alerts.model_copy(deep=True)

    def update_alert_rules(self, data: dict[str, Any]) -> AlertRuleConfig:
        self._alerts = self._alerts.model_copy(update=data)
        self._flush()
        return self.get_alert_rules()

    def snapshot(self) -> dict[str, Any]:
        return {
            "prompts": self.get_prompts().model_dump(mode="json"),
            "prompt_versions": [
                record.model_dump(mode="json") for record in self.list_prompt_versions()
            ],
            "policies": self.get_policies().model_dump(mode="json"),
            "alerts": self.get_alert_rules().model_dump(mode="json"),
            "plugin_states": self.get_plugin_states(),
        }

    def _load(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        if "prompts" in payload:
            self._prompts = PromptConfig.model_validate(payload["prompts"])
        if "prompt_versions" in payload and isinstance(payload["prompt_versions"], list):
            self._prompt_history = [
                PromptTemplateRecord.model_validate(item)
                for item in payload["prompt_versions"]
                if isinstance(item, dict)
            ]
        if not self._prompt_history:
            self._append_prompt_version("initial prompts", flush=False)
        if "policies" in payload:
            self._policies = PolicyConfig.model_validate(payload["policies"])
        if "alerts" in payload:
            self._alerts = AlertRuleConfig.model_validate(payload["alerts"])
        if "plugin_states" in payload:
            self._plugin_states = {
                str(key): bool(value) for key, value in payload["plugin_states"].items()
            }

    def _clear_response_cache(self) -> None:
        if self._response_cache:
            self._response_cache.clear()
            self._response_cache_stats["clears"] += 1

    def _flush(self) -> None:
        if not self._storage_path:
            return
        payload = {
            "prompts": self._prompts.model_dump(mode="json"),
            "prompt_versions": [record.model_dump(mode="json") for record in self._prompt_history],
            "policies": self._policies.model_dump(mode="json"),
            "alerts": self._alerts.model_dump(mode="json"),
            "plugin_states": self._plugin_states,
        }
        # Keep runtime config consistent with state JSON writes.
        # Use atomic replace to avoid partial writes.
        tmp_path = self._storage_path.with_name(f".{self._storage_path.name}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._storage_path)

    def _append_prompt_version(self, change_summary: str, *, flush: bool = True) -> None:
        for record in self._prompt_history:
            record.active = False
        revision = (
            1
            if not self._prompt_history
            else max(record.revision for record in self._prompt_history) + 1
        )
        self._prompt_history.append(
            PromptTemplateRecord(
                prompts=self._prompts.model_copy(deep=True),
                revision=revision,
                change_summary=change_summary,
            )
        )
        if flush:
            self._flush()


class MetricsService:
    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def snapshot(self) -> dict[str, int]:
        return dict(self._counters)


class DiagnosticsService:
    def __init__(
        self,
        repository: DiagnosticsRepository,
        exporter: DiagnosticsJsonlExporter | None = None,
    ) -> None:
        self._repository = repository
        self._exporter = exporter

    def record(
        self,
        level: DiagnosticLevel,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        sanitized = sanitize_context(context or {})
        request_id = get_request_id()
        if request_id:
            sanitized.setdefault("request_id", request_id)
        event = DiagnosticEvent(level=level, code=code, message=message, context=sanitized)
        self._repository.add(event)
        if self._exporter is not None:
            self._exporter.export(event.model_dump(mode="json"))

    def list_recent(self) -> list[DiagnosticEvent]:
        return self._repository.list_recent()

    def query(
        self,
        *,
        tenant_id: str | None = None,
        session_id: str | None = None,
        room_id: str | None = None,
        level: str | None = None,
        code_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[DiagnosticEvent]:
        events = self._repository.list_recent()
        filtered: list[DiagnosticEvent] = []
        normalized_level = None if level is None else level.lower()
        for event in events:
            context = event.context
            if tenant_id is not None and str(context.get("tenant_id")) != tenant_id:
                continue
            if session_id is not None and str(context.get("session_id")) != session_id:
                continue
            if room_id is not None and str(context.get("room_id")) != room_id:
                continue
            if normalized_level is not None and event.level.value != normalized_level:
                continue
            if code_prefix is not None and not event.code.startswith(code_prefix):
                continue
            filtered.append(event)
            if limit is not None and len(filtered) >= limit:
                break
        return filtered


def _config_file(storage_root: str | Path | None) -> Path | None:
    if not storage_root:
        return None
    root = Path(storage_root) / "state"
    root.mkdir(parents=True, exist_ok=True)
    return root / "runtime_config.json"
