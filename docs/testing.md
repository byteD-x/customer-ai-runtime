# 测试文档

## 1. 测试目标

验证平台在文本、语音、RTC、知识库、业务查询、人工协同、宿主挂载、鉴权桥接、插件装配等关键链路上的行为正确性。

## 2. 当前测试基线

当前仓库已具备基础 API 与嵌入式模块测试。随着 `Auth Bridge`、插件和业务增强落地，测试范围同步扩展到路由增强、质量反馈、知识运维与运营统计链路。

## 3. 测试分层

### 3.1 单元测试

- 路由策略插件
- 路由置信度分层
- `intent_stack` 主题切换与回退
- 文本 / 语音 / RTC 响应时延记录
- 消息反馈字段写入与转人工状态切换
- 知识库健康评分与重复切片统计
- 切片参数校验与优化建议计算
- 知识版本激活与历史版本回退
- 插件注册中心
- Auth Bridge
- Context Builder
- Knowledge Domain Manager
- Tool 参数校验
- Handoff 策略

### 3.2 集成测试

- 文本知识问答
- 文本业务查询
- 页面上下文驱动的业务路由
- “回到刚才的问题”等多轮主题回退
- 管理端按渠道汇总首响与平均响应时长
- 消息级反馈提交与 `feedback_summary` 汇总
- 用户通过 `request_human` 反馈直接生成交接包
- 转人工
- 人工接管
- 会话关闭
- 知识库导入与检索
- 管理端知识库健康报告
- 管理端检索失败聚合报告
- 管理端知识版本快照与激活切换
- 管理端切片优化建议与应用
- 管理端知识库效果分析报告
- 管理端 Prompt revision 只读摘要、安全 diff 与账本异常 issues

### 3.3 关键链路测试

- 语音轮次
- RTC WebSocket 事件链路
- 宿主挂载子应用
- 进程内 facade 调用
- Session / JWT / Custom Token 鉴权桥接
- 插件启停与回退

## 4. 建议命令

```powershell
# 快速目标化测试：默认跑 stream 链路，内置超时保护
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite auto
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite selector
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite external
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite rag
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Target "tests\test_runtime_api.py::test_chat_knowledge_stream_flow"
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Target "tests\test_runtime_api.py::test_admin_prompt_revisions_return_safe_metadata,tests\test_runtime_api.py::test_admin_prompt_diff_compares_active_revision_with_target"
# 完整本地质量门禁
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\eval_rag.py
.venv\Scripts\python.exe scripts\check_external_readiness.py --json
.venv\Scripts\python.exe scripts\eval_online_rag.py path\to\online-rag.jsonl --json
.venv\Scripts\python.exe examples\interview_demo.py
# 可选：需要本机安装 k6 且服务已启动
k6 run deploy\k6-smoke.js
```

