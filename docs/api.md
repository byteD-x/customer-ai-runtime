# API 文档

本文档描述当前本地参考实现已落地的主要接口契约；少量生产化增强会显式标注为 future target，不写成当前事实。

## 1. 基本约定

- Base URL: `http://127.0.0.1:8000`
- 内容类型：`application/json`
- 核心标识：`tenant_id`、`session_id`、`knowledge_base_id`

### 1.1 认证方式

任选其一：

- `X-API-Key: <key>`
- `Authorization: Bearer <jwt>`
- `Cookie: host_session=<session-id>`
- `X-Host-Token: <token>`

### 1.2 权限约定（当前实现）

- 以 `/api/v1/admin/*` 开头的读取型接口：`admin` / `operator`
- 以 `/api/v1/admin/*` 开头的写入型接口（`PUT`/部分 `POST`）：仅 `admin`
- 知识版本、切片优化等操作型管理接口即使是 `GET`，当前也要求 `admin`
- 会话人工协同（`claim-human`、`messages/human`、`close`）：仅 `admin`

### 1.3 通用响应

```json
{
  "request_id": "req_xxx",
  "data": {},
  "error": null
}
```

错误：

```json
{
  "request_id": "req_xxx",
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "tenant_id is required",
    "details": {}
  }
}
```

## 2. 健康检查

### `GET /healthz`

- 用途：服务健康检查

## 3. 认证与上下文接口

### `GET /api/v1/auth/context`

- 用途：查看当前请求解析出的认证上下文
- 返回重点：`auth_mode`、`tenant_ids`、`host_auth_context`

### `POST /api/v1/context/resolve`

- 用途：显式解析业务上下文

请求示例：

```json
{
  "tenant_id": "demo-tenant",
  "channel": "web",
  "session_id": null,
  "integration_context": {
    "industry": "ecommerce",
    "page_context": {
      "page_type": "order_detail",
      "order_id": "ORD-1001"
    },
    "business_objects": {
      "order_id": "ORD-1001"
    }
  }
}
```

## 4. 会话接口

### `POST /api/v1/sessions`

- 用途：创建会话

### `GET /api/v1/sessions/{session_id}`

- 用途：查询会话
- 返回重点：`last_route`、`last_intent`、`intent_stack`、`satisfaction_score`、`resolution_status`、`first_response_time`、`avg_response_time`

### `GET /api/v1/sessions/{session_id}/messages?tenant_id=demo-tenant`

- 用途：查询会话消息历史
- 返回重点：消息包含 `feedback_type`、`feedback_comment`、`feedback_submitted_at`

### `POST /api/v1/sessions/{session_id}/claim-human`

- 用途：人工接管会话
- 权限：`admin`

### `POST /api/v1/sessions/{session_id}/messages/human`

- 用途：人工写入回复
- 权限：`admin`

### `POST /api/v1/sessions/{session_id}/messages/{message_id}/feedback`

- 用途：提交消息级反馈
- 支持字段：`feedback_type`（`upvote` / `downvote` / `request_human`）
- 支持字段：`comment`（可选，最长 1000 字符）
- 返回重点：
  - `message`
  - `session`
  - `handoff`（仅 `request_human` 时返回）

### `POST /api/v1/sessions/{session_id}/close`

- 用途：关闭会话
- 支持字段：`satisfaction_score`（1-5，可选）
- 支持字段：`resolution_status`（`resolved` / `unresolved` / `escalated`，可选）
- 权限：`admin`

## 5. 文本客服接口

### `POST /api/v1/chat/messages`

- 用途：发起文本客服请求

请求示例：

```json
{
  "tenant_id": "demo-tenant",
  "session_id": null,
  "channel": "web",
  "message": "我的订单 ORD-1001 什么时候发货？",
  "knowledge_base_id": "kb_support",
  "integration_context": {
    "industry": "ecommerce",
    "page_context": {
      "page_type": "order_detail"
    },
    "business_objects": {
      "order_id": "ORD-1001"
    }
  }
}
```

响应重点字段：

