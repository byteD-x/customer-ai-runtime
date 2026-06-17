# 实施路线图

## 1. 阶段划分

| 阶段 | 目标 | 依赖 | 当前状态 |
| --- | --- | --- | --- |
| 1 | 业务需求分析 | 用户目标 | 已完成并校正 |
| 2 | 总体架构设计 | 阶段 1 | 已完成并校正 |
| 3 | 模块设计 | 阶段 2 | 已完成并校正 |
| 4 | 业务增强设计 | 阶段 3 | 本轮补齐 |
| 5 | 宿主桥接与鉴权设计 | 阶段 3 | 本轮补齐 |
| 6 | 插件系统设计 | 阶段 3 | 本轮补齐 |
| 7 | 路线图与进展控制 | 阶段 1-6 | 本轮同步维护 |
| 8 | 基础骨架 | 阶段 1-7 | 已完成 |
| 9 | 核心模块开发 | 阶段 8 | 已完成当前面试基线 |
| 10 | 业务增强与行业适配开发 | 阶段 4, 9 | 已完成当前面试基线 |
| 11 | 宿主挂载与鉴权桥接开发 | 阶段 5, 9 | 已完成当前面试基线 |
| 12 | 插件机制开发 | 阶段 6, 9 | 已完成当前面试基线 |
| 13 | 语音能力开发 | 阶段 9 | 已完成本地与可选 provider 基线 |
| 14 | RTC 通话能力开发 | 阶段 13 | 已完成当前面试基线 |
| 15 | 人工协同与运营能力开发 | 阶段 9, 12 | 已完成成本治理、队列与摘要基线 |
| 16 | 联调、测试与文档收尾 | 全阶段 | 已完成本地可复现基线 |

## 2. 联调顺序

1. Auth Bridge 与 API Key 并行联调
2. 插件注册中心与路由插件联调
3. 行业适配器与上下文构造器联调
4. 路由置信度阈值、`intent_stack` 与页面上下文加权联调
5. 业务工具插件与业务适配器联调
6. 文本链路联调
7. 语音链路联调
8. RTC 链路联调
9. 人工协同与管理接口联调
10. 成本治理、知识缓存与业务不缓存联调
11. RAG eval 与面试 demo 联调
12. 外部 OpenAI models、OpenAI Admin usage/costs、Qdrant runtime config/health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖 readiness 检查与审计元数据输出
13. 线上脱敏样本 RAG eval 与 k6 smoke 模板验证入口

## 3. 测试顺序

1. 单元测试：插件注册、Auth Bridge、Context Builder
2. 单元测试：路由置信度分层、多轮意图回退、页面上下文感知路由
3. 集成测试：文本、知识、业务工具、人工协同
4. 宿主挂载测试：FastAPI 子应用、进程内 facade
5. 鉴权桥接测试：API Key、Session、JWT、Custom Token
6. 语音与 RTC 测试
7. 成本与缓存测试：知识问答首次/重复、业务查询不缓存、本地模型价格表估算、usage 来源、币种、账期、本地预算阈值和成本摘要聚合
8. 人工接管队列测试：优先级、入队时间、技能组过滤、认领状态、`queue_backend`、`atomic_claim`、`consistency_scope`，以及 local / SQLite 后端口径
9. RAG eval 测试：10 个本地标注 cases、多知识库、cohort、人工复核状态、`offline_accuracy`、命中、低分未命中、引用关键词失败明细、引用准确率、上下文 precision/recall、拒答准确率和 faithfulness 分数
10. 面试 demo 冒烟：输出 route、citations、finance_knowledge、tool_result、handoff_package、handoff_queue、claimed_session、cost_summary、rag_eval_summary
11. 外部 readiness 冒烟：未配置凭据或未启用对应 provider 时返回 `skipped`，配置后按真实 HTTP/TCP 探针或配置一致性检查返回，并输出检查范围、依赖环境变量、探针类型和证据口径
12. k6 smoke：服务启动后验证健康检查与指标摘要接口，压测结果不外推生产 SLA
12. 文档一致性核对

## 4. Future Target

- 多实例人工接管队列：在当前 SQLite 队列表事务认领基础上，继续落地 Redis sorted set、Postgres 行级锁队列和共享 Session 存储。
- 真实成本结算：在现有本地模型价格表基础上接入 provider 原生 usage、租户预算、币种和账单周期。
- 线上 RAG 评估：接入业务标注集、人工复核和灰度流量反馈。
- 外部系统联调：真实 OpenAI / Qdrant / 业务 API / 客服工单系统配置后再声明通过。
