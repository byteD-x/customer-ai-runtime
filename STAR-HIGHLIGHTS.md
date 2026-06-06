# Customer AI Runtime - 项目亮点与技术难点 (STAR)

## 项目概述

**Customer AI Runtime** 是一个面向真实业务场景的企业级智能客服能力平台，支持文本、语音、RTC 实时通话三种接入模式，可插件化、可行业增强、可宿主系统挂载。

**技术栈**: Python 3.13+, FastAPI, Pydantic v2, OpenAI SDK, Qdrant/Pinecone/Milvus, gRPC, GraphQL, HTTP, WebSocket, Docker

---

## 本轮新增可验证亮点（面试强化）

### 亮点 A: 低成本 AI 客服治理闭环

**Situation (背景)**
AI 客服在真实业务中不能只关注“能回答”，还需要回答成本、缓存、实时数据正确性和预算风险，否则高频 FAQ 会浪费模型调用，实时订单查询又可能被错误缓存。

**Task (任务)**
在不引入重型数据库或付费依赖的前提下，为本地 runtime 增加可演示、可测试的成本治理能力。

**Action (行动)**
- 新增 `LLMUsage` / `CostRecord` 模型，文本响应返回 `usage`、`cache_hit`、`estimated_cost_cents`、`budget_status`。
- 在 `ChatService` 中只缓存知识问答，cache key 绑定 tenant、query、知识库版本、prompt hash 和引用片段；业务查询明确不缓存。
- 在 `AdminService` 中新增成本摘要聚合，按 provider 和 route 输出 token、成本和缓存命中。

**Result (结果)**
本地可通过 `test_chat_cost_summary_and_knowledge_cache` 验证首次知识问答不命中缓存、重复知识问答命中缓存、业务查询不缓存、成本摘要可聚合。线上真实节省比例需要实际流量与账单数据补充。

**证据**
`src/customer_ai_runtime/application/chat.py`、`src/customer_ai_runtime/application/admin.py`、`tests/test_runtime_api.py`

### 亮点 B: RAG 质量评测闭环

**Situation (背景)**
RAG 项目常见问题是只展示一条成功问答，却无法解释错误路由、引用缺失和低分召回是否应该算命中。

**Task (任务)**
新增本地可复现 eval，用小样本 case 证明评测机制，而不是虚构线上准确率。

**Action (行动)**
- 新增 `evaluate_rag_results`，评估 route、引用关键词、有效命中阈值和失败明细。
- 新增 `examples/rag_eval_cases.json` 和 `scripts/eval_rag.py`，通过 TestClient 调真实 API 路径完成评测。
- 用测试覆盖引用关键词失败明细，确保 eval 不只是 happy path。

**Result (结果)**
`scripts/eval_rag.py` 本地输出 `rag_eval_summary`，当前样例 3 个 case 可复现通过；该结果只代表本地 eval cases，不代表线上准确率。

**证据**
`src/customer_ai_runtime/evaluation.py`、`examples/rag_eval_cases.json`、`scripts/eval_rag.py`、`tests/test_interview_artifacts.py`

### 亮点 C: 人工接管队列与面试演示闭环

**Situation (背景)**
客服系统不能只返回“已转人工”，还需要让运营侧知道谁在排队、按什么优先级、由哪个客服认领。

**Task (任务)**
在单实例本地 runtime 中实现轻量队列，支持风险优先、技能组过滤和认领，并提供一键演示脚本。

**Action (行动)**
- 在 `Session` 上新增 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
- 管理端新增 queue 和 claim-next 接口，认领后会话进入 `human_in_service`。
- 新增 `examples/interview_demo.py`，串起知识问答、缓存、业务工具、风险转人工、队列认领、成本摘要和 RAG eval。

**Result (结果)**
本地 demo 可输出 `route`、`citations`、`tool_result`、`handoff_queue`、`claimed_session`、`cost_summary`、`rag_eval_summary`；多实例原子认领仍是 future target，可迁移到 Redis sorted set 或数据库事务。

**证据**
`src/customer_ai_runtime/application/handoff.py`、`src/customer_ai_runtime/application/admin.py`、`examples/interview_demo.py`、`tests/test_runtime_api.py`

---

## 一、核心亮点

### 亮点 1: 多模态客服引擎架构

**Situation (背景)**
传统客服系统通常只能处理单一渠道（文本或语音），且语音和 RTC 实时通话链路复杂，需要状态机、打断、超时和音频流处理。企业需要统一的客服平台同时支持文本、语音轮次、RTC 实时通话，且不同渠道需要共享同一套路由、知识和业务增强逻辑。