Linux/macOS 示例：

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src tests
```

`scripts/test-fast.ps1` 用于开发中的目标化回归，不替代提交前完整门禁。当前预设：

- `auto`：根据当前 `git status` 自动选择最小 pytest 目标，包含未跟踪的新文件；无法安全归类时回退完整 `pytest tests`。
- `stream`：文本知识问答 + 流式 Chat 正常/错误事件，默认 suite。
- `api`：完整 runtime API 集成测试。
- `rag`：RAG 质量与面试材料一致性测试。
- `agent`：受控多工具工作流测试。
- `providers`：可选 provider、云厂商 speech provider 与 OpenAI prompt 组装测试。
- `smoke`：插件、路由、回复后处理和限流主体等低成本冒烟测试。
- `external`：外部 readiness 与线上 RAG 样本评估入口测试。
- `selector`：快速测试选择器自身测试。
- `full`：完整 `pytest tests`，用于显式回退验证。

脚本默认使用 `.venv\Scripts\python.exe`，如果不存在则退回 `python`；默认超时为 120 秒，可用 `-TimeoutSeconds` 调整。若超时，脚本返回退出码 `124` 并输出已捕获的 pytest stdout/stderr，便于定位卡住点。`auto` 只优化开发反馈速度，提交前仍需运行 `scripts/test.ps1`。

## 5. 验收重点

- 文本、语音、RTC 都能正常完成一轮处理
- 低置信度 / 用户要求人工时能平滑转人工
- 同一句短问在详情页与无上下文页的路由结果可区分
- `intent_stack` 能支持主题切换后再回到上一个主题
- 会话详情与管理端可查看首响和平均响应时长
- 点赞 / 点踩 / 转人工反馈可写入消息并被管理端汇总
- 知识库健康报告能输出健康分与重复切片率
- 检索未命中问题可按知识库查看 Top 查询
- 知识版本切换后，新增文档与检索命中应落在新的激活版本
- 切片优化应用后，应生成新版本并保留优化报告
- 知识库效果分析应能输出命中率、满意度与负反馈率
- 知识问答首次请求应 `cache_hit=false`，重复同一安全知识问答应 `cache_hit=true`
- 业务工具查询必须保持 `cache_hit=false`，避免缓存实时订单/售后状态
- 成本摘要应按 provider、route 聚合 token、usage 来源、币种、账期、本地预算阈值、基于本地模型价格表的估算成本和缓存命中
- Prompt revision 摘要和 diff 接口不得返回 Prompt 原文；应覆盖 unknown revision、空账本、损坏账本和 active revision 不唯一等治理异常
- 人工接管队列应按风险优先级与入队时间排序，支持按 `skill_group` 过滤认领，并返回 `queue_backend` / `atomic_claim` / `consistency_scope` 当前后端口径
- RAG eval 应覆盖 8 个本地标注 cases、多知识库、标注集元数据、灰度 cohort、人工复核状态、离线准确率、命中、低分未命中、引用关键词失败明细、`citation_accuracy`、`context_precision`、`context_recall`、`refusal_accuracy` 和 `faithfulness_score`
- Chat 知识回复缺少有效引用时应返回 `refusal=true`、`refusal_reason`、空 `citations` / `references`，避免无证据强答
- 外部 readiness 脚本在缺少 OpenAI / OpenAI Admin / Qdrant / 业务 API / 工单 API / Redis / Postgres 配置时应返回 `skipped`，配置后按真实 HTTP/TCP 探针返回 `passed` 或 `failed`
- 线上 RAG 评估脚本只读取脱敏 JSON/JSONL 样本并输出 `online_accuracy`，不能在缺少样本时宣称线上准确率
- k6 smoke 只验证当前部署的健康检查和指标摘要接口，不等同于生产 SLA 或容量上限
- 面试演示脚本应输出 `route`、`citations`、`tool_result`、`handoff_package`、`handoff_queue`、`claimed_session`、`cost_summary`、`rag_eval_summary`
- 缺失 API Key 时可由宿主桥接完成认证
- 不同行业上下文能影响路由与工具选择
- 插件禁用后有默认兜底

## 6. 当前不可验证项

- 若未配置真实 OpenAI / Qdrant / 外部业务系统，只能验证本地默认提供商链路，不能宣称外部联调已通过。
- `scripts/check_external_readiness.py` 只检查可选外部依赖配置、可达性和部分权限探针；未配置时为 `skipped`，不代表外部联调失败或通过。
- `deploy/k6-smoke.js` 是压测模板；未运行真实压测并保留输出前，不能声明 QPS、p95/p99 或 SLA。
- `scripts/eval_rag.py` 使用本地 provider 与临时存储，验证的是可重复的本地标注样例离线评测闭环；其中 `context_precision` / `context_recall` 基于本地标注关键词和返回引用文本启发式计算，用于暴露额外无关引用或上下文遗漏，不代表线上准确率。
- `scripts/eval_online_rag.py` 需要真实业务导出的脱敏标注样本；输出只代表该输入样本，不自动代表全量线上准确率。
- 当前成本为本地模型价格表估算，不代表真实 provider 账单或线上节省比例。
- `examples/interview_demo.py` 是面试演示脚本，用于串起本地闭环，不代表生产压测结果。
