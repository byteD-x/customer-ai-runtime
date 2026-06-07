# 模块设计

## 1. 模块总览

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| Session Service | 会话创建、恢复、状态流转 | `tenant_id`、`session_id`、消息 | `Session` |
| Route Orchestrator | 路由分类与策略编排 | 消息、上下文、行业 | `RouteDecision` |
| Knowledge Service | 知识库、切片、检索 | 文档、查询、知识域 | Chunk / Citation |
| Tool Service | 业务工具调度 | 工具名、参数、上下文 | `BusinessResult` |
| Voice Service | ASR + 文本链路 + TTS | 音频载荷 | 文本结果 + 音频结果 |
| RTC Service | 房间与通话状态机 | RTC 事件 | RTC 输出事件 |
| Handoff Service | 转人工策略与交接包 | 会话、原因、策略 | `HandoffPackage` |
| Cost Governance | LLM 用量、usage 来源、缓存命中与成本摘要 | Chat 响应、诊断事件 | `usage` / `cost_summary` |
| RAG Evaluation | 离线 RAG 标注样例与脱敏线上样本评测 | eval cases、chat results | `rag_eval_summary` / `online_rag_eval_summary` |
| Auth Service | API Key / Host Bridge 认证 | Header / Cookie / Token | `AuthContext` |
| Plugin Registry | 插件注册、发现、启停、优先级 | 插件元数据 | 可执行插件集合 |
| Business Context Builder | 合并宿主、页面、行为、会话上下文 | 请求与宿主上下文 | `BusinessContext` |
| Knowledge Domain Manager | 解析知识域与知识库选择 | 租户、行业、场景 | 域配置 |
| Response Enhancement Orchestrator | 回复后处理与结构化输出 | 原始回复、上下文 | 增强后回复 |

## 2. 领域对象

### 2.1 核心标识

- `tenant_id`
- `session_id`
- `knowledge_base_id`
- `room_id`
- `plugin_id`

### 2.2 关键模型

- `Session`
- `IntentFrame`
- `Message`
- `MessageFeedbackType`
- `RouteDecision`
- `KnowledgeBase`
- `KnowledgeVersion`
- `KnowledgeChunkConfig`
- `KnowledgeDocument`
- `KnowledgeChunk`
- `BusinessResult`
- `HandoffPackage`
- `LLMUsage`
- `CostRecord`
- `RTCRoom`
- `HostAuthContext`
- `BusinessContext`
- `PluginDescriptor`

## 3. 会话管理模块

### 输入

- `tenant_id`
- `session_id`
- `channel`
- `message`

### 输出

- 当前会话
- 消息历史
- 当前状态
- `last_route`
- `last_intent`
- `intent_stack`
- `satisfaction_score`
- `resolution_status`
- `first_response_time`
- `avg_response_time`
- 消息级 `feedback_type` / `feedback_comment` / `feedback_submitted_at`
- `handoff_reason`
- `handoff_skill_group`
- `handoff_priority`
- `handoff_enqueued_at`
- `assigned_operator_id`

### 状态机

- `active`
- `waiting_human`
- `human_in_service`
- `closed`

### 异常处理

- 缺失 `tenant_id` 返回 `validation_error`
- 非法 `session_id` 返回 `not_found`
- 越权访问返回 `forbidden`

## 4. 路由模块

### 输入

- 用户消息
- 行业类型
- 宿主上下文
- 历史摘要
- `page_context`
- `business_objects`
- `intent_stack`

### 输出

- `knowledge`
- `business`
- `handoff`
- `risk`
- `plugin`
- `fallback`
- `confidence`
- `confidence_band`
- `intent`
- `matched_signals`

### 扩展方式

- `RouteStrategyPlugin`
- 行业适配器可提供路由提示
- 风险插件可覆盖默认路由结果
- `Route Orchestrator` 会聚合插件候选结果，而不是只依赖单次命中
- 结合 `page_context`、`business_objects` 和 `intent_stack` 对候选路由做动态加权
- 当置信度低于 `route_fallback_confidence_threshold` 时进入澄清兜底
- 当低于 `route_handoff_confidence_threshold` 或连续低置信度时升级为转人工

## 5. RAG 模块

### 输入

- `tenant_id`
- `knowledge_base_id`
- `query`
- `top_k`
- `min_score`

### 输出

