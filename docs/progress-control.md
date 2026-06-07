# 项目进展控制文档

## 1. 最终产品目标

交付一个完整的、可运行的、可维护的、可扩展的、可挂载到宿主系统中的智能客服平台，覆盖文本、语音、RTC、RAG、实时业务数据增强、行业增强、宿主桥接、插件扩展、人工协同、运营管理、测试与文档。

## 2. 当前事实

- 仓库已有基础代码和基础文档，不是空仓。
- 已有能力：文本、语音、RTC、知识库、业务工具、人工接手、管理 API、示例、基础测试。
- 本轮新增已落地能力：`Auth Bridge`、插件注册中心、行业适配器、上下文解析、知识域管理、回复后处理、插件管理接口、多认证模式测试。
- 本轮进一步增强：插件生命周期自动启动/关闭、插件启停状态持久化、宿主自定义桥接插件注册入口与示例。
- 面试项目强化能力已落地：成本治理与知识问答缓存、usage 来源/币种/账期/预算阈值字段、可配置模型价格表、provider billing 样本导入、非阻断样本质量诊断、独立金额聚合与诊断差异摘要、Prompt revision 只读摘要与安全 diff、RAG eval 本地标注样例、RAG 引用来源与拒答门禁、线上样本评估入口、结构化交接包、接口化入队的人工接管队列、可选 SQLite 队列表事务认领、带审计元数据且覆盖 Qdrant provider 配置一致性的外部 readiness 脚本、k6 smoke 模板、面试演示脚本和 STAR 材料。
- 仍保留的边界：当前为单体参考实现，外部 OpenAI / Qdrant / 真实业务系统 / 客服工单系统联调依赖外部配置；readiness 脚本只检查配置一致性、HTTP/TCP 可达性和部分权限探针，审计元数据只说明检查口径，不代表端到端联调通过。

## 3. 阶段状态

| 阶段 | 名称 | 状态 | 验收结论 |
| --- | --- | --- | --- |
| 1 | 业务需求分析 | 已完成 | 已校正文档 |
| 2 | 总体架构设计 | 已完成 | 已校正文档 |
| 3 | 模块设计 | 已完成 | 已校正文档 |
| 4 | 业务增强设计 | 已完成 | 文档与代码已对齐 |
| 5 | 宿主桥接与鉴权设计 | 已完成 | API Key / Session / JWT / Custom Token 已支持 |
| 6 | 插件系统设计 | 已完成 | 注册、启停、优先级、管理接口已落地 |
| 7 | 路线图与进展控制 | 已完成 | 已更新当前基线 |
| 8 | 基础骨架 | 已完成 | 基础工程已存在 |
| 9-16 | 实现与联调阶段 | 已完成当前面试基线 | 成本治理、RAG eval 标注样例、online eval 入口、接管队列、readiness 脚本、k6 smoke 模板、演示脚本和测试已补齐 |

## 4. 已完成清单

