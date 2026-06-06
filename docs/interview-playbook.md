# Customer AI Runtime 面试追问手册

> 定位：AI 平台架构 / AI 客服 Runtime。本文只记录当前仓库可验证事实；未接入真实 OpenAI、Qdrant、Redis 或外部业务系统的内容统一标注为 future target。

## 1. 低成本治理：为什么能低成本跑 AI 客服？

**可讲亮点**

- 知识类问答支持安全缓存，重复命中时 `cache_hit=true`，本轮 usage 归零；业务查询不缓存，避免订单、售后等实时状态过期。
- 每轮文本请求记录 provider、route、token 估算、估算成本、缓存命中和预算状态，管理端可按 provider / route 汇总。
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
- 答：当前本地 provider 是估算值，用于治理链路和面试演示；真实 OpenAI 接入时优先使用 SDK usage 字段，再按实际模型价格表计算。仓库不虚构线上成本指标。

## 2. RAG 质量评测：如何证明 RAG 不只是“能回答”？

**可讲亮点**

- 新增本地 eval cases，评估 route 是否正确、citation 是否包含期望关键词、citation score 是否达到有效命中阈值。
- `low_score_miss` 用例用于证明“低分不算有效命中”，避免把兜底引用包装成准确命中。
- 失败明细包含 missing keywords、route mismatch、effective hit mismatch，可直接指导补文档、调切片或调阈值。

**代码证据**

- `src/customer_ai_runtime/evaluation.py`
- `examples/rag_eval_cases.json`
- `scripts/eval_rag.py`
- `tests/test_interview_artifacts.py`

**验证命令**

```powershell
.venv\Scripts\python.exe scripts\eval_rag.py
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
4. 风险问题：进入 `handoff_queue`，再 `claim-next`。
5. 成本摘要：展示 `cost_summary` 的 cache hit 和按 route 聚合。
6. RAG eval：展示 `rag_eval_summary`。

**验证命令**

```powershell
.venv\Scripts\python.exe examples\interview_demo.py
```

## 5. 技术难点与解决方案

### 难点 1：低成本与实时正确性的冲突

**问题**：FAQ 高频重复，完全不缓存会浪费模型调用；但订单、物流、售后等业务查询如果缓存，会把过期状态返回给用户。

**解决方案**：

- 只对知识问答启用安全缓存。
- cache key 绑定 tenant、query、knowledge_base_id、知识版本、prompt hash 和 citation key。
- 宿主身份上下文存在时不缓存，避免用户级敏感答案串用。
- 业务查询走实时工具链路，明确 `cache_hit=false`。

**可验证结果**：`test_chat_cost_summary_and_knowledge_cache` 覆盖首次知识问答、重复知识问答、业务查询和成本摘要聚合。

### 难点 2：RAG 评测不能把“有引用”当“答对”

**问题**：本地检索兜底可能返回低分引用，如果只看 citation 数量，会误判为命中。

**解决方案**：

- eval case 同时检查 route、引用关键词和 citation score。
- `expect_effective_hit=false` 用于验证低分未命中。
- 失败明细暴露 `missing_keywords`、`route_ok`、`effective_hit_ok`。

**可验证结果**：`scripts/eval_rag.py` 输出 `rag_eval_summary`；`tests/test_interview_artifacts.py` 覆盖引用关键词失败明细。

### 难点 3：转人工要能被运营侧消费

**问题**：只告诉用户“已转人工”不够，客服主管需要知道队列顺序、技能组、风险优先级和认领人。

**解决方案**：

- `Session` 增加 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
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

## 6. STAR 表达模板

### STAR：低成本 AI 客服治理

- **S**：FAQ 高频重复但业务查询必须实时，简单统一缓存会造成错误。
- **T**：在不引入付费依赖的前提下实现成本可观测和安全缓存。
- **A**：增加 usage/cost 字段、知识问答安全缓存、业务查询不缓存、管理端成本摘要。
- **R**：本地测试可验证缓存命中、业务不缓存和成本聚合；真实节省比例待线上账单数据确认。

### STAR：RAG 质量评测

- **S**：RAG demo 容易只展示成功样例，无法解释引用缺失和低分召回。
- **T**：建立本地可复现 eval，证明评测机制而非虚构准确率。
- **A**：设计 eval cases，检查 route、引用关键词、有效命中阈值，输出失败明细。
- **R**：`scripts/eval_rag.py` 可本地复跑，当前样例通过；线上准确率需业务标注集。

### STAR：人工接管队列

- **S**：高风险和投诉类问题需要进入人工队列，且运营侧要按优先级处理。
- **T**：实现单实例轻量队列和认领链路。
- **A**：在 Session 上落队列字段，管理端提供 queue 和 claim-next，风险会话优先。
- **R**：本地测试验证排序、技能组过滤和认领状态；多实例原子认领作为 future target。

## 7. 边界与 future target

- 当前本地 JSON 存储适合开发、演示和单实例部署；多实例强一致不是当前事实。
- 当前 RAG eval 是小规模本地 case，不代表线上准确率。
- 当前成本为估算链路；真实账单需要接模型供应商 usage 与价格配置。
- Redis queue、Postgres repository、真实客服工单系统、Qdrant/OpenAI 联调均可作为下一阶段扩展，不写成已完成能力。
