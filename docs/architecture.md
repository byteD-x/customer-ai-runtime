# 总体架构设计

## 1. 设计目标

平台目标是在统一客服引擎上，支持文本、语音、RTC、多行业增强、宿主系统挂载、自定义鉴权桥接、插件化扩展、低成本治理、RAG 质量评测和人工接管队列。

## 2. 当前事实与 Target State

### 2.1 当前事实

- 已有单体参考实现，可运行文本、语音、RTC、知识库、基础工具与人工协同。
- 运行模式支持独立 FastAPI 与宿主 FastAPI 挂载。
- 已落地成本摘要、知识问答安全缓存、RAG eval 本地标注样例、RAG 引用来源与拒答门禁、带审计元数据的外部 readiness 脚本、k6 smoke 模板与单实例人工接管队列。

### 2.2 Target State

- 保持单体可运行，同时保留未来拆分为多服务的边界。
- 多实例人工接管队列、真实模型账单计费、真实业务标注集评测和真实外部系统端到端联调属于 future target。

## 3. 分层架构

```text
┌──────────────────────────────────────────────────────────────┐
│ 渠道接入层                                                   │
│ HTTP Chat / Voice / Admin API | RTC WebSocket | SDK / 挂载  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 宿主桥接层                                                   │
│ Auth Bridge | Host Auth Context Mapper | Host Context Proxy │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 核心客服引擎层                                               │
│ Session | Route Orchestrator | LLM Orchestrator             │
│ Voice Runtime | RTC State Machine | Handoff Orchestrator    │
└──────────────────────────────────────────────────────────────┘
            │                          │
            ▼                          ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│ 业务增强层                  │  │ 插件平台层                  │
│ Industry Adapter            │  │ Plugin Registry             │
│ Business Context Builder    │  │ Route / Tool / Auth /       │
│ Knowledge Domain Manager    │  │ Industry / Handoff /        │
│ Real-time Data Provider     │  │ Context / Response Plugins  │
│ Response Enhancement        │  │ Lifecycle / Priority        │
└─────────────────────────────┘  └─────────────────────────────┘
            │                          │
            └──────────────┬───────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 提供商适配层                                                 │
│ LLM | ASR | TTS | RTC | Vector Store | Business API         │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 运营管理层                                                   │
│ Prompt | Policy | Knowledge | Plugin Admin | Metrics        │
│ Diagnostics | Cost Summary | RAG Eval | Handoff Queue       │
│ 灰度与回滚                                                    │
└──────────────────────────────────────────────────────────────┘
```

## 4. 关键模块关系

### 4.1 渠道接入层

- 负责把文本、语音、RTC 输入标准化为统一请求模型。
- 负责从 HTTP Header / Cookie / Query / Body 中收集宿主上下文。

### 4.2 宿主桥接层

- 优先处理认证入口。
- 当缺失 `X-API-Key` 时，允许通过 `Auth Bridge` 完成宿主身份认证。
- 产出统一 `HostAuthContext`。

### 4.3 核心客服引擎层

- `Session` 管理会话生命周期。
- `Route Orchestrator` 决定知识、业务、人工、高风险、插件路线，并执行置信度分层。
- `LLM Orchestrator` 融合检索结果、实时数据和上下文。
- `Cost Governance` 记录 usage、usage 来源、币种、账期、cache hit、估算成本和本地预算阈值。
- `RTC` 服务直接处理实时热路径，不通过事件总线。

### 4.4 业务增强层

- `Business Context Builder` 合并页面、用户、宿主对象、会话摘要和 `intent_stack`。
- `Knowledge Domain Manager` 管理不同租户、行业下的知识域。
- `Real-time Business Data Provider` 通过业务工具插件读取动态数据。
- `Response Enhancement Orchestrator` 统一做引用、风格、脱敏和结构化输出后处理。
- `RAG Eval` 不进入在线热路径，作为离线脚本验证 route、引用关键词、上下文 precision/recall、有效命中、引用准确率、拒答准确率和启发式 faithfulness 分数。

### 4.5 插件平台层

- 插件是主流程的一部分，不是可有可无的边车。
- 路由、业务工具、人工协同、行业适配、鉴权桥接、上下文增强、回复后处理都通过插件接入。

## 5. 典型调用链

### 5.1 文本请求

