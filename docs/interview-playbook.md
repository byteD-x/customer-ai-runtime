# Customer AI Runtime 面试追问手册

> 定位：AI 平台架构 / AI 客服 Runtime。本文只记录当前仓库可验证事实；外部 OpenAI / Qdrant provider、Redis 或真实业务系统联调需配置，未验证内容统一标注为 future target。

## 1. 低成本治理：为什么能低成本跑 AI 客服？

**可讲亮点**

- 知识类问答支持安全缓存，重复命中时 `cache_hit=true`，本轮 usage 归零；业务查询不缓存，避免订单、售后等实时状态过期。
- 每轮文本请求记录 provider、model、route、token、usage 来源、币种、账期、模型价格估算成本、缓存命中和本地预算阈值；管理端可导入 provider billing 样本，并按 provider / route 分别汇总本地估算成本、账单样本金额和诊断样本差异，同时输出运行时 usage 与导入 provider billing usage 的 token 对账摘要；导入响应会返回非阻断样本质量诊断。
- 默认 `local` provider 可本地跑通；OpenAI usage 可在 provider 层透传 SDK 返回的 usage。

**代码证据**

- `src/customer_ai_runtime/application/chat.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/domain/models.py`
- `tests/test_runtime_api.py::test_chat_cost_summary_and_knowledge_cache`
- `tests/test_runtime_api.py::test_chat_cost_uses_configured_model_price_map`
- `tests/test_runtime_api.py::test_provider_billing_import_updates_cost_summary`
- `tests/test_runtime_api.py::test_provider_billing_usage_reconciliation_matches_runtime_usage`

**验证命令**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_runtime_api.py::test_provider_billing_usage_reconciliation_matches_runtime_usage
```

**面试官可能追问**

- 问：为什么只缓存知识问答，不缓存业务查询？
- 答：知识问答依赖版本化知识库和引用片段，缓存 key 绑定 tenant、query、knowledge_base_id、active version、prompt hash 和 citation key；业务查询涉及订单、物流、售后等实时数据，缓存会带来错误状态，因此强制不缓存。

- 问：成本估算是不是线上真实成本？
- 答：当前支持本地模型价格表估算，也支持把已取得的 provider billing 样本导入为 `provider.billing_recorded` 诊断事件；成本摘要会分开展示 `estimated_cost_cents`、`provider_billed_cost_cents` 和 `cost_reconciliation`，其中 `variance_cents` 只表示导入样本金额减去本地估算金额。摘要还会通过 `usage_reconciliation` 按 `tenant_id + session_id + provider + model` 对运行时 usage 与导入 provider billing usage 做 token 对账诊断，区分强匹配、未匹配和弱归因样本。导入响应中的 `quality_issue_count` / `quality_issues` 只是非阻断的本地样本质量诊断，用来提示样本归因、时间窗、币种或账期等问题。自动拉取 provider 账单、完整租户结算和线上节省比例仍是 future target，仓库不虚构线上成本指标。

## 2. RAG 质量评测：如何证明 RAG 不只是“能回答”？

**可讲亮点**

- 新增 8 个本地标注 eval cases，评估 route 是否正确、citation 是否包含期望关键词、citation score 是否达到有效命中阈值。
- eval payload 支持多知识库播种，当前覆盖 `kb_support` 和 `kb_saas`，包含行业术语和反馈回放样例。
- eval payload 带 `dataset_id`、`cohort`、`review_status` 和 `label`，汇总输出 `reviewed_case_count`、`offline_accuracy`、`citation_accuracy`、`context_precision`、`context_recall`、`refusal_accuracy`、`faithfulness_score` 与 `cohort_breakdown`。
- Chat 知识回复会输出引用来源字段，并在无有效引用时返回 `refusal=true` 和 `hallucination_check`，避免无证据强答。
- `low_score_miss` 用例用于证明“低分不算有效命中”，避免把兜底引用包装成准确命中。
- 失败明细包含 missing keywords、missing context keywords、route mismatch、effective hit mismatch，可直接指导补文档、调切片或调阈值。

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
- 答：当前仓库没有全量线上标注集和真实灰度流量，只能给可复现的本地标注样例结果；`offline_accuracy` 只表示这些本地 labeled cases 的通过率，`context_precision` / `context_recall` 只表示本地标注关键词与返回引用文本的启发式匹配，`online_accuracy` 只表示手动导入的脱敏样本。线上准确率必须基于业务标注集、灰度数据和人工复核，不能凭 demo case 虚构。

- 问：评测失败后怎么优化？
- 答：先看失败类型：route 错就调整路由策略或上下文信号；citation keyword 或 context keyword 缺失就补知识、改切片；context precision 低说明返回了额外无关引用；effective hit 低就调 embedding、召回 top_k、min_score 或切片参数。

## 3. 人工接管队列：为什么不是简单“转人工”？

**可讲亮点**

- Session 增加 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
- `handoff_package` 增加情绪、问题摘要、最后用户消息、相关业务对象、页面上下文和行为信号，便于人工客服接手。
- 队列按风险优先级倒序、同优先级按入队时间排序；支持 `skill_group` 过滤和 `claim-next`，返回 `queue_backend`、`atomic_claim=true` 与 `consistency_scope` 口径。默认 `local` 为单进程认领，可选 `sqlite` 使用共享队列表事务认领。
- 风险类关键词会进入 `risk` 技能组，认领后状态从 `waiting_human` 变为 `human_in_service`。

**代码证据**

- `src/customer_ai_runtime/application/handoff.py`
- `src/customer_ai_runtime/application/handoff_queue.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/application/session.py`
- `tests/test_runtime_api.py::test_handoff_queue_orders_and_claims_by_skill_group`
- `tests/test_runtime_api.py::test_sqlite_handoff_queue_supports_shared_transaction_claim`
- `tests/test_runtime_api.py::test_handoff_queue_can_use_sqlite_backend_from_settings`

**验证命令**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite handoff
```