- `session_id`
- `route`
- `industry`
- `confidence`
- `route_confidence`
- `route_confidence_band`
- `intent`
- `answer`
- `citations`
- `references`：由引用后处理生成的可展示引用列表，包含 `source` / `source_url` / `page` 等可选来源字段
- `hallucination_check`：知识型回复的启发式证据门禁结果，包含 `faithfulness_score`、`citation_count`、`effective_citation_count` 等字段
- `refusal` / `refusal_reason`：知识型回复缺少有效引用或证据重叠不足时返回，表示系统拒绝强答
- `tool_result`
- `handoff`
- `host_auth_context`
- `route_decision`
- `cache_hit`：是否命中知识问答安全缓存；业务查询不缓存
- `usage`：LLM token 用量，默认本地 provider 返回估算值
- `estimated_cost_cents`：按本地模型价格表估算的本轮成本，单位为美分
- `budget_status`：`ok` / `alert`
- `usage_source`：`estimated` / `provider`，区分本地估算用量与真实 provider usage
- `billing_currency`：当前本地估算默认 `USD`，可通过租户成本策略覆盖
- `billing_period`：当前本地口径默认 `per_request`，可通过租户成本策略覆盖
- `tenant_budget_estimated_cents`：当前策略中的本地预算告警阈值，可按租户覆盖，仍不是租户真实账单额度

`handoff` 为结构化交接包，当前重点字段包括：

- `reason`
- `summary`
- `issue_summary`
- `sentiment`
- `last_user_message`
- `related_business_objects`
- `page_context`
- `behavior_signals`
- `recommended_reply`

其中 `route_decision` 包含：

- `route`
- `confidence`
- `confidence_band`
- `intent`
- `tool_name`
- `reason`
- `matched_signals`

### `POST /api/v1/chat/messages/stream`

- 用途：发起文本客服流式请求
- 请求体：与 `POST /api/v1/chat/messages` 相同
- 响应类型：`application/x-ndjson`
- 当前实现：复用完整文本客服主链路，输出协议级流式事件；默认本地 `LLMProvider.generate_stream` 仍以完整回答作为单个 delta，真实 token 级增量输出依赖后续接入具备 streaming 能力的 provider。
- 安全边界：服务端会在幻觉门禁、转人工改写、引用后处理和脱敏完成后再释放最终可展示答案；若 provider 原始 delta 与最终答案不一致，则流式 delta 以最终安全答案为准。

事件示例：

```json
{"type":"delta","delta":"根据知识库内容，七天无理由退款...","done":true}
{"type":"final","data":{"session_id":"session_xxx","route":"knowledge","answer":"根据知识库内容，七天无理由退款...","citations":[]}}
```

错误事件示例：

```json
{"type":"error","error":{"code":"not_found","message":"知识库不存在","details":{},"status_code":404}}
```

### `POST /api/v1/chat/handoff`

- 用途：显式触发转人工

## 6. 知识库接口

### `POST /api/v1/knowledge-bases`

### `GET /api/v1/knowledge-bases?tenant_id=demo-tenant`

### `GET /api/v1/knowledge-bases/{knowledge_base_id}?tenant_id=demo-tenant`

- 返回重点：`active_version_id`、`version_count`、`chunk_max_tokens`、`chunk_overlap`

### `POST /api/v1/knowledge-bases/{knowledge_base_id}/documents`

### `POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/upload`

- 用途：上传文档文件并写入知识库，复用现有切片、版本和向量写入链路
- 请求类型：`multipart/form-data`
- 表单字段：
  - `tenant_id`
  - `file`
- 当前支持：UTF-8 文本、Markdown；PDF / Word 解析依赖可选 provider extra 中的 `pypdf` / `python-docx`
- 返回重点：`knowledge_base`、`document`、`chunks`

### `POST /api/v1/knowledge-bases/{knowledge_base_id}/search`

## 7. 业务工具接口

### `POST /api/v1/tools/business-query`

- 用途：显式执行业务工具

请求示例：

```json
{
  "tenant_id": "demo-tenant",
  "tool_name": "order_status",
  "parameters": {
    "order_id": "ORD-1001"
  },
  "integration_context": {
    "industry": "ecommerce"
  }
}
```