**Task (任务)**
设计并实现统一的多模态客服引擎，要求：
- 三种渠道（文本/语音/RTC）共享核心路由和业务逻辑
- 语音链路需要集成 ASR 和 TTS 提供商
- RTC 链路需要 WebSocket 实时状态机和事件驱动
- 实时语音热路径不能通过事件总线（避免延迟）
- 支持多提供商切换（阿里云、腾讯云、OpenAI 等）

**Action (行动)**
- 设计分层架构：渠道接入层 → 宿主桥接层 → 核心引擎层 → 业务增强层 → 插件平台层 → 提供商适配层
- 实现 `VoiceService` 统一处理语音轮次：ASR 转写 → 文本链路 → TTS 合成
- 实现 `RTCService` 处理实时通话：建房/入房 → WebSocket 音频事件 → RTC 状态机 → 实时响应
- 提供商抽象层支持 `ASRProvider` / `TTSProvider` 接口，已落地本地、OpenAI、阿里云、腾讯云四种实现
- RTC 状态机直接处理热路径，不经过事件总线，确保低延迟

**Result (结果)**
- ✅ 三种渠道共享同一套路由策略、业务工具和知识检索逻辑
- ✅ 语音提供商可插拔切换，配置驱动
- ✅ RTC 实时通话支持打断、超时和状态流转
- ✅ 端到端语音轮次响应时间可追踪（`duration_ms` 诊断事件）
- 📊 性能口径：分位数统计（p50/p95）基于最近诊断样本，用于快速排障

**证据文件**:
- [`src/customer_ai_runtime/application/voice_rtc.py`](src/customer_ai_runtime/application/voice_rtc.py)
- [`src/customer_ai_runtime/providers/aliyun_provider.py`](src/customer_ai_runtime/providers/aliyun_provider.py)
- [`src/customer_ai_runtime/providers/tencent_provider.py`](src/customer_ai_runtime/providers/tencent_provider.py)
- [`docs/architecture.md`](docs/architecture.md)

---

### 亮点 2: 插件化架构设计

**Situation (背景)**
客服平台的路由策略、业务工具、行业适配、鉴权桥接、上下文增强、回复后处理等能力需要长期演进，不同租户和行业需求差异大。如果把这些逻辑写死在主流程中，会导致版本耦合、租户冲突和维护困难。

**Task (任务)**
设计并实现完整的插件系统，要求：
- 支持 7 种插件类型：路由策略、业务工具、人工协同、行业适配、鉴权桥接、上下文增强、回复后处理
- 插件可注册、可启停、可替换、可优先级排序
- 支持多租户和行业范围隔离
- 插件失败不能拖垮主流程
- 插件状态可持久化，服务重启后恢复

**Action (行动)**
- 定义 `Plugin` 抽象基类和 `PluginDescriptor` 元数据模型
- 实现 `PluginRegistry` 管理插件生命周期（register/startup/resolve/execute/shutdown/unregister）
- 7 种插件扩展点全部落地并接入主流程
- 插件按 `priority` 从高到低执行，同类插件支持多租户/行业覆盖
- 插件状态持久化到运行时配置 JSON，服务重启后自动恢复启用/禁用状态
- FastAPI 生命周期内自动调用插件 `startup/shutdown` 钩子

**Result (结果)**
- ✅ 完整插件平台落地，7 种扩展点全部可用
- ✅ 插件元数据包含：plugin_id、name、version、kind、priority、enabled、tenant_scopes、industry_scopes、channel_scopes、capabilities
- ✅ 插件状态持久化，重启后恢复
- ✅ 任意插件失败时记录诊断并回退，不拖垮主流程
- 📊 已内置多个示例插件：`HostHeaderBridge`、`OrderStatusTool`、行业适配器等

**证据文件**:
- [`src/customer_ai_runtime/application/plugins.py`](src/customer_ai_runtime/application/plugins.py)
- [`docs/plugin-system.md`](docs/plugin-system.md)
- [`examples/host_custom_auth_bridge.py`](examples/host_custom_auth_bridge.py)
- [`examples/business_tool_plugin_example.py`](examples/business_tool_plugin_example.py)

---

### 亮点 3: 智能路由增强策略

**Situation (背景)**
传统 RAG 客服只能处理静态知识命中问题，无法识别实时业务查询、高风险场景、人工请求等复杂情况。且低置信度时强答会导致用户体验差，需要分层决策和意图追踪。