**面试官可能追问**

- 问：多实例下怎么保证 claim-next 不重复？
- 答：默认 `local` 后端只保证单进程锁内认领，`consistency_scope=single_process` 明确一致性边界；可选 `sqlite` 后端把等待队列写入 `<storage_root>/state/handoff_queue.sqlite3`，使用 SQLite 事务做共享队列表认领，`consistency_scope=shared_sqlite_queue`。但它只覆盖队列层，不等于完整多实例 Session 存储；Redis sorted set / Postgres 行级锁和共享 Session 仓储仍是下一阶段。

## 4. 演示闭环：现场怎么讲？

**演示顺序**

1. 知识问答：输出 `route=knowledge` 和 `citations`。
2. 重复知识问答：输出 `knowledge_cache_hit=true`。
3. 业务查询：输出 `route=business` 和 `tool_result`，证明实时工具链路不走缓存。
4. 风险问题：输出 `handoff_package`，进入 `handoff_queue`，再 `claim-next`。
5. 成本摘要：展示 `cost_summary` 的 cache hit、usage 来源、币种、账期和按 route 聚合。
6. RAG eval：展示 `rag_eval_summary` 的标注样例、cohort、复核状态、引用准确率、上下文 precision/recall、拒答准确率、faithfulness 分数和 `offline_accuracy`。
7. Online eval：如果有脱敏 JSON/JSONL 样本，可展示 `online_accuracy`，并强调它只代表输入样本。
8. 外部 readiness：展示未配置外部凭据或未启用对应 provider 时 `overall_status=skipped`，以及 `audit` 中的检查范围、依赖环境变量、探针类型和证据口径；Qdrant 场景可用 `qdrant_runtime_config` 区分应用是否选择 Qdrant provider 与 URL 是否配置，强调不冒充真实端到端联调通过。
9. k6 smoke：服务已启动且本机安装 k6 时，可用模板验证健康检查与指标摘要接口，不把模板阈值当生产 SLA。

**验证命令**

```powershell
.venv\Scripts\python.exe examples\interview_demo.py
.venv\Scripts\python.exe scripts\check_external_readiness.py --json
.venv\Scripts\python.exe scripts\eval_online_rag.py path\to\online-rag.jsonl --json
# 可选：需要本机安装 k6 且服务已启动
k6 run deploy\k6-smoke.js
```

当前本地实测基线以本节验证命令输出为准；该结果只代表当前本地样例、输入样本、配置一致性和外部依赖配置就绪态，不代表线上准确率、真实成本节省、生产 SLA 或外部 provider 端到端联调结果。

## 5. Prompt 版本与回滚：如何降低提示词改坏的风险？

**可讲亮点**