### `POST /api/v1/agents/tool-workflow`

- 用途：按受控步骤执行多工具工作流，例如“订单状态 -> 物流轨迹 -> 售后建议”
- 权限：`admin` / `operator`，面向运营排查、内部演示和受控自动化，不作为开放式自主 Agent
- 请求字段：
  - `tenant_id`
  - `session_id`（可选）
  - `channel`（默认 `web`）
  - `integration_context`（可选）
  - `steps`：有序工具步骤，每步包含 `tool_name`、`parameters`
  - `max_steps`：最大步骤数，防止无限循环
  - `allowed_tools`：允许调用的工具白名单
- 返回重点：
  - `plan`：按顺序列出本次工作流计划执行的工具名
  - `state`：`final` / `repair_required`
  - `final_answer`：最后一个已执行工具的摘要；失败停止时为失败摘要
  - `trace`：每步包含 `step_index`、`tool_name`、`phase`、`status`、`summary`、`error`、`observation`、`duration_ms`

## 8. 语音接口

### `POST /api/v1/voice/turn`

- 用途：发起语音轮次请求

请求示例：

```json
{
  "tenant_id": "demo-tenant",
  "session_id": null,
  "channel": "app_voice",
  "audio_base64": "base64-payload",
  "content_type": "text/plain",
  "knowledge_base_id": "kb_support",
  "integration_context": {
    "industry": "ecommerce"
  }
}
```

响应重点字段：

- `transcript`
- `asr_confidence`
- `audio_response_base64`
- `audio_format`

## 9. RTC 接口

### `POST /api/v1/rtc/rooms`

### `POST /api/v1/rtc/rooms/{room_id}/join`

### `POST /api/v1/rtc/rooms/{room_id}/interrupt`

### `POST /api/v1/rtc/rooms/{room_id}/end`

### `WS /ws/v1/rtc/{room_id}?tenant_id=demo-tenant&session_id=session_xxx`

客户端事件：

- `join`
- `user_audio`
- `interrupt`
- `request_human`
- `end`

服务端事件：

- `room_joined`
- `transcript`
- `assistant_message`
- `assistant_audio`
- `state_changed`
- `handoff`
- `ended`
- `error`

## 10. 插件管理接口

### `GET /api/v1/admin/plugins`

- 用途：查看插件列表、状态、优先级、作用域和能力

### `POST /api/v1/admin/plugins/{plugin_id}/enable`

- 用途：启用插件

### `POST /api/v1/admin/plugins/{plugin_id}/disable`

- 用途：禁用插件

## 11. 管理接口

### `GET /api/v1/admin/metrics`

### `GET /api/v1/admin/metrics/summary`

- 用途：返回指标计数、按路由聚合的统计、会话摘要、满意度摘要、诊断摘要和响应缓存摘要
- 可选查询参数：
  - `tenant_id`
- 返回重点：
  - `satisfaction_summary`
  - `resolution_summary`
  - `feedback_summary`
  - `response_time_summary`
  - `response_cache_summary`：单实例内存响应缓存运行时统计，包含 `enabled`、`ttl_seconds`、`size`、`hits`、`misses`、`writes`、`expired`、`clears`

### `GET /api/v1/admin/costs/summary`

- 用途：汇总当前诊断样本中的 LLM token、估算成本、导入 provider billing 样本金额、诊断样本成本差异、缓存命中和预算告警
- 权限：`admin` / `operator`
- 可选查询参数：
  - `tenant_id`
- 返回重点：
  - `sample_size`
  - `total_tokens`
  - `estimated_cost_cents`
  - `provider_billed_cost_cents`
  - `cost_reconciliation`
  - `cache_hits`
  - `cache_hit_rate`
  - `budget_alerts`
  - `provider_usage_records`
  - `provider_billing_records`
  - `usage_source_counts`
  - `cost_source_counts`
  - `billing_currency_counts`
  - `billing_period_counts`
  - `tenant_budget_estimated_cents`
  - `by_provider`
  - `by_route`