**Task (任务)**
实现智能路由系统，要求：
- 支持知识型、业务型、人工型、高风险型、插件型路由
- 路由决策输出置信度分层（high/medium/low）和置信度分数
- 支持 `intent_stack` 多轮意图追踪，识别用户回退和主题切换
- 支持 `page_context` 和 `business_objects` 场景感知加权
- 低置信度时优先澄清，连续低置信度或挫败信号时转人工

**Action (行动)**
- 实现 `RoutingService` 聚合插件候选结果，结合页面上下文、业务对象和 `intent_stack` 做动态加权
- 路由决策输出：`route`、`confidence`、`confidence_band`、`intent`、`tool_name`、`reason`、`matched_signals`
- `SessionService` 维护 `intent_stack`（最大深度 6），记录主题切换与回退历史
- 热配置支持：`route_fallback_confidence_threshold`、`route_handoff_confidence_threshold`、`intent_stack_max_depth`、`intent_return_keywords`
- 识别"这个"、"刚才那个"等指代词，延续上一轮业务工具上下文

**Result (结果)**
- ✅ 路由置信度分层，避免低置信度强答
- ✅ `intent_stack` 支持多轮追踪，用户说"返回上一个问题"时可回退
- ✅ 页面上下文感知：在订单详情页问"这个到哪了"自动识别为物流查询
- ✅ 连续低置信度或挫败信号时自动升级转人工
- 📊 路由决策全链路可诊断，匹配信号和原因可追溯

**证据文件**:
- [`src/customer_ai_runtime/application/routing.py`](src/customer_ai_runtime/application/routing.py)
- [`src/customer_ai_runtime/application/session.py`](src/customer_ai_runtime/application/session.py)
- [`tests/test_routing_enhancements.py`](tests/test_routing_enhancements.py)

---

### 亮点 4: 宿主系统挂载与鉴权桥接

**Situation (背景)**
企业已有业务系统（电商、SaaS、CRM 等）通常有自己的登录态（Cookie/Session/JWT/SSO），不愿重建统一 API Key 体系。客服平台需要复用宿主身份体系，而不是强制改造。

**Task (任务)**
实现宿主桥接能力，要求：
- 支持 API Key、Session/Cookie、JWT/Bearer、Custom Token 多种认证模式
- 宿主可注册自定义 `AuthBridgePlugin` 实现任意鉴权逻辑
- 客服平台复用宿主登录态和租户/权限上下文
- 支持独立部署和 FastAPI 子应用挂载两种模式
- 日志中不得输出完整票据、Cookie、JWT 原文

**Action (行动)**
- 定义 `AuthBridgePlugin` 抽象：`can_handle` + `authenticate` 两步
- 认证顺序：X-API-Key 优先 → 按优先级尝试已启用桥接器 → 产出统一 `HostAuthContext`
- `HostAuthContext` 包含：tenant_id、principal_id、roles、permissions、source_system、auth_mode、session_claims、business_scope
- 实现 `CustomerAIRuntimeModule` 支持 FastAPI 子应用挂载
- 提供示例：`HostHeaderBridge` 从自定义 Header 解析身份

**Result (结果)**
- ✅ 5 种认证模式落地：API Key、Session、JWT、Custom Token、Custom Bridge
- ✅ 宿主可注册任意桥接器（SSO 票据换票、内部鉴权接口 introspection、网关换票等）
- ✅ 支持子应用挂载和进程内 facade 调用
- ✅ 敏感信息脱敏，不输出原文
- 📊 已测试：API Key 流、JWT 流、自定义 Header 桥接流

**证据文件**:
- [`src/customer_ai_runtime/application/auth.py`](src/customer_ai_runtime/application/auth.py)
- [`docs/auth-bridge.md`](docs/auth-bridge.md)
- [`examples/host_custom_auth_bridge.py`](examples/host_custom_auth_bridge.py)
- [`tests/test_runtime_api.py`](tests/test_runtime_api.py)

---

### 亮点 5: 业务增强与行业适配器

**Situation (背景)**
单纯 RAG 只能处理静态知识，无法处理订单状态、物流轨迹、工单进度等实时业务数据。且不同行业（电商、SaaS、教育、物流、CRM）的话术、规则和数据结构差异大。

**Task (任务)**
实现业务增强能力，要求：
- 区分四类信息：通用静态知识、行业静态知识、实时业务数据、当前会话与页面上下文
- 支持 5 种内置行业：电商、SaaS、教育、物流、CRM
- 实时业务数据通过业务工具插件或业务适配器查询
- 行业规则不写死在主流程，通过适配器与插件声明

