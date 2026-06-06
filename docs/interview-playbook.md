# Customer AI Runtime 面试追问手册

> 定位：AI 平台架构 / AI 客服 Runtime。本文只记录当前仓库可验证事实；外部 OpenAI / Qdrant provider、Redis 或真实业务系统联调需配置，未验证内容统一标注为 future target。

## 1. 低成本治理：为什么能低成本跑 AI 客服？

**可讲亮点**

- 知识类问答支持安全缓存，重复命中时 `cache_hit=true`，本轮 usage 归零；业务查询不缓存，避免订单、售后等实时状态过期。
- 每轮文本请求记录 provider、model、route、token、模型价格估算成本、缓存命中和预算状态，管理端可按 provider / route 汇总。
- 默认 `local` provider 可本地跑通；OpenAI usage 可在 provider 层透传 SDK 返回的 usage。

**代码证据**

- `src/customer_ai_runtime/application/chat.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/domain/models.py`
- `tests/test_runtime_api.py::test_chat_cost_summary_and_knowledge_cache`

**验证命令**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_runtime_api.py::test_chat_cost_summary_and_knowledge_cache
```

**面试官可能追问**

- 问：为什么只缓存知识问答，不缓存业务查询？
- 答：知识问答依赖版本化知识库和引用片段，缓存 key 绑定 tenant、query、knowledge_base_id、active version、prompt hash 和 citation key；业务查询涉及订单、物流、售后等实时数据，缓存会带来错误状态，因此强制不缓存。

- 问：成本估算是不是线上真实成本？
- 答：当前支持本地模型价格表估算，用于治理链路和面试演示；真实 OpenAI 接入时优先使用 SDK usage 字段，再结合租户、币种和结算周期做账单核算。仓库不虚构线上成本指标。

## 2. RAG 质量评测：如何证明 RAG 不只是“能回答”？

**可讲亮点**

- 新增 8 个本地 eval cases，评估 route 是否正确、citation 是否包含期望关键词、citation score 是否达到有效命中阈值。
- eval payload 支持多知识库播种，当前覆盖 `kb_support` 和 `kb_saas`，包含行业术语和反馈回放样例。
- `low_score_miss` 用例用于证明“低分不算有效命中”，避免把兜底引用包装成准确命中。
- 失败明细包含 missing keywords、route mismatch、effective hit mismatch，可直接指导补文档、调切片或调阈值。

**代码证据**

- `src/customer_ai_runtime/evaluation.py`
- `examples/rag_eval_cases.json`
- `scripts/eval_rag.py`
- `tests/test_interview_artifacts.py`

**验证命令**

```powershell
.venv\Scripts\python.exe scripts\eval_rag.py --json
.venv\Scripts\python.exe -m pytest tests\test_interview_artifacts.py
```

**面试官可能追问**

- 问：为什么不直接说准确率多少？
- 答：当前仓库没有线上标注集和真实流量，只能给可复现的离线 eval 结果；线上准确率必须基于业务标注集、灰度数据和人工复核，不能凭 demo case 虚构。

- 问：评测失败后怎么优化？
- 答：先看失败类型：route 错就调整路由策略或上下文信号；citation keyword 缺失就补知识、改切片；effective hit 低就调 embedding、召回 top_k、min_score 或切片参数。

## 3. 人工接管队列：为什么不是简单“转人工”？

**可讲亮点**

- Session 增加 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
- `handoff_package` 增加情绪、问题摘要、最后用户消息、相关业务对象、页面上下文和行为信号，便于人工客服接手。
- 队列按风险优先级倒序、同优先级按入队时间排序；支持 `skill_group` 过滤和 `claim-next`。
- 风险类关键词会进入 `risk` 技能组，认领后状态从 `waiting_human` 变为 `human_in_service`。

**代码证据**

- `src/customer_ai_runtime/application/handoff.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/application/session.py`
- `tests/test_runtime_api.py::test_handoff_queue_orders_and_claims_by_skill_group`

**验证命令**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_runtime_api.py::test_handoff_queue_orders_and_claims_by_skill_group
```

**面试官可能追问**

