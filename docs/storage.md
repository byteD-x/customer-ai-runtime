# 存储与多实例说明（当前事实 + 迁移建议）

## 1. 当前实现（当前事实）

当前仓库默认使用本地 JSON 进行状态持久化（适合开发/演示/单实例）：

- 会话：`<storage_root>/state/sessions.json`
- 知识库：`<storage_root>/state/knowledge.json`
- RTC 房间：`<storage_root>/state/rtc_rooms.json`
- 诊断事件：`<storage_root>/state/diagnostics.json`
- 运行时配置：`<storage_root>/state/runtime_config.json`

人工接管队列当前不是独立消息队列，而是复用 `Session` 状态字段形成单实例轻量队列：

- `handoff_reason`
- `handoff_skill_group`
- `handoff_priority`
- `handoff_enqueued_at`
- `assigned_operator_id`

管理端 `GET /api/v1/admin/handoff/queue` 基于当前租户的 `waiting_human` 会话做内存排序；`POST /api/v1/admin/handoff/claim-next` 认领后把会话状态切到 `human_in_service`。当前返回 `queue_backend=local`、`atomic_claim=true` 和 `consistency_scope=single_process`，其中 `atomic_claim` 只表示单进程锁内认领，`consistency_scope` 明确该一致性边界，不代表多实例队列一致性。该实现适合本地演示、单实例部署和面试项目验证。

## 2. 已知限制

- 不适合多实例并发写入与强一致需求
- 缺少事务与索引，数据量大时查询与写入会退化

## 3. 迁移建议（future target）

- 抽象 repository 接口并新增可选实现（Postgres/Redis），保留 JSON 作为 dev fallback
- 人工接管队列可迁移为 Redis sorted set：score 使用 `priority` 与 `enqueued_at` 组合，value 存 `tenant_id/session_id/skill_group`，认领使用原子 pop 或 Lua 脚本；也可使用 Postgres `SELECT ... FOR UPDATE SKIP LOCKED` 做队列表事务认领。当前仓库只提供 Redis/Postgres TCP readiness，不落地多实例队列实现。
- 采用可回滚迁移策略：
  - 只读迁移或双写一段时间
  - 明确回滚开关与数据一致性检查