**Action (行动)**
- 设计联合增强流程：IndustryAdapter → BusinessContextBuilder → RouteStrategy → Knowledge/Business → ResponseEnhancement
- 5 种行业适配器内置：ecommerce（订单/物流/售后）、saas（账号/订阅/工单）、education（课程/进度）、logistics（运单/异常）、crm（客户档案/服务记录）
- 业务工具插件支持实时 API 查询（HTTP/gRPC/GraphQL）
- `BusinessContext` 统一模型包含：page_context、business_objects、user_profile、behavior_signals、session_summary、intent_stack

**Result (结果)**
- ✅ 四类信息分离处理，实时数据不写入知识库
- ✅ 5 种行业适配器落地，支持自定义行业
- ✅ 业务工具插件支持 HTTP/gRPC/GraphQL 三种协议
- ✅ 页面上下文和业务对象注入，路由决策可感知场景
- 📊 示例：订单详情页问"这个到哪了"自动调用物流查询工具

**证据文件**:
- [`docs/business-enhancement.md`](docs/business-enhancement.md)
- [`src/customer_ai_runtime/application/business.py`](src/customer_ai_runtime/application/business.py)
- [`src/customer_ai_runtime/providers/http_business_provider.py`](src/customer_ai_runtime/providers/http_business_provider.py)
- [`src/customer_ai_runtime/providers/graphql_business_provider.py`](src/customer_ai_runtime/providers/graphql_business_provider.py)

---

### 亮点 6: 运营管理闭环

**Situation (背景)**
客服平台上线后需要持续优化：Prompt/Policy 需要热配置、会话需要监控、问题需要诊断、知识需要评估效果、满意度需要采集反馈。

**Task (任务)**
实现运营管理能力，要求：
- Prompt/Policy 热配置，支持运行时更新
- 会话级响应时效追踪（首响、平均响应）
- 质量反馈闭环（满意度评分、解决状态）
- 用户反馈采集（点赞/点踩/转人工）
- 知识库健康巡检与检索失败分析
- 诊断事件记录与导出

**Action (行动)**
- 实现 `RuntimeConfigService` 管理 Prompt/Policy/Plugin 状态，持久化到 JSON
- `SessionService` 记录 `first_response_time`、`avg_response_time`、`satisfaction_score`、`resolution_status`
- 消息级支持点赞、点踩、转人工反馈，转人工直接生成交接包
- 管理端汇总：平均分、分布、解决状态统计、响应时效分渠道汇总
- 知识库健康巡检：文档数、切片数、平均切片长度、重复切片率、空文档数、健康分
- 检索失败分析：记录未命中查询、最高分、渠道，输出 Top 缺口问题
- 诊断事件结构化记录，支持 JSONL 导出

**Result (结果)**
- ✅ Prompt/Policy 可热更新，无需重启
- ✅ 会话级响应时效全追踪
- ✅ 满意度与解决状态闭环
- ✅ 知识库效果可量化（命中率、有效命中率、满意度、负反馈率）
- ✅ 自动切片优化建议（推荐 chunk_max_tokens / chunk_overlap）
- 📊 管理端接口：`GET /api/v1/admin/metrics/summary`

**证据文件**:
- [`src/customer_ai_runtime/application/runtime.py`](src/customer_ai_runtime/application/runtime.py)
- [`src/customer_ai_runtime/application/session.py`](src/customer_ai_runtime/application/session.py)
- [`src/customer_ai_runtime/core/diagnostics_export.py`](src/customer_ai_runtime/core/diagnostics_export.py)
- [`docs/slo.md`](docs/slo.md)

---

### 亮点 7: 企业级工程规范

**Situation (背景)**
企业级平台需要严格的工程质量保障：类型安全、代码规范、测试覆盖、本地质量门禁、安全控制、日志脱敏、限流熔断等。

**Task (任务)**
建立工程规范，要求：
- 类型安全（mypy 严格模式）
- 代码规范（ruff check/format）
- 测试覆盖（pytest + asyncio）
- 本地质量门禁脚本
- 安全控制（敏感信息脱敏、限流、租户隔离）
- 结构化日志（structlog）