- Prompt 更新会形成版本历史，记录 revision、变更摘要和激活状态，便于解释“为什么这次回答策略变了”。
- Prompt hash 已进入知识问答缓存 key，避免 Prompt 变更后复用旧缓存答案。
- `GET /api/v1/admin/prompts/revisions` 可查看只读 revision 摘要，返回字段长度和 hash，不暴露 Prompt 原文。
- `GET /api/v1/admin/prompts/{revision}/diff` 可对比 active revision 与目标 revision，输出字段级变化、长度差和 hash 差异。
- 回滚 API 为 `POST /api/v1/admin/prompts/{revision}/rollback`，用于把历史版本恢复为新的激活版本，并保留完整 revision 审计链。

**代码证据**

- `src/customer_ai_runtime/application/runtime.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/api/routes.py`
- `tests/test_runtime_api.py`

**面试官可能追问**

- 问：为什么回滚不是直接覆盖当前 Prompt？
- 答：回滚也应生成一条新版本记录，这样审计链路能看到从哪个 revision 回退、谁触发、原因是什么；直接覆盖会丢失事故复盘线索。

- 问：为什么 diff 接口不直接返回 Prompt 原文？
- 答：系统提示词和运营提示词可能包含内部策略，审计接口只需要证明“哪些字段变了、长度和 hash 如何变化”；原文继续留在受权限保护的配置视图里，降低扩散面。

## 6. 受控 Agent 工具流：为什么不是开放式 Agent？

**可讲亮点**

- 工具流使用显式 `steps`、`allowed_tools` 和 `max_steps`，只允许调用白名单工具，避免模型自由规划导致越权或循环调用。
- 每一步保留 plan、phase、observation、失败状态和最终摘要，适合面试演示“订单状态 -> 物流轨迹 -> 售后建议”这类确定性链路。
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

**可验证结果**：`test_chat_cost_summary_and_knowledge_cache` 覆盖首次知识问答、重复知识问答、业务查询、usage 来源、币种、账期、本地预算阈值和成本摘要聚合；`test_chat_cost_uses_configured_model_price_map` 覆盖本地模型价格表。

### 难点 2：RAG 评测不能把“有引用”当“答对”

**问题**：本地检索兜底可能返回低分引用，如果只看 citation 数量，会误判为命中。

**解决方案**：

- eval case 同时检查 route、引用关键词、上下文关键词和 citation score，并覆盖多知识库、行业术语、反馈回放和低分未命中。
- case 带本地标注集元数据、cohort 和人工复核状态，汇总输出 `offline_accuracy` 与 cohort breakdown。
- `expect_effective_hit=false` 用于验证低分未命中。
- 失败明细暴露 `missing_keywords`、`missing_context_keywords`、`route_ok`、`effective_hit_ok`、`citation_accuracy`、`context_precision`、`context_recall`、`refusal_ok` 和 `faithfulness_score`。

**可验证结果**：`scripts/eval_rag.py` 输出 `rag_eval_summary`；`tests/test_interview_artifacts.py` 覆盖引用关键词失败明细、上下文 precision/recall、标注样例字段、人工复核计数和 `offline_accuracy`。

### 难点 3：转人工要能被运营侧消费

**问题**：只告诉用户“已转人工”不够，客服主管需要知道队列顺序、技能组、风险优先级和认领人。

**解决方案**：

- `Session` 增加 handoff reason、skill group、priority、enqueued_at、assigned_operator_id。
- `HandoffPackage` 补充 sentiment、issue_summary、last_user_message、related_business_objects、page_context、behavior_signals。
- 管理端 queue 按 priority 倒序、同优先级按入队时间排序。
- `claim-next` 认领后切换为 `human_in_service` 并记录 operator，队列响应带 `queue_backend`、`atomic_claim` 和 `consistency_scope` 口径。

**可验证结果**：`test_handoff_queue_orders_and_claims_by_skill_group` 覆盖风险优先、技能组过滤和认领状态；SQLite 后端测试覆盖共享队列表排序、过滤、事务认领和容器配置选择。

### 难点 4：面试演示必须可复现

**问题**：外部 OpenAI、Qdrant、真实订单系统都可能因为配置或网络不可用导致现场演示失败。

**解决方案**：

