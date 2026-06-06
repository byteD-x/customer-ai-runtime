# 性能口径与 SLO（当前事实 + 建议口径）

## 1. 当前已记录的数据

- 会话级：`first_response_time`、`avg_response_time`（见会话模型字段）
- 诊断级：部分事件包含 `duration_ms`（例如 `chat.completed`、`voice.turn_completed`）
- 管理接口汇总：`GET /api/v1/admin/metrics/summary` 的 `response_time_summary`
- 成本治理：`chat.cost_recorded` 诊断事件与 `GET /api/v1/admin/costs/summary`
- 缓存命中：Chat 响应字段 `cache_hit`，成本摘要中的 `cache_hits` / `cache_hit_rate`，以及管理端 `response_cache_summary`
- 人工队列：`GET /api/v1/admin/handoff/queue` 返回当前单实例等待队列
- 离线 RAG eval：`scripts/eval_rag.py` 输出 `pass_rate`、`effective_hit_rate`、`citation_accuracy`、`context_precision`、`context_recall`、`refusal_accuracy`、`faithfulness_score`、`offline_accuracy`、`reviewed_case_count`、`cohort_breakdown` 和失败明细
- 线上样本 RAG eval：`scripts/eval_online_rag.py` 读取脱敏 JSON/JSONL 标注样本并输出 `online_accuracy`，只代表输入样本
- 压测模板：`deploy/k6-smoke.js` 可对 `/healthz` 和 `admin/metrics/summary` 做 k6 冒烟压测，thresholds 是本地模板，不代表生产 SLA

说明：分位数统计（p50/p95）当前基于“最近诊断样本”（受查询上限影响），用于快速排障与趋势观察，不等同于全量离线统计口径。成本、缓存、队列、RAG eval 和 k6 smoke 当前也属于本地治理与演示口径，不代表真实账单、线上准确率或生产 SLA。

## 2. 建议的稳定口径（对齐验收）

- `turn_duration_ms`：从收到请求到返回响应（文本/语音/RTC）端到端耗时
- 分位数：至少输出 p50、p95，并明确：
  - 统计窗口（最近 N 条 / 最近 5 分钟）
  - 稳态还是冷启动
  - 是否包含外部 provider 耗时
- `estimated_cost_cents`：当前按本地模型价格表与 LLM usage 估算；若 provider 只返回 `total_tokens`，按输入侧估算成本。当前响应和诊断会显式返回 `usage_source`、`billing_currency`、`billing_period` 与 `tenant_budget_estimated_cents`，但真实账单仍需要 provider 原生账单、租户预算、币种和结算周期系统对接
- `cache_hit_rate`：仅统计安全知识问答缓存，不把实时业务查询纳入可缓存口径；`response_cache_summary` 是当前单实例内存缓存运行时统计，不代表多实例全局缓存命中率
- `handoff_wait_ms`：从 `handoff_enqueued_at` 到认领成功的等待时长，按 `skill_group` 聚合 p50/p95
- `rag_eval_pass_rate` / `offline_accuracy`：仅用于本地标注 case 回归；当前样例包含标注集元数据、灰度 cohort、人工复核状态、引用准确率、上下文 precision/recall、拒答准确率和启发式 faithfulness 分数，但线上口径仍必须基于真实业务标注集、灰度流量和人工复核
- `online_accuracy`：仅由 `scripts/eval_online_rag.py` 基于输入的脱敏线上标注样本计算，不能外推为全量线上准确率
- `http_req_duration p(95)` / `http_req_failed`：当前只在 `deploy/k6-smoke.js` 中作为可调整 smoke thresholds，生产 SLO 需以实际压测环境、并发模型、数据集和 k6 输出为准

## 3. Future Target

- 将当前内存/JSON 样本统计迁移为可持久化、可窗口聚合的指标后端。
- 在现有本地模型价格表基础上接入 provider 原生 usage、租户预算、币种和账单结算，区分模型、route 和缓存节省。
- 将单实例 handoff queue 指标迁移到多实例队列或数据库事务口径。
- 将 RAG eval 从本地标注样例和人工导出的脱敏样本扩展为真实业务标注集、线上灰度流量和反馈闭环。