说明：该接口仍基于最近诊断事件聚合，`estimated_cost_cents` 是本地模型价格表估算；`provider_billed_cost_cents` 只统计通过 provider billing 导入接口写入的样本金额，不会混入估算成本；`cost_reconciliation.variance_cents = provider_billed_cost_cents - estimated_cost_cents`，`variance_ratio` 在估算成本为 0 时返回 `null`；`by_provider` 与 `by_route` 中同步返回 `cost_variance_cents` 和 `cost_variance_ratio`。这些字段只用于导入样本后的诊断对账观察，`billing_currency`、`billing_period` 与 `tenant_budget_estimated_cents` 支持策略配置和租户级覆盖。自动拉取 provider 真实账单、账单系统结算和线上节省比例仍属于 future target。

### `POST /api/v1/admin/costs/provider-billing-records`

- 用途：导入外部 provider billing 样本，写入 `provider.billing_recorded` 诊断事件，并参与成本摘要聚合
- 权限：`admin`
- 请求体：
  - `records[]`
    - `tenant_id`
    - `provider`
    - `billed_cost_cents`
    - `billing_currency`
    - `billing_period`
    - `model`（可选）
    - `route`（可选）
    - `session_id`（可选）
    - `total_tokens`（可选）
    - `external_record_id`（可选）
    - `usage_start` / `usage_end`（可选）
- 返回重点：
  - `imported_count`
  - `quality_issue_count`
  - `quality_issues`
  - `records`

说明：该接口用于把已取得的 provider billing 样本导入本地诊断账本，便于面试演示和本地治理验证。导入不会因为样本质量提示而阻断；`quality_issue_count` / `quality_issues` 只用于提示 usage 时间窗倒置、缺少归因维度、重复外部记录 ID、批次内币种或账期混杂等本地样本质量问题。它不是 provider 账单自动同步器，也不代表完整租户结算系统或真实成本节省。

### `GET /api/v1/admin/sessions?tenant_id=demo-tenant`

### `GET /api/v1/admin/handoff/queue`

- 用途：查看当前等待人工接管队列；默认 `local` 为单实例轻量队列，可选 `sqlite` 为共享队列表
- 权限：`admin` / `operator`
- 查询参数：
  - `tenant_id`
  - `skill_group`（可选）
- 排序规则：优先级倒序，同优先级按 `handoff_enqueued_at` 先后排序
- 入队来源：聊天自动转人工、`POST /api/v1/chat/handoff` 和 `request_human` 反馈均通过 `HandoffQueueBackend.enqueue` 写入队列；当前默认后端仍为 `local`，可通过 `CUSTOMER_AI_HANDOFF_QUEUE_BACKEND=sqlite` 启用 SQLite 共享队列表
- 返回重点：
  - `session_id`
  - `skill_group`
  - `priority`
  - `handoff_reason`
  - `enqueued_at`
  - `queue_wait_seconds`：基于 `handoff_enqueued_at` 计算的本地等待秒数，用于管理端观测
  - `assigned_operator_id`
  - `queue_backend`：当前默认 `local`；可选 `sqlite`
  - `atomic_claim`：当前默认 `true`；`local` 表示单进程锁内认领，`sqlite` 表示 SQLite 队列表事务认领
  - `consistency_scope`：当前默认 `single_process`；SQLite 后端返回 `shared_sqlite_queue`，用于明确一致性边界

### `POST /api/v1/admin/handoff/claim-next`

- 用途：按队列顺序认领下一条待人工接管会话
- 权限：`admin`
- 查询参数：
  - `tenant_id`
  - `skill_group`（可选）
  - `operator_id`（可选）
- 返回：认领后的队列项；无可认领会话时返回 `null`

### `GET /api/v1/admin/sessions/{session_id}/monitor?tenant_id=demo-tenant`

- 用途：查看单个会话的监控视图
- 返回重点：
  - `session`
  - `message_count`
  - `last_message`
  - `related_rooms`
  - `diagnostics`

### `GET /api/v1/admin/prompts`