- 切片结果
- 检索命中
- 引用列表

### 扩展方式

- 向量库适配层
- 知识域管理器
- 不同行业可使用不同知识域组合
- `KnowledgeBase` 维护 `active_version_id`、`version_count`、默认切片参数 `chunk_max_tokens` / `chunk_overlap`
- `KnowledgeVersion` 维护版本状态、来源版本与版本级切片配置，文档、切片、引用都按 `version_id` 隔离
- `KnowledgeService` 额外提供知识库健康报告，用于输出文档数、切片数、重复切片率、空文档数、激活版本与切片配置
- `KnowledgeService` 支持知识版本快照、版本激活与基于统计结果的切片优化报告 / 应用
- 当检索后没有有效引用时，写入 `knowledge.retrieve_miss` 诊断事件，供管理端聚合知识缺口
- 当检索命中有效引用时，写入知识命中诊断与版本标记，用于后续知识库效果分析
- 知识问答在无宿主敏感上下文、存在引用、知识版本和 prompt hash 受控时可进入安全缓存
- `RetrievalService` 负责对检索结果做轻量 rerank，并把 `source`、`source_url`、`page` 和 `metadata` 透传到 `Citation`
- `HallucinationCheckService` 对知识型回复执行启发式证据门禁；缺少有效引用或证据重叠不足时返回拒答字段，避免无证据强答
- `scripts/eval_rag.py` 通过本地可复现 API 链路评估 route、引用关键词、上下文 precision/recall、有效命中阈值、标注集元数据、cohort、人工复核状态、`citation_accuracy`、`refusal_accuracy`、`faithfulness_score`、`offline_accuracy` 和失败明细
- `scripts/eval_online_rag.py` 读取脱敏 JSON/JSONL 样本，输出样本级 `online_accuracy`

## 6. 业务工具模块

### 输入

- 工具名
- 参数
- 行业
- 宿主身份
- 页面 / 业务对象上下文

### 输出

- 结构化业务结果
- 可向用户展示的摘要
- 是否建议转人工

### 扩展方式

- `BusinessToolPlugin`
- `BusinessAdapter`
- 行业适配器提供默认工具集合

## 7. 语音模块

### 输入

- `audio_base64`
- `content_type`
- `transcript_hint`

### 输出

- `transcript`
- `asr_confidence`
- `audio_response_base64`
- `audio_format`

### 状态

- 接收音频
- ASR 识别
- 文本链路处理
- TTS 输出

## 8. RTC 模块

### 输入事件

- `join`
- `user_audio`
- `interrupt`
- `request_human`
- `end`

### 输出事件

- `room_joined`
- `transcript`
- `assistant_message`
- `assistant_audio`
- `state_changed`
- `handoff`
- `ended`
- `error`

### 状态机

- `created`
- `joined`
- `listening`
- `thinking`
- `speaking`
- `waiting_human`
- `ended`

## 9. Auth Bridge 模块

### 输入

- Header
- Cookie
- Query
- 宿主票据

### 输出

- `HostAuthContext`
- 平台访问角色
- 宿主身份与权限映射结果

### 支持模式

- API Key
- Session / Cookie
- JWT / Bearer
- Custom Token
- 自定义桥接插件

### 失败策略

- 未认证返回 `auth_error`
- 租户不匹配返回 `forbidden`
- 宿主票据解析失败返回 `host_auth_error`

## 10. 插件系统模块

### 核心抽象

- `Plugin`
- `PluginRegistry`
- `PluginContext`
- `RouteStrategyPlugin`
- `BusinessToolPlugin`
- `HumanHandoffPlugin`
- `IndustryAdapterPlugin`
- `AuthBridgePlugin`
- `ContextEnricherPlugin`
- `ResponsePostProcessorPlugin`

### 生命周期

- 注册
- 启用
- 禁用
- 卸载
- 启动
- 关闭

### 插件执行原则

- 按优先级排序
- 支持租户、行业、渠道装配
- 插件失败时回退到默认实现

## 11. 业务增强模块

### Business Context Builder

- 合并宿主身份、页面上下文、业务对象、用户画像、最近行为、会话摘要、`intent_stack`

### Knowledge Domain Manager

- 维护 `tenant_id + industry + scenario -> knowledge domains`
- 管理端可基于知识域对应的知识库查看健康报告、版本列表、切片优化建议、检索失败聚合与效果分析