**Action (行动)**
- `pyproject.toml` 配置完整：build-system、dependencies、optional-dependencies、pytest、ruff、mypy
- `scripts/test.ps1` 串联 lint → format check → compileall → mypy → pytest
- 核心依赖：FastAPI、Pydantic v2、httpx、openai、qdrant-client、structlog、tenacity、opentelemetry
- 实现 `TokenBucketRateLimiter` 支持租户级限流
- 实现 `sanitize_context` 脱敏函数，日志不输出敏感字段原文
- 统一错误模型 `AppError`，结构化响应

**Result (结果)**
- ✅ 本地质量门禁脚本覆盖代码规范、类型检查和测试
- ✅ 类型安全：mypy 严格模式（warn_unused_ignores、warn_redundant_casts、no_implicit_optional）
- ✅ 代码规范：ruff 自动格式化
- ✅ 测试覆盖：9 个测试文件，覆盖运行时 API、路由增强、响应增强、速率限制、Prompt 脱敏、RAG eval 与面试 demo 等
- ✅ 限流熔断：租户级 Token Bucket，支持 burst 和 TTL
- ✅ 安全脱敏：日志自动脱敏

**证据文件**:
- [`pyproject.toml`](pyproject.toml)
- [`scripts/test.ps1`](scripts/test.ps1)
- [`src/customer_ai_runtime/core/rate_limit.py`](src/customer_ai_runtime/core/rate_limit.py)
- [`src/customer_ai_runtime/core/redaction.py`](src/customer_ai_runtime/core/redaction.py)
- [`src/customer_ai_runtime/core/errors.py`](src/customer_ai_runtime/core/errors.py)

---

## 二、技术难点与解决方案

### 难点 1: 多模态渠道统一路由

**问题**
文本、语音、RTC 三种渠道输入形式完全不同（HTTP 请求/音频流/WebSocket 事件），但需要共享同一套路由决策逻辑。且语音和 RTC 对延迟敏感，不能在热路径上增加过多开销。

**解决方案**
- 抽象统一 `BusinessContext` 模型，三种渠道都映射到同一模型
- `RoutingService.decide()` 只依赖 `BusinessContext`，不感知渠道差异
- 语音链路：`VoiceService.process_turn()` 先 ASR 转文本，再调用 `ChatService.process_message()`
- RTC 链路：`RTCService` 直接处理 WebSocket 事件，状态机内部调用语音服务
- 性能敏感路径不使用事件总线，直接函数调用

**效果**
- ✅ 三种渠道共享路由、业务工具和知识检索主链路
- ✅ 语音轮次端到端延迟可控（ASR + 文本 + TTS）
- ✅ RTC 实时通话支持打断和超时

---

### 难点 2: 意图栈多轮追踪

**问题**
用户多轮对话中会频繁切换主题和回退（"返回上一个问题"、"还是那个订单"），需要追踪历史意图并支持回退。且同一意图连续出现时需要合并，避免栈溢出。

**解决方案**
- `Session.intent_stack` 维护最近 6 个意图帧
- `IntentFrame` 包含：intent、route、tool_name、confidence、confidence_band、low_confidence_count、matched_signals、context_snapshot、last_user_message
- 相同意图合并：更新 `low_confidence_count`，不新增帧
- 回退识别：命中 `intent_return_keywords` 时返回上一个意图
- 上下文快照合并：回退时合并历史快照与当前快照

**效果**
- ✅ 支持用户说"返回上一个问题"准确回退
- ✅ 同一意图连续追问时栈不膨胀
- ✅ 低置信度连续出现时自动升级转人工

---

### 难点 3: 插件失败隔离

**问题**
插件是外部扩展代码，可能抛出异常、超时或返回错误结果。如果插件失败拖垮主流程，会导致整个服务不可用。

**解决方案**
- 插件执行包裹 try-except，失败时记录诊断事件并回退
- 路由插件：失败时降级为 fallback 路由
- 业务工具插件：失败时返回错误结果，不阻断回复生成
- 鉴权桥接插件：失败时尝试下一个桥接器
- 所有插件失败都记录 `DiagnosticEvent`，包含 level、code、message、context

**效果**
- ✅ 任意插件失败不拖垮主流程
- ✅ 失败可诊断，日志可追溯
- ✅ 降级策略保证服务可用性

---

### 难点 4: 宿主鉴权桥接通用性

**问题**
不同宿主的鉴权方式千差万别（Cookie、JWT、SSO 票据、网关换票、双向签名），平台无法预知所有场景。如何设计通用桥接接口？

**解决方案**
- `AuthBridgePlugin` 两步抽象：
  1. `can_handle(request_data)`：判断是否能处理当前请求
  2. `authenticate(request_data)`：解析并返回 `ResolvedAuthContext`