- 演示默认使用本地 LLM / Vector / Business provider。
- 脚本使用临时 storage，不污染本地状态。
- 输出稳定字段，便于面试时按字段讲架构。
- 外部 readiness 脚本独立检查 OpenAI models、OpenAI Admin usage/costs、Qdrant runtime config/health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖；缺少配置或未启用对应 provider 时返回 `skipped`，配置不一致或探针失败时返回 `failed`，并通过 `audit` 字段说明检查范围、依赖环境变量、探针类型和证据口径，不误报联调通过。

**可验证结果**：`.venv\Scripts\python.exe examples\interview_demo.py` 退出码为 0，输出关键段落；`.venv\Scripts\python.exe scripts\check_external_readiness.py --json` 在未配置外部凭据或未启用对应 provider 时输出 `skipped` 和 `audit` 元数据。

## 8. STAR 表达模板

### STAR：低成本 AI 客服治理

- **S**：FAQ 高频重复但业务查询必须实时，简单统一缓存会造成错误。
- **T**：在不引入付费依赖的前提下实现成本可观测和安全缓存。
- **A**：增加 usage/cost、usage 来源、cost 来源、币种、账期、本地预算阈值字段、模型价格表估算、provider billing 样本导入、非阻断样本质量诊断、诊断样本成本差异摘要、usage token 对账摘要、知识问答安全缓存、业务查询不缓存、管理端成本摘要。
- **R**：本地测试可验证缓存命中、业务不缓存、价格表估算、provider billing 样本导入、质量问题提示、成本聚合、样本金额对账差异和 usage token 对账差异；真实节省比例待线上账单数据确认。

### STAR：RAG 质量评测

- **S**：RAG demo 容易只展示成功样例，无法解释引用缺失和低分召回。
- **T**：建立本地可复现 eval，证明评测机制而非虚构准确率。
- **A**：设计 8 个带 dataset、cohort、review_status 和 label 的 eval cases，检查 route、引用关键词、上下文 precision/recall、有效命中阈值、拒答期望和 faithfulness 分数，输出失败明细，并覆盖多知识库与反馈回放。
- **R**：`scripts/eval_rag.py` 可本地复跑，当前本地标注样例通过；线上准确率需业务标注集。

### STAR：人工接管队列

- **S**：高风险和投诉类问题需要进入人工队列，且运营侧要按优先级处理。
- **T**：实现单实例轻量队列和认领链路。
- **A**：在 Session 上落队列字段，生成结构化交接包，管理端提供 queue 和 claim-next，风险会话优先。
- **R**：本地测试验证排序、技能组过滤和认领状态；多实例原子认领作为 future target。

### STAR：Prompt 治理与受控工具流

- **S**：Prompt 调整和多工具自动化都可能引入回答漂移、越权调用或难以复盘的问题。
- **T**：在不宣称线上指标的前提下，补齐本地可解释的 Prompt 版本历史和受控工具编排设计。
- **A**：Prompt 更新记录 revision，缓存 key 绑定 prompt hash；只读 revision 摘要和安全 diff 仅暴露长度与 hash，并通过 `issues` 标记空账本、损坏账本和 active 不唯一；工具流限制白名单、步骤上限和失败降级，并保留审计轨迹。
- **R**：本地测试覆盖 Prompt 回滚、revision 摘要、安全 diff、异常账本 issues、受控工具流 trace、禁用工具拦截与步骤上限，适合作为面试中的治理设计讲点。

## 9. 边界与 future target

- 当前本地 JSON 存储适合开发、演示和单实例部署；多实例强一致不是当前事实。
- 当前 RAG eval 是本地标注样例，online eval 只代表导入的脱敏样本，不代表全量线上准确率。
- 当前成本支持本地模型价格表估算、provider billing 样本导入、非阻断样本质量诊断、诊断样本成本差异摘要和 `usage_reconciliation` token 对账摘要，并显式暴露 usage 来源、cost 来源、币种、账期和本地预算阈值；自动 provider 账单拉取、完整租户结算和线上节省比例仍是 future target。
- 当前 `queue_backend=local`、`consistency_scope=single_process` 只代表单进程锁内认领边界；`queue_backend=sqlite`、`consistency_scope=shared_sqlite_queue` 只代表共享 SQLite 队列表事务认领，不代表完整多实例 Session 存储强一致。
- Redis queue、Postgres repository、共享 Session 存储、真实客服工单系统、Qdrant/OpenAI 端到端联调和生产压测均可作为下一阶段扩展，不写成已完成能力。