- 问：多实例下怎么保证 claim-next 不重复？
- 答：当前是单实例本地可验证实现；多实例 future target 是 Redis sorted set 或数据库行级锁，按 priority/enqueued_at 排序并用原子 pop/事务认领。

## 4. 演示闭环：现场怎么讲？

**演示顺序**

1. 知识问答：输出 `route=knowledge` 和 `citations`。
2. 重复知识问答：输出 `knowledge_cache_hit=true`。
3. 业务查询：输出 `route=business` 和 `tool_result`，证明实时工具链路不走缓存。
4. 风险问题：输出 `handoff_package`，进入 `handoff_queue`，再 `claim-next`。
5. 成本摘要：展示 `cost_summary` 的 cache hit 和按 route 聚合。
6. RAG eval：展示 `rag_eval_summary`。

**验证命令**

```powershell
.venv\Scripts\python.exe examples\interview_demo.py
```

当前本地实测基线以本节验证命令输出为准；该结果只代表当前本地样例，不代表线上准确率、真实成本节省、生产 SLA 或外部 provider 联调结果。

## 5. Prompt 版本与回滚：如何降低提示词改坏的风险？

**可讲亮点**

- Prompt 更新会形成版本历史，记录 revision、变更摘要和激活状态，便于解释“为什么这次回答策略变了”。
- Prompt hash 已进入知识问答缓存 key，避免 Prompt 变更后复用旧缓存答案。
- 回滚 API 为 `POST /api/v1/admin/prompts/{revision}/rollback`，用于把历史版本恢复为新的激活版本，并保留完整 revision 审计链。

**代码证据**

- `src/customer_ai_runtime/application/runtime.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/api/routes.py`
- `tests/test_runtime_api.py`

**面试官可能追问**

- 问：为什么回滚不是直接覆盖当前 Prompt？
- 答：回滚也应生成一条新版本记录，这样审计链路能看到从哪个 revision 回退、谁触发、原因是什么；直接覆盖会丢失事故复盘线索。

## 6. 受控 Agent 工具流：为什么不是开放式 Agent？

**可讲亮点**

- 工具流使用显式 `steps`、`allowed_tools` 和 `max_steps`，只允许调用白名单工具，避免模型自由规划导致越权或循环调用。
- 每一步保留输入、输出、失败状态和降级策略，适合面试演示“订单状态 -> 物流轨迹 -> 售后建议”这类确定性链路。
- HTTP API 为 `POST /api/v1/agents/tool-workflow`，仅 `admin` / `operator` 可调用；服务围绕顺序执行、禁用工具拦截和失败停止设计。

**代码证据**

- `src/customer_ai_runtime/application/agent_workflow.py`
- `src/customer_ai_runtime/api/routes.py`
- `tests/test_agent_workflow.py`
- `tests/test_runtime_api.py`

**面试官可能追问**

- 问：为什么不用一个完全自主的 Agent？
- 答：客服场景更看重可控、可审计和权限边界。受控工具流把“能调用什么、最多调用几步、失败后怎么处理”写进请求和服务约束，便于定位问题，也更适合接入真实业务系统。

## 7. 技术难点与解决方案

### 难点 1：低成本与实时正确性的冲突

**问题**：FAQ 高频重复，完全不缓存会浪费模型调用；但订单、物流、售后等业务查询如果缓存，会把过期状态返回给用户。

**解决方案**：

- 只对知识问答启用安全缓存。
- cache key 绑定 tenant、query、knowledge_base_id、知识版本、prompt hash 和 citation key。
- 宿主身份上下文存在时不缓存，避免用户级敏感答案串用。
- 业务查询走实时工具链路，明确 `cache_hit=false`。

**可验证结果**：`test_chat_cost_summary_and_knowledge_cache` 覆盖首次知识问答、重复知识问答、业务查询和成本摘要聚合；`test_chat_cost_uses_configured_model_price_map` 覆盖本地模型价格表。

### 难点 2：RAG 评测不能把“有引用”当“答对”

**问题**：本地检索兜底可能返回低分引用，如果只看 citation 数量，会误判为命中。

**解决方案**：