- 桥接器按优先级依次尝试，首个成功者胜出
- `AuthRequestContext` 包含完整请求信息：method、path、headers、cookies、query_params、body
- `ResolvedAuthContext` 统一输出：role、tenant_ids、auth_mode、host_auth_context

**效果**
- ✅ 宿主可注册任意桥接逻辑（示例：Header 桥接、JWT 桥接）
- ✅ 桥接器可测试、可替换
- ✅ 平台不感知具体桥接实现

---

### 难点 5: 知识库效果量化

**问题**
知识库上线后效果如何？哪些问题是检索失败的？如何给出优化建议？传统做法靠人工抽检，效率低且无法量化。

**解决方案**
- 检索失败分析：记录未命中查询、最高分、渠道
- 管理端聚合：按知识库汇总 Top 缺口问题
- 自动切片优化：基于当前切片统计（文档数、切片数、平均长度、重复率）给出推荐 `chunk_max_tokens` / `chunk_overlap`
- 知识版本管理：支持版本快照、激活切换与回滚
- 效果指标：命中率、有效命中率、满意度、负反馈率

**效果**
- ✅ 检索失败可量化、可聚合
- ✅ 自动给出切片优化建议
- ✅ 知识库效果可追踪（满意度、负反馈率）

---

### 难点 6: 成本治理与实时正确性的冲突

**问题**
高频 FAQ 如果每次都调用 LLM，成本不可控；但订单、物流、售后等实时业务查询如果缓存，会返回过期状态。统一缓存策略会在“成本”和“正确性”之间制造冲突。

**解决方案**
- 新增 `LLMUsage` 与成本诊断字段，文本响应返回 `usage`、`cache_hit`、`estimated_cost_cents`、`budget_status`
- 只缓存知识问答，cache key 绑定 tenant、query、知识库、激活版本、prompt hash 和引用片段
- 宿主身份上下文存在时不缓存，避免用户级敏感答案串用
- 业务工具查询明确不缓存，继续走实时业务工具
- 管理端提供 `GET /api/v1/admin/costs/summary`，按 provider 和 route 聚合

**效果**
- ✅ 本地测试覆盖首次知识问答不命中、重复知识问答命中、业务查询不缓存
- ✅ 管理端可看到 token、估算成本、缓存命中率和预算告警
- ⚠️ 真实成本节省比例需要线上账单与流量数据补充

---

### 难点 7: RAG 评测不能把“有引用”当“答对”

**问题**
RAG demo 容易只展示成功样例；本地检索兜底也可能返回低分引用。如果只看 citation 数量，会把低质量召回误判为有效命中。

**解决方案**
- 新增 `evaluate_rag_results`，统一评估 route、引用关键词、有效命中阈值
- eval case 支持 `expect_effective_hit=false`，专门验证低分未命中
- 输出 `missing_keywords`、`route_ok`、`effective_hit_ok` 等失败明细
- `scripts/eval_rag.py` 通过 TestClient 调真实 API 链路，避免只测纯函数

**效果**
- ✅ 本地 `scripts/eval_rag.py` 可复现输出 `rag_eval_summary`
- ✅ 测试覆盖引用关键词失败明细
- ⚠️ 当前 eval 只代表本地小样本，不宣称线上准确率

---

### 难点 8: 人工接管要从“提示语”升级为可运营队列

**问题**
只返回“已转人工”无法支撑客服运营：主管需要知道哪些会话在等、风险会话是否优先、应分配给哪个技能组、是否已经被认领。

**解决方案**
- 在 `Session` 上新增 `handoff_reason`、`handoff_skill_group`、`handoff_priority`、`handoff_enqueued_at`、`assigned_operator_id`
- `HandoffService` 根据风险词、行业和 integration_context 解析技能组与优先级
- 管理端 `GET /api/v1/admin/handoff/queue` 按优先级和入队时间排序
- 管理端 `POST /api/v1/admin/handoff/claim-next` 支持按技能组认领，认领后状态变为 `human_in_service`

**效果**
- ✅ 测试覆盖风险会话优先、同优先级按入队时间、按技能组过滤认领
- ✅ 面试 demo 可现场输出 `handoff_queue` 与 `claimed_session`
- ⚠️ 当前是单实例轻量队列，多实例原子认领为 Redis sorted set / 数据库事务 future target

---

## 三、待补充指标

以下指标需要实际运行数据或用户确认：