1. 接收 HTTP 请求。
2. `AuthService` 通过 API Key 或 Auth Bridge 解析身份。
3. `Business Context Builder` 合并宿主与页面上下文。
4. `Industry Adapter` 识别行业。
5. `Session` 维护 `intent_stack`，记录主题切换与回退历史。
6. `Route Strategy Plugins` 产出候选路由。
7. `Route Orchestrator` 结合 `page_context`、`business_objects`、`intent_stack` 对候选结果做动态加权。
8. 若路由置信度不足，先走澄清兜底；若连续低置信度或存在挫败信号，则升级转人工。
9. 若为知识型：`Knowledge Domain Manager` 解析知识域并检索。
10. 若为知识型且满足安全条件：尝试读取知识问答缓存；命中时不再调用 LLM。
11. 若为业务型：`Business Tool Plugins` 或 `BusinessAdapter` 调实时接口，业务结果不缓存。
12. `LLM / Response Enhancement` 生成回复。
13. `Human Handoff Plugins` 判断是否转人工，并写入接管队列字段。
14. 记录 usage、usage 来源、币种、账期、cache hit、估算成本、本地预算阈值与诊断事件。
15. `Response Post Processor Plugins` 完成脱敏、格式化、多语言或结构化输出。

### 5.4 面试演示与离线评测链路

1. `examples/interview_demo.py` 使用本地临时存储和默认 provider 启动 TestClient。
2. 依次演示知识问答、重复知识问答缓存命中、业务工具查询、风险转人工、队列认领、成本摘要。
3. `scripts/eval_rag.py` 使用本地标注 eval cases 验证 route、引用关键词、上下文 precision/recall、有效命中率、cohort、人工复核状态、引用准确率、拒答准确率、faithfulness 分数、`offline_accuracy` 和失败明细。
4. `scripts/eval_online_rag.py` 可读取脱敏线上 JSON/JSONL 标注样本并输出样本级 `online_accuracy`。
5. `scripts/check_external_readiness.py` 检查 OpenAI models、OpenAI Admin usage/costs、Qdrant health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖的配置与可达性；未配置时返回 `skipped`，JSON 输出带顶层与逐项 `audit` 元数据用于说明检查范围、依赖环境变量、探针类型和证据口径。
6. `deploy/k6-smoke.js` 提供健康检查与指标摘要接口的 k6 smoke 模板。
7. 该链路用于可复现演示，不代表线上准确率、真实成本、外部联调通过或生产压测结果。

### 5.2 语音请求

1. ASR 产出文本。
2. 进入统一文本链路。
3. TTS 输出音频。

### 5.3 RTC 请求

1. 建房/入房。
2. WebSocket 收用户音频事件。
3. 直接走 RTC 状态机与语音链路。
4. 返回 `transcript`、`assistant_message`、`assistant_audio`、`state_changed`、`handoff` 等事件。

## 6. API 模式与挂载模式

### 6.1 API 模式

- 独立部署。
- 主要通过 `X-API-Key` 或宿主桥接 Header / Cookie 调用。

### 6.2 挂载模式

- 宿主系统把运行时作为子应用挂载，或在进程内直接调用 facade。
- 宿主系统可以注册自定义 `AuthBridgePlugin`。
- 平台复用宿主登录态与租户/权限上下文。

## 7. 部署形态

### 7.1 当前交付形态

- 单体 FastAPI 参考实现
- 本地 JSON 持久化
- 可选 OpenAI / Qdrant / HTTP Business Adapter
- 单实例人工接管队列基于 `Session` 状态字段排序，`atomic_claim=true` 只代表单进程锁内认领，`consistency_scope=single_process` 明确一致性边界
- RAG eval 与 interview demo 默认只依赖本地 provider；online eval 只代表输入样本；readiness 脚本未配置外部凭据时返回 `skipped`，其审计元数据只说明检查口径

### 7.2 Future Target

- API Gateway / Channel Gateway
- Core Orchestrator
- Voice Runtime
- RTC Gateway
- Ops API / Console
- 独立知识与向量服务

## 8. 关键原则

- 主对象统一使用 `tenant_id`、`session_id`、`knowledge_base_id`。
- `session` 承载可恢复上下文，不与 `conversation` 混用。
- 路由决策必须保留 `confidence`、`confidence_band` 和 `intent_stack` 轨迹，避免低置信度强答。
- 实时语音热路径不经过事件总线。
- 静态知识与实时业务数据必须分离处理。
- 认证与上下文映射必须插件化，不把宿主逻辑写死到主流程。
- 成本治理必须区分知识问答缓存与实时业务查询，不能用缓存牺牲业务正确性。
- 离线 eval 只证明当前本地标注 case 可复现，不宣称线上准确率。