- 用途：查看当前 Prompt 配置与版本历史
- 返回重点：
  - `prompts`
  - `prompt_versions`
  - `active_revision`

### `GET /api/v1/admin/prompts/revisions`

- 用途：查看 Prompt revision 只读治理摘要，不返回 Prompt 原文
- 权限：`admin` / `operator`
- 返回重点：
  - `active_revision`
  - `revision_count`
  - `revisions`
  - `issues`
- `revisions` 字段只包含 `version_id`、`revision`、`active`、`change_summary`、`created_at`、`prompt_lengths`、`prompt_hashes`
- `issues` 用于暴露空账本、损坏账本、active revision 不唯一、revision 重复等治理问题

### `GET /api/v1/admin/prompts/{revision}/diff`

- 用途：对比指定 Prompt revision 与基准 revision，默认基准为当前唯一 active revision
- 权限：`admin` / `operator`
- 可选查询参数：
  - `base_revision`：指定基准 revision；不传时使用当前唯一 active revision
- 返回重点：
  - `base_revision`
  - `target_revision`
  - `diff_available`
  - `changed_fields`
  - `field_diffs`
  - `issues`
- `field_diffs` 只返回字段名、是否变化、长度、`sha256_12` 和长度差，不返回 Prompt 原文
- 若 active revision 不唯一，默认 diff 会返回 `diff_available=false`，并在 `issues` 中说明原因

### `GET /api/v1/admin/runtime-config`

- 用途：查看运行时热配置快照
- 返回重点：
  - `prompts`
  - `policies`
  - `alerts`
  - `plugin_states`

### `PUT /api/v1/admin/runtime-config`

- 用途：一次性热更新运行时配置
- 支持更新：
  - `prompts`
  - `policies`
  - `alerts`
  - `plugin_states`

### `PUT /api/v1/admin/prompts`

- 用途：更新 Prompt 配置并记录新版本
- 支持字段：`knowledge_answer`、`business_answer`、`fallback_answer`、`change_summary`

### `POST /api/v1/admin/prompts/{revision}/rollback`

- 用途：将 Prompt 配置回滚到指定历史 revision，并生成一条新的激活版本记录
- 权限：`admin`
- 路径参数：
  - `revision`：目标历史版本号
- 请求字段：
  - `change_summary`（可选，默认记录为 rollback）
- 返回重点：
  - `prompts`
  - `prompt_versions`
  - `policies`
  - `alerts`
  - `plugin_states`

### `GET /api/v1/admin/policies`

### `PUT /api/v1/admin/policies`

路由增强相关策略字段：

- `route_fallback_confidence_threshold`
- `route_handoff_confidence_threshold`
- `intent_stack_max_depth`
- `intent_return_keywords`
- `response_cache_enabled`
- `response_cache_ttl_seconds`
- `cost_alert_estimated_cents`
- `billing_currency`
- `billing_period`
- `tenant_cost_policies`

### `GET /api/v1/admin/diagnostics`

可选查询参数：

- `tenant_id`
- `session_id`
- `room_id`
- `level`
- `code_prefix`
- `limit`

### `GET /api/v1/admin/rooms?tenant_id=demo-tenant`

### `GET /api/v1/admin/knowledge-bases/{knowledge_base_id}/health`

- 用途：查看单个知识库健康报告
- 可选查询参数：
  - `tenant_id`
- 返回重点：
  - `document_count`
  - `chunk_count`
  - `average_chunk_length`
  - `duplicate_chunk_ratio`
  - `empty_document_count`
  - `health_score`
  - `active_version_id`
  - `chunk_config`

### `GET /api/v1/admin/knowledge-bases/{knowledge_base_id}/versions`

- 用途：查看知识库版本列表
- 权限：`admin`
- 可选查询参数：
  - `tenant_id`
- 返回重点：
  - `version_id`
  - `status`
  - `source_version_id`
  - `document_count`
  - `chunk_count`
  - `chunk_config`
  - `created_at`

### `POST /api/v1/admin/knowledge-bases/{knowledge_base_id}/versions/snapshot`