- [ ] **性能指标**: p50/p95 响应时间（文本/语音/RTC 分别统计）
- [ ] **可用性指标**: 服务 SLA（当前基于诊断样本，非全量统计）
- [ ] **业务指标**: 日均会话数、问题解决率、转人工率
- [ ] **规模指标**: 支持租户数、知识库文档量级、QPS 峰值
- [ ] **用户反馈**: 满意度平均分、负反馈率
- [ ] **成本指标**: 真实模型账单、缓存节省比例、租户预算阈值
- [ ] **RAG 指标**: 业务标注集准确率、召回率、人工复核通过率
- [ ] **队列指标**: 人工接管平均等待时长、技能组负载、重复认领冲突率

---

## 四、简历 STAR 精简版

### STAR 1: 多模态客服引擎
- **S**: 企业需要统一客服平台支持文本/语音/RTC，且不同渠道共享路由逻辑
- **T**: 设计多模态引擎，语音链路集成 ASR/TTS，RTC 链路支持 WebSocket 实时状态机
- **A**: 分层架构，渠道接入层标准化请求，核心引擎层统一路由，提供商适配层支持多厂商
- **R**: 三种渠道共享核心服务，语音提供商可插拔，RTC 支持打断和超时

### STAR 2: 插件化架构
- **S**: 路由/工具/行业/鉴权等能力需长期演进，写死主流程会导致耦合和冲突
- **T**: 实现完整插件系统，支持 7 种扩展点，可注册/启停/替换/优先级排序
- **A**: 定义 Plugin 抽象和描述符，实现注册中心管理生命周期，状态持久化
- **R**: 7 种插件全部落地，插件失败不拖垮主流程，重启后恢复启用状态

### STAR 3: 智能路由增强
- **S**: 传统 RAG 无法处理业务查询/高风险/人工请求，低置信度强答体验差
- **T**: 实现置信度分层、意图栈追踪、页面上下文感知的路由系统
- **A**: 聚合插件候选结果，动态加权，intent_stack 维护最近 6 个意图帧
- **R**: 支持多轮回退，连续低置信度自动转人工，路由决策可追溯

### STAR 4: 宿主鉴权桥接
- **S**: 企业已有 Cookie/JWT/SSO 等登录态，不愿统一 API Key
- **T**: 实现 5 种认证模式，支持自定义桥接器，复用宿主身份体系
- **A**: AuthBridgePlugin 两步抽象（can_handle + authenticate），按优先级尝试
- **R**: 支持子应用挂载和进程内调用，宿主可注册任意桥接逻辑

### STAR 5: 业务增强与行业适配
- **S**: 单纯 RAG 无法处理实时业务数据，且不同行业差异大
- **T**: 区分四类信息，支持 5 种行业适配器，实时数据通过工具插件查询
- **A**: 联合增强流程，行业识别 → 上下文构造 → 路由决策 → 知识/业务 → 回复增强
- **R**: 5 种行业落地，实时数据不写入知识库，页面上下文感知路由

### STAR 6: 低成本治理与安全缓存
- **S**: 高频知识问答消耗模型成本，但实时业务查询不能被缓存污染
- **T**: 在本地可运行前提下实现成本可观测与安全缓存策略
- **A**: 记录 LLM usage、cache_hit、估算成本和预算状态；只缓存版本化知识问答，业务查询不缓存
- **R**: 测试验证缓存命中、业务不缓存和成本摘要；真实节省比例待线上数据确认

### STAR 7: RAG 质量评测闭环
- **S**: RAG demo 无法证明长期质量，低分兜底引用容易被误判为命中
- **T**: 建立本地可复现 eval，输出失败明细
- **A**: 设计 eval cases，检查 route、引用关键词、有效命中阈值，并通过 TestClient 调真实 API
- **R**: `scripts/eval_rag.py` 可输出 `rag_eval_summary`，当前样例可复现通过；线上准确率需标注集

### STAR 8: 人工接管队列
- **S**: 高风险和投诉问题不能只提示“转人工”，还需要运营侧排队和认领
- **T**: 实现单实例轻量队列，支持优先级、技能组和 claim-next
- **A**: 在 Session 上落队列字段，管理端按优先级和入队时间排序，认领后切到 `human_in_service`
- **R**: 测试覆盖风险优先、技能组过滤和认领状态；多实例原子认领为 future target

---

## 五、证据索引