- eval case 同时检查 route、引用关键词和 citation score，并覆盖多知识库、行业术语、反馈回放和低分未命中。
- `expect_effective_hit=false` 用于验证低分未命中。
- 失败明细暴露 `missing_keywords`、`route_ok`、`effective_hit_ok`。

**可验证结果**：`scripts/eval_rag.py` 输出 `rag_eval_summary`；`tests/test_interview_artifacts.py` 覆盖引用关键词失败明细。

### 难点 3：转人工要能被运营侧消费

**问题**：只告诉用户“已转人工”不够，客服主管需要知道队列顺序、技能组、风险优先级和认领人。

**解决方案**：

- `Session` 增加 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
- `HandoffPackage` 补充 sentiment、issue_summary、last_user_message、related_business_objects、page_context、behavior_signals。
- 管理端 queue 按 priority 倒序、同优先级按入队时间排序。
- `claim-next` 认领后切换为 `human_in_service` 并记录 operator。

**可验证结果**：`test_handoff_queue_orders_and_claims_by_skill_group` 覆盖风险优先、技能组过滤和认领状态。

### 难点 4：面试演示必须可复现

**问题**：外部 OpenAI、Qdrant、真实订单系统都可能因为配置或网络不可用导致现场演示失败。

**解决方案**：

- 演示默认使用本地 LLM / Vector / Business provider。
- 脚本使用临时 storage，不污染本地状态。
- 输出稳定字段，便于面试时按字段讲架构。

**可验证结果**：`.venv\Scripts\python.exe examples\interview_demo.py` 退出码为 0，输出关键段落。

## 8. STAR 表达模板

### STAR：低成本 AI 客服治理

- **S**：FAQ 高频重复但业务查询必须实时，简单统一缓存会造成错误。
- **T**：在不引入付费依赖的前提下实现成本可观测和安全缓存。
- **A**：增加 usage/cost 字段、模型价格表估算、知识问答安全缓存、业务查询不缓存、管理端成本摘要。
- **R**：本地测试可验证缓存命中、业务不缓存、价格表估算和成本聚合；真实节省比例待线上账单数据确认。

### STAR：RAG 质量评测

- **S**：RAG demo 容易只展示成功样例，无法解释引用缺失和低分召回。
- **T**：建立本地可复现 eval，证明评测机制而非虚构准确率。
- **A**：设计 8 个 eval cases，检查 route、引用关键词、有效命中阈值，输出失败明细，并覆盖多知识库与反馈回放。
- **R**：`scripts/eval_rag.py` 可本地复跑，当前样例通过；线上准确率需业务标注集。

### STAR：人工接管队列

- **S**：高风险和投诉类问题需要进入人工队列，且运营侧要按优先级处理。
- **T**：实现单实例轻量队列和认领链路。
- **A**：在 Session 上落队列字段，生成结构化交接包，管理端提供 queue 和 claim-next，风险会话优先。
- **R**：本地测试验证排序、技能组过滤和认领状态；多实例原子认领作为 future target。

### STAR：Prompt 治理与受控工具流

- **S**：Prompt 调整和多工具自动化都可能引入回答漂移、越权调用或难以复盘的问题。
- **T**：在不宣称线上指标的前提下，补齐本地可解释的 Prompt 版本历史和受控工具编排设计。
- **A**：Prompt 更新记录 revision，缓存 key 绑定 prompt hash；工具流限制白名单、步骤上限和失败降级，并保留审计轨迹。
- **R**：本地测试覆盖 Prompt 回滚、受控工具流 trace、禁用工具拦截与步骤上限，适合作为面试中的治理设计讲点。

## 9. 边界与 future target

- 当前本地 JSON 存储适合开发、演示和单实例部署；多实例强一致不是当前事实。
- 当前 RAG eval 是小规模本地 case，不代表线上准确率。
- 当前成本支持本地模型价格表估算；真实账单仍需要接模型供应商 usage、币种、租户预算和结算周期。
- Redis queue、Postgres repository、真实客服工单系统、Qdrant/OpenAI 联调均可作为下一阶段扩展，不写成已完成能力。
