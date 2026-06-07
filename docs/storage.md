# 存储与多实例说明（当前事实 + 迁移建议）

## 1. 当前实现（当前事实）

当前仓库默认使用本地 JSON 进行状态持久化（适合开发/演示/单实例）：

- 会话：`<storage_root>/state/sessions.json`
- 知识库：`<storage_root>/state/knowledge.json`
- RTC 房间：`<storage_root>/state/rtc_rooms.json`
- 诊断事件：`<storage_root>/state/diagnostics.json`
- 运行时配置：`<storage_root>/state/runtime_config.json`

人工接管队列默认不是独立消息队列，而是复用 `Session` 状态字段形成单实例轻量队列：

- `handoff_reason`
- `handoff_skill_group`
- `handoff_priority`
- `handoff_enqueued_at`
- `assigned_operator_id`

管理端 `GET /api/v1/admin/handoff/queue` 基于当前租户的等待队列排序，并基于 `handoff_enqueued_at` 返回本地等待时长观测字段 `queue_wait_seconds`；`POST /api/v1/admin/handoff/claim-next` 认领后把会话状态切到 `human_in_service`。默认返回 `queue_backend=local`、`atomic_claim=true` 和 `consistency_scope=single_process`，其中 `atomic_claim` 只表示单进程锁内认领。设置 `CUSTOMER_AI_HANDOFF_QUEUE_BACKEND=sqlite` 后，会使用 `<storage_root>/state/handoff_queue.sqlite3` 保存等待队列表和 Session 快照，并返回 `queue_backend=sqlite`、`consistency_scope=shared_sqlite_queue`，用于验证共享队列表的事务认领。该 SQLite 后端只覆盖人工接管队列，不代表当前 JSON Session 仓储已经具备完整多实例强一致能力。

## 2. 已知限制

- 默认 `local` 后端不适合多实例并发写入与强一致需求
- SQLite 后端提供队列表事务认领，但仍依赖当前 Session 仓储同步会话状态，不等同于完整分布式存储
- 本地 JSON 仓储缺少跨进程事务与全局索引，数据量大时查询与写入会退化

## 3. 迁移建议（future target）

- 抽象 repository 接口并新增可选实现（Postgres/Redis），保留 JSON 作为 dev fallback
- 人工接管队列后续可迁移为 Redis sorted set：score 使用 `priority` 与 `enqueued_at` 组合，value 存 `tenant_id/session_id/skill_group`，认领使用原子 pop 或 Lua 脚本；也可使用 Postgres `SELECT ... FOR UPDATE SKIP LOCKED` 做队列表事务认领。当前仓库已提供可选 SQLite 队列表后端和 Redis/Postgres TCP readiness，但 Redis/Postgres 队列实现仍属于 future target。
- 采用可回滚迁移策略：
  - 只读迁移或双写一段时间
  - 明确回滚开关与数据一致性检查