### 核心代码
- [`src/customer_ai_runtime/application/routing.py`](src/customer_ai_runtime/application/routing.py) - 路由服务
- [`src/customer_ai_runtime/application/session.py`](src/customer_ai_runtime/application/session.py) - 会话管理
- [`src/customer_ai_runtime/application/plugins.py`](src/customer_ai_runtime/application/plugins.py) - 插件注册
- [`src/customer_ai_runtime/application/auth.py`](src/customer_ai_runtime/application/auth.py) - 鉴权桥接
- [`src/customer_ai_runtime/application/voice_rtc.py`](src/customer_ai_runtime/application/voice_rtc.py) - 语音/RTC
- [`src/customer_ai_runtime/application/runtime.py`](src/customer_ai_runtime/application/runtime.py) - 运行时配置
- [`src/customer_ai_runtime/application/chat.py`](src/customer_ai_runtime/application/chat.py) - 成本记录与知识缓存
- [`src/customer_ai_runtime/application/admin.py`](src/customer_ai_runtime/application/admin.py) - 成本摘要与接管队列
- [`src/customer_ai_runtime/application/handoff.py`](src/customer_ai_runtime/application/handoff.py) - 转人工策略与队列字段
- [`src/customer_ai_runtime/evaluation.py`](src/customer_ai_runtime/evaluation.py) - RAG eval 评分逻辑

### 文档
- [`docs/architecture.md`](docs/architecture.md) - 总体架构
- [`docs/plugin-system.md`](docs/plugin-system.md) - 插件系统
- [`docs/auth-bridge.md`](docs/auth-bridge.md) - 宿主桥接
- [`docs/business-enhancement.md`](docs/business-enhancement.md) - 业务增强
- [`docs/slo.md`](docs/slo.md) - 性能口径
- [`docs/interview-playbook.md`](docs/interview-playbook.md) - 面试追问与 STAR 话术

### 测试
- [`tests/test_runtime_api.py`](tests/test_runtime_api.py) - 运行时 API 测试
- [`tests/test_routing_enhancements.py`](tests/test_routing_enhancements.py) - 路由增强测试
- [`tests/test_provider_extensions.py`](tests/test_provider_extensions.py) - 提供商扩展测试
- [`tests/test_interview_artifacts.py`](tests/test_interview_artifacts.py) - RAG eval 与 demo 测试

### 示例
- [`examples/host_custom_auth_bridge.py`](examples/host_custom_auth_bridge.py) - 自定义鉴权桥接
- [`examples/business_tool_plugin_example.py`](examples/business_tool_plugin_example.py) - 业务工具插件
- [`examples/interview_demo.py`](examples/interview_demo.py) - 面试演示闭环
- [`examples/rag_eval_cases.json`](examples/rag_eval_cases.json) - 本地 RAG eval cases

---

## 六、总结

**项目定位**: 企业级智能客服能力平台，不是简单 RAG 问答，而是能处理知识问答、实时业务查询、AI/人工协同的完整客服引擎。

**核心技术价值**:
1. ✅ 多模态统一架构（文本/语音/RTC）
2. ✅ 完整插件平台（7 种扩展点）
3. ✅ 智能路由增强（置信度分层/意图栈/场景感知）
4. ✅ 宿主鉴权桥接（5 种模式/自定义桥接）
5. ✅ 业务增强与行业适配（5 种行业/实时数据）
6. ✅ 运营管理闭环（热配置/反馈/诊断/知识库效果）
7. ✅ 成本治理闭环（usage/缓存/成本摘要/预算状态）
8. ✅ RAG 质量评测（离线 case/失败明细/可复现脚本）
9. ✅ 人工接管队列（技能组/优先级/claim-next）
10. ✅ 企业级工程规范（本地质量门禁/类型安全/限流脱敏）

**技术难点突破**:
- 多模态渠道统一路由
- 意图栈多轮追踪
- 插件失败隔离
- 宿主鉴权桥接通用性
- 知识库效果量化
- 成本治理与实时正确性冲突
- RAG 有效命中评测
- 人工接管队列化与认领

**待确认指标**: 性能分位数、业务规模、用户反馈数据、真实成本节省比例、线上 RAG 准确率需实际运行或用户补充。

## 七、简历资料维护口径

- 本文同时作为“项目亮点文档”和“技术难题与解决方案文档”入口，可被 `resume-new/项目文档索引.md` 直接引用。
- 可直接复用的已验证内容：插件化运行时、上下文路由、宿主鉴权桥接、成本治理、RAG eval、人工接管队列与本地质量门禁。
- 写入简历时只使用本文证据索引能追溯的实现；性能分位数、业务规模、真实成本节省比例和线上准确率继续标注为待补充指标。
