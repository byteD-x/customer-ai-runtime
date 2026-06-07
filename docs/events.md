# 诊断事件与埋点约定（当前事实）

本仓库通过 `DiagnosticsService` 记录诊断事件，并可通过管理接口查询：

- `GET /api/v1/admin/diagnostics`（需要 `admin` 权限）

## 1. 通用字段

每条事件包含：

- `event_id`：事件唯一标识
- `level`：`info` / `warning` / `error`
- `code`：事件码（稳定标识）
- `message`：事件描述（面向排障）
- `created_at`：UTC 时间
- `context`：结构化上下文（默认会做脱敏与截断）

`context` 中常见字段：

- `tenant_id`
- `session_id`
- `room_id`
- `channel`
- `request_id`（若来自 HTTP 请求）

## 2. 已落地的核心事件码（示例）

以下为当前代码中已出现的事件码集合（非穷尽），用于对接运营看板/排障流程时的稳定参考：

- `chat.route_decided`：路由决策完成
- `chat.tool_executed`：业务工具已执行
- `chat.knowledge_retrieved`：知识检索完成（包含 `effective_hit`）
- `knowledge.retrieve_miss`：知识检索未命中有效引用（warning）
- `chat.cost_recorded`：LLM usage、缓存命中、估算成本与预算状态已记录
- `provider.billing_recorded`：外部 provider billing 样本已导入，用于成本摘要按独立口径聚合并计算诊断样本差异
- `chat.handoff_required`：需要转人工（warning）
- `chat.completed`：一次聊天请求完成（包含 `duration_ms`）
- `voice.turn_completed`：一次语音轮次完成（包含 `duration_ms`）
- `rtc.room_created` / `rtc.room_joined` / `rtc.audio_processed`
- `session.satisfaction_recorded` / `session.resolution_recorded`
- `message.feedback_recorded` / `message.feedback_request_human`

## 3. 成本治理事件字段

`chat.cost_recorded` 的 `context` 当前包含：

- `tenant_id`
- `session_id`
- `provider`
- `model`
- `route`
- `channel`
- `cache_hit`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `usage_estimated`
- `usage_source`
- `estimated_cost_cents`
- `budget_status`
- `billing_currency`
- `billing_period`
- `tenant_budget_estimated_cents`

`provider.billing_recorded` 的 `context` 当前包含：

- `tenant_id`
- `session_id`
- `provider`
- `model`
- `route`
- `total_tokens`
- `usage_source=provider_billing`
- `cost_source=provider_billing`
- `estimated_cost_cents=0.0`
- `provider_billed_cost_cents`
- `billing_currency`
- `billing_period`
- `external_record_id`
- `usage_start`
- `usage_end`

这些字段用于 `GET /api/v1/admin/costs/summary` 聚合。`usage_source=provider` 表示上游 SDK 已返回原生 usage，`usage_source=estimated` 表示运行时本地估算，`usage_source=provider_billing` 表示导入的 provider billing 样本；`estimated_cost_cents` 当前按本地模型价格表与 usage 估算，`provider_billed_cost_cents` 只统计导入账单样本金额。摘要中的 `cost_reconciliation.variance_cents` 以及 provider / route bucket 的 `cost_variance_cents` 统一按“导入账单样本金额 - 本地估算金额”计算，只用于诊断样本对账；当本地估算成本为 0 时，差异比例返回 `null`。`billing_currency`、`billing_period` 和 `tenant_budget_estimated_cents` 默认来自全局策略，也可通过 `tenant_cost_policies` 做租户级覆盖。provider billing 样本导入接口返回的 `quality_issue_count` / `quality_issues` 是接口层的非阻断样本质量诊断，不写入 `provider.billing_recorded` 事件 context，也不影响已导入样本参与本地成本摘要聚合。自动拉取 provider 真实账单与完整账单系统结算仍属于 future target。`total_tokens` 等数值字段不会被按敏感 token 误脱敏；真实密钥、Cookie、JWT 等仍按脱敏规则处理。

## 4. 注意事项

- 诊断事件默认会对自由文本做截断/脱敏，不保证保留原文。
- 事件属于“诊断面”而非实时音频热路径；RTC 热路径中的事件以 WebSocket 消息为主。
- RAG eval 脚本主要消费 Chat API 返回值，不依赖诊断事件作为唯一依据。

## 5. 导出（当前实现）

可选配置 `CUSTOMER_AI_DIAGNOSTICS_EXPORT_PATH`（相对路径会落在 `storage_root` 下），启用后会把每条诊断事件以 JSON Lines 方式追加写入该文件，便于外部采集器摄取。