- 用途：基于当前激活版本创建知识快照版本
- 请求字段：
  - `tenant_id`
  - `description`（可选）
  - `source_version_id`（可选，不传时基于当前激活版本）
- 返回重点：
  - `knowledge_base`
  - `version`

### `POST /api/v1/admin/knowledge-bases/{knowledge_base_id}/versions/{version_id}/activate`

- 用途：切换知识库激活版本
- 请求字段：
  - `tenant_id`
- 返回重点：
  - `knowledge_base`
  - `version`

### `GET /api/v1/admin/knowledge-bases/{knowledge_base_id}/chunk-optimization`

- 用途：查看当前知识库切片优化建议
- 权限：`admin`
- 可选查询参数：
  - `tenant_id`
- 返回重点：
  - `current_chunk_config`
  - `recommended_chunk_config`
  - `average_chunk_length`
  - `duplicate_chunk_ratio`
  - `oversized_chunk_ratio`
  - `undersized_chunk_ratio`

### `POST /api/v1/admin/knowledge-bases/{knowledge_base_id}/chunk-optimization/apply`

- 用途：按指定切片参数生成优化后的新版本，并切换为激活版本
- 请求字段：
  - `tenant_id`
  - `max_tokens`
  - `overlap`
  - `description`（可选）
  - `activate`（可选，默认 `true`）
- 返回重点：
  - `knowledge_base`
  - `version`
  - `document_count`
  - `chunk_count`

### `GET /api/v1/admin/knowledge/retrieval-misses`

- 用途：查看知识检索未命中聚合报告
- 可选查询参数：
  - `tenant_id`
  - `knowledge_base_id`
  - `limit`
- 返回重点：
  - `miss_count`
  - `top_queries`

### `GET /api/v1/admin/knowledge/effectiveness`

- 用途：按知识库汇总知识检索效果
- 可选查询参数：
  - `tenant_id`
  - `knowledge_base_id`
- 返回重点：
  - `query_count`
  - `effective_hit_count`
  - `miss_count`
  - `hit_rate`
  - `average_satisfaction`
  - `negative_feedback_rate`
  - `active_versions`
  - `recommendation`

### `GET /api/v1/admin/providers/health`

### `GET /api/v1/admin/alerts`

- 用途：查看需要关注的运维告警线索
- 可选查询参数：
  - `tenant_id`
- 告警规则来源：
  - `runtime-config.alerts.provider_not_ready_enabled`
  - `runtime-config.alerts.diagnostic_error_threshold`
  - `runtime-config.alerts.waiting_human_session_threshold`

### `GET /api/v1/admin/tools/catalog`

可选查询参数：

- `tenant_id`
- `industry`
- `channel`
- `include_disabled`

返回当前作用域下的工具目录元数据，包括：

- `name`
- `category`
- `description`
- `required_parameters`
- `optional_parameters`
- `input_schema`
- `output_schema`
- `timeout_ms`
- `retry_policy`
- `suggested_context_keys`
- `plugin_id`
- `version`
- `priority`
- `enabled`
- `available`
- `tenant_scopes`
- `industry_scopes`
- `channel_scopes`
- `capabilities`

### `GET /api/v1/admin/tools/catalog/categories`

可选查询参数与 `/api/v1/admin/tools/catalog` 一致：

- `tenant_id`
- `industry`
- `channel`
- `include_disabled`

返回按工具分类聚合后的目录摘要，包括：

- `category`
- `tool_count`
- `enabled_count`
- `tools`

## 12. 错误码

- `validation_error`
- `auth_error`
- `host_auth_error`
- `forbidden`
- `not_found`
- `provider_error`
- `policy_blocked`
- `handoff_required`
- `rtc_state_error`
- `plugin_error`

## 13. 接入建议

- 文本客服：`POST /api/v1/chat/messages`
- 语音客服：`POST /api/v1/voice/turn`
- RTC 通话：房间 API + RTC WebSocket
- 宿主挂载：优先用挂载模式并注册 `AuthBridgePlugin`
- 进程内接入：直接调用 facade，并显式传入 `integration_context`