- 基础 FastAPI 工程骨架
- 文本客服主链路
- 基础知识库与向量检索
- 基础业务工具能力
- 语音轮次处理
- RTC 房间与 WebSocket 事件
- 人工接手与会话关闭
- 管理接口、示例与基础自动化测试
- 本轮设计文档基线重写
- Auth Bridge 抽象与多模式鉴权桥接
- 插件注册中心与路由/工具/人工协同/行业/上下文/回复插件
- 行业适配器、知识域管理与上下文解析接口
- 插件管理接口与多认证模式测试
- LLM usage / cache hit / estimated cost 记录、`usage_source`、`cost_source`、可配置 `billing_currency`、可配置 `billing_period`、可配置 `tenant_budget_estimated_cents`、provider billing 样本导入、非阻断样本质量诊断、诊断样本成本差异摘要、租户成本策略与成本摘要接口
- 可配置模型价格表，用于按 provider / model 估算本轮调用成本
- 知识问答安全缓存与业务查询不缓存策略
- Prompt revision 只读摘要、安全 diff、账本异常 issues 与回滚审计链路
- RAG eval 8 个本地标注 cases、多知识库样例、cohort、人工复核状态、`offline_accuracy`、`citation_accuracy`、`context_precision`、`context_recall`、`refusal_accuracy`、`faithfulness_score`、评测脚本与失败明细
- 结构化 `handoff_package`：情绪、问题摘要、最后用户消息、相关业务对象、页面上下文与行为信号
- 人工接管队列、`HandoffQueueBackend.enqueue` 入队契约、技能组、优先级排序、`queue_backend` / `atomic_claim` / `consistency_scope` 返回字段、默认 local 单进程认领、可选 SQLite 队列表事务认领和 `claim-next`
- OpenAI models、OpenAI Admin usage/costs、Qdrant runtime config/health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖外部 readiness 脚本，缺少配置或未启用对应 provider 时返回 `skipped`，配置不一致或探针失败时返回 `failed`，并在 JSON 输出中提供顶层与逐项 `audit` 元数据
- `scripts/eval_online_rag.py` 线上脱敏样本评估入口和 `deploy/k6-smoke.js` 压测模板
- 面试演示脚本与 STAR/简历材料补充

## 5. 进行中清单

- 示例接入进一步丰富
- 真实外部 provider / 业务系统联调材料补充（需要外部配置）

## 6. 待开始清单

- 暂无阻塞型待开始项，后续以增强和部署深化为主

## 7. 风险与阻塞

- 宿主鉴权桥接涉及安全边界，必须避免把未验证的 Token 直接当可信身份。
- 插件化改造会影响现有路由、工具和人工协同主链路，需通过回归测试兜底。
- 当前默认本地 ASR/TTS 仍主要用于开发验证；真实生产音频能力依赖外部提供商配置。
- 当前 RAG eval 是本地标注样例，包含 cohort、人工复核状态、`offline_accuracy`、引用准确率、上下文 precision/recall、拒答准确率和 faithfulness 分数；online eval 只代表输入的脱敏样本，不代表全量线上准确率。
- 当前成本支持本地模型价格表估算、provider billing 样本导入、非阻断 `quality_issues` / `quality_issue_count` 样本质量诊断和诊断样本成本差异摘要，并显式返回 usage 来源、cost 来源、可配置币种、可配置账期和可配置本地预算阈值；这些只代表本地样本治理口径，自动拉取 provider 真实账单、完整租户结算和线上节省比例仍需要接入账单系统。
- 当前人工接管队列默认 `local` 后端，入队动作已接口化并由容器统一注入；可选 `sqlite` 后端使用共享队列表事务认领并返回 `consistency_scope=shared_sqlite_queue`。该能力只覆盖队列层，不代表 JSON Session 仓储已具备完整多实例强一致；Redis/Postgres 队列与共享 Session 存储仍是 future target。
- 当前 readiness 脚本在缺少外部配置或未启用对应 provider 时返回 `skipped`，并输出检查范围、依赖环境变量、探针类型和证据口径等审计元数据；`qdrant_runtime_config` 只说明 Qdrant provider 与 URL 配置是否一致，不能据此声明 Qdrant 端到端 RAG 联调通过，k6 smoke 模板未运行真实压测前不能声明生产 SLA。

## 8. 每阶段输入输出

### 阶段 4

- 输入：业务与模块设计
- 输出：`docs/business-enhancement.md`、`docs/adapter-design.md`

### 阶段 5

- 输入：架构与集成约束
- 输出：`docs/auth-bridge.md`

### 阶段 6

- 输入：模块边界与扩展要求
- 输出：`docs/plugin-system.md`

### 阶段 8-16

- 输入：前述设计文档
- 输出：源码、API、测试、示例、部署文档

## 9. 最终交付检查清单

- 源码
- 配置
- API
- 宿主桥接
- 插件体系
- 行业增强
- 语音与 RTC
- 人工协同
- 成本治理
- RAG eval
- 面试演示
- 测试
- 示例
- 文档
