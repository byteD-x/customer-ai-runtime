# 项目总览

## 1. 项目做了什么

项目构建一个可复用、可挂载、可行业增强、可插件化扩展的智能客服平台，覆盖：

- 文本客服
- 语音客服
- RTC 实时通话
- RAG 知识增强
- 实时业务数据增强
- 行业适配
- AI / 人工协同
- 成本与缓存治理
- RAG 质量评测
- 人工接管队列
- 宿主系统集成
- 多认证模式桥接
- 运营管理

## 2. 解决了什么问题

- FAQ 与重复咨询占用人工
- 实时业务查询依赖多个系统
- 单纯 RAG 无法处理动态数据与人工协同
- 宿主系统不愿重建认证体系
- 行业逻辑与扩展能力容易写死在主流程中
- 高频知识问答如果每次都调用模型，成本不可控；但实时业务查询又不能被错误缓存
- RAG 命中不能只靠单条 demo，需要可复现的 route、引用和有效命中评测
- 转人工不能只返回提示语，还需要排队、优先级、技能组和认领链路

## 3. 为什么单纯 RAG 不够

- RAG 适合静态知识，不适合订单、物流、工单、账号等实时状态。
- 高风险、投诉、低置信度、人工请求不应该继续强答。
- 语音和 RTC 需要状态机、打断、超时和音频链路。

## 4. 为什么需要业务增强

因为客服回复必须融合：

- 行业静态知识
- 实时业务数据
- 当前用户与页面上下文
- 当前会话摘要和历史

## 5. 为什么需要宿主鉴权桥接

- 大部分业务系统已有 Cookie、Session、JWT、SSO 或内部 Token。
- 平台应复用宿主身份，不应要求宿主统一改成 `X-API-Key`。
- 客服平台只负责统一映射和授权，不侵入宿主身份体系。

## 6. 为什么需要插件机制

- 路由、工具、行业、鉴权、上下文和回复后处理都需要长期演进。
- 如果把这些逻辑写死在主流程，会导致版本耦合、租户冲突和维护困难。

## 7. 关键技术各自解决什么问题

- `RAG`：静态知识增强
- `Business Tool / Adapter`：实时业务数据查询
- `Auth Bridge`：复用宿主登录态
- `Plugin Registry`：统一扩展装配
- `Industry Adapter`：按行业差异增强路由和上下文
- `ASR / TTS / RTC`：语音与实时通话链路
- `Handoff Service`：AI 与人工协同
- `LLMUsage / Cost Summary`：token、usage 来源、币种、账期、缓存命中、估算成本与本地预算阈值
- `RAG Eval`：本地标注 case 和脱敏样本驱动的检索、拒答与引用质量验证
- `Handoff Queue`：基于会话状态的单实例人工接管队列，`atomic_claim` 仅表示单进程锁内认领，`consistency_scope=single_process` 明确一致性边界

## 8. 系统如何运行

### 当前事实

- 当前为单体 FastAPI 参考实现。
- 可作为独立服务或挂载子应用运行。
- 已具备多认证桥接、插件注册中心、行业增强主链路、成本治理、RAG eval 本地标注样例、线上样本评估入口、带审计元数据的外部 readiness 脚本、k6 smoke 模板与人工接管队列。

### Target State

- 后续可按边界拆分为多服务。
- 多实例人工接管队列、真实客服工单系统、真实 OpenAI / Qdrant / 业务系统端到端联调、生产 SLA 和真实成本节省比例属于 future target，不能写成当前事实。

## 9. 如何接入

- API 模式：直接调用 HTTP / WebSocket
- 挂载模式：宿主挂载子应用
- SDK / facade 模式：宿主进程内调用

## 10. 如何扩展

- 注册 `AuthBridgePlugin`
- 注册 `BusinessToolPlugin`
- 注册 `IndustryAdapterPlugin`
- 注册 `RouteStrategyPlugin`
- 注册 `ContextEnricherPlugin`
- 注册 `ResponsePostProcessorPlugin`

## 11. 如何维护

- 通过 Admin API 维护 Prompt / Policy / Plugin 状态
- 通过 Diagnostics / Metrics 做排障
- 通过 Cost Summary 观察模型成本、usage 来源、币种、账期、缓存命中和预算风险
- 通过 RAG Eval 脚本做本地标注样例质量回归；通过 online eval 脚本评估输入的脱敏线上样本
- 通过 Handoff Queue 管理人工接管优先级与认领
- 通过文档和进展控制约束设计与实现一致性