### Real-time Business Data Provider

- 通过工具插件或业务适配器读取动态数据

### Response Enhancement Orchestrator

- 回复格式化
- 引用附加
- 脱敏
- 多语言
- 结构化输出

## 12. 成本治理模块

### 输入

- LLM provider 返回或本地估算的 `LLMUsage`
- route、provider、channel、session、cache_hit
- 本地模型价格表配置
- `PolicyConfig.cost_alert_estimated_cents`、`billing_currency`、`billing_period` 与 `tenant_cost_policies`

### 输出

- Chat 响应字段：`usage`、`cache_hit`、`estimated_cost_cents`、`budget_status`、`usage_source`、`billing_currency`、`billing_period`、`tenant_budget_estimated_cents`
- 诊断事件：`chat.cost_recorded`，包含 provider、model、route、usage、usage 来源、币种、账期、本地预算阈值和估算成本
- 管理端聚合：`GET /api/v1/admin/costs/summary`，按 provider / route 汇总 token、估算成本、缓存命中、provider usage 记录数、usage 来源、币种和账期；`GET /api/v1/admin/metrics/summary` 输出单实例 `response_cache_summary`

### 设计取舍

- 本地 provider 默认估算 token，并按本地模型价格表估算成本，用于演示治理链路；预算阈值、币种和账期支持全局策略与租户级覆盖；真实 provider 可优先使用 SDK usage，但真实账单仍属于 future target。
- 知识问答缓存命中时 usage 归零，便于观察缓存节省的请求。
- 业务工具查询不缓存，避免实时订单、物流、售后状态过期。

## 13. 管理模块

### 管理对象

- Prompt
- Policy
- Metrics
- Diagnostics
- Knowledge health report
- Retrieval miss report
- Cost summary
- Handoff queue
- RAG eval scripts
- External readiness scripts
- k6 smoke template
- Plugin 状态
- Provider 健康状态

### Prompt 治理

- `GET /api/v1/admin/prompts` 保留当前 Prompt 配置与完整版本历史视图，用于兼容现有管理端读取。
- `GET /api/v1/admin/prompts/revisions` 输出只读 revision 摘要，仅包含版本元数据、Prompt 字段长度和 `sha256_12`，不返回 Prompt 原文。
- `GET /api/v1/admin/prompts/{revision}/diff` 默认对比当前唯一 active revision 与目标 revision；也可通过 `base_revision` 指定基准。
- Prompt diff 只返回字段级变化、长度、hash 和长度差，避免把系统提示词或运营提示词原文扩散到审计接口。
- Prompt revision `issues` 会暴露空账本、损坏账本、active revision 不唯一、revision 重复等治理风险，便于面试演示“可审计、可回滚、可诊断”的 Prompt 管理闭环。

### 当前统计摘要

- `satisfaction_summary`
- `resolution_summary`
- `feedback_summary`
- `response_time_summary`
- `response_cache_summary`
- `cost_summary`
- `handoff_queue`

### 失败方式

- 非管理员返回 `forbidden`
- 配置校验失败返回 `validation_error`

## 14. 与 Future Target 的边界

- 当前交付以单体参考实现为主。
- 文档中的多服务拆分、独立控制台等属于 future target，不宣称当前仓库已落地。
- 当前人工接管队列已通过 `HandoffQueueBackend.enqueue` 接口化并由容器统一注入；默认 `local` 后端基于 `Session` 做单进程锁内认领，`queue_backend=local`、`consistency_scope=single_process` 明确该边界；可选 `sqlite` 后端使用 `<storage_root>/state/handoff_queue.sqlite3` 做共享队列表事务认领，返回 `queue_backend=sqlite`、`consistency_scope=shared_sqlite_queue`。该 SQLite 后端只覆盖队列层，不代表当前 JSON Session 仓储具备完整多实例强一致；Redis sorted set / Postgres 行级锁队列仍属于 future target。
- 当前 RAG eval 是本地标注样例评测，包含 cohort、人工复核状态、引用准确率、上下文 precision/recall、拒答准确率、faithfulness 分数和 `offline_accuracy`；online eval 只代表输入样本，不代表全量线上准确率。
- 当前成本治理是本地模型价格表估算，并显式暴露 usage 来源、可配置币种、可配置账期和可配置本地预算阈值，不代表真实 provider 账单或线上节省比例。
