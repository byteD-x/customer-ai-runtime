# TODO 精简版

> 最后更新：2026-06-07
> 本文只保留下一步要做的事项；已完成能力详见 `docs/progress-control.md`，阶段路线详见 `docs/roadmap.md`，面试表达详见 `docs/interview-playbook.md`。

## 1. 当前基线

当前本地面试基线已完成：

- 文本、语音、RTC 三端客服链路
- RAG 知识库、版本管理、健康巡检、检索失败分析
- 实时业务工具、行业适配、插件注册与启停
- Auth Bridge：API Key / Session / JWT / Custom Token / 自定义桥接
- 路由置信度分层、`intent_stack`、页面上下文感知
- 成本治理：LLM usage、usage 来源、cost 来源、可配置币种、可配置账期、可配置本地预算阈值、租户成本策略、可配置模型价格表、provider billing 样本导入、非阻断样本质量诊断、诊断样本成本差异摘要、provider billing usage token 对账摘要、知识问答安全缓存、业务查询不缓存、成本摘要
- LLM 接入治理：模型覆盖、结构化 schema、Prompt 版本历史、Prompt revision 只读摘要、安全 diff 与 prompt hash 缓存隔离
- Prompt 回滚 API：指定 revision 回滚并生成新的激活版本记录，revision 摘要和 diff 接口可暴露账本异常 issues
- RAG eval：10 个本地标注 case、多知识库样例、标注集元数据、灰度 cohort、人工复核状态、离线准确率、引用准确率、上下文 precision/recall、拒答准确率、faithfulness 分数、失败明细、可复现脚本
- RAG 文件上传解析：文本 / Markdown 已可走上传入口，PDF / Word 依赖 `providers` extra
- AgentWorkflow HTTP API：顺序工具步骤、工具白名单、步骤上限、失败停止与 trace
- 结构化交接包：情绪、问题摘要、最后用户消息、相关业务对象、页面上下文和行为信号
- 人工接管队列：`HandoffQueueBackend.enqueue` 入队契约、技能组、优先级、默认 local 单进程 `claim-next`，以及可选 SQLite 共享队列表事务认领，返回当前后端 `consistency_scope` 和本地等待时长观测字段 `queue_wait_seconds`
- 外部 readiness 脚本：OpenAI models、OpenAI Admin usage/costs、Qdrant runtime config/health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖未配置或未启用对应 provider 时返回 `skipped`，JSON 输出包含检查范围、依赖环境变量、探针类型和证据口径等审计元数据
- 线上 RAG 样本评估入口：`scripts/eval_online_rag.py` 读取脱敏 JSON/JSONL 样本并输出 `online_accuracy`
- k6 smoke 模板：`deploy/k6-smoke.js` 可对健康检查和管理端指标摘要做可复现压测入口
- 本地质量门禁修复：`scripts/test.ps1` 串联静态检查、类型检查与测试
- 面试演示与 STAR / 简历材料

## 2. 优先待办

### P0：面试可讲深度

- 当前本地可完成的 P0 面试增强项已完成；后续 P0 只接收能绑定代码、测试和面试讲述的新问题。

### P1：生产化增强

- **多实例人工队列**：当前已完成 `HandoffQueueBackend.enqueue` 入队接口化和可选 SQLite 队列表事务认领；后续继续迁移为 Redis sorted set 原子 pop 或 Postgres 行级锁认领，并补齐共享 Session 存储。
- **真实成本结算**：当前已完成租户级预算阈值、币种和账期策略配置，以及 provider billing 样本导入、非阻断样本质量诊断、摘要聚合、诊断样本成本差异展示与本地 provider billing usage token 对账摘要；后续继续接入自动 provider 账单/usage 明细拉取、账单结算系统和财务级对账。
- **外部系统联调**：在 readiness 脚本基础上，补充真实 OpenAI / Qdrant / 业务 API / 客服工单系统的端到端联调记录。
- **部署材料完善**：在现有 Docker Compose 基础上，已细化 Qdrant provider 启用、readiness 配置一致性检查和常见故障排查；后续继续补充真实环境变量模板审计、启动检查记录和外部系统联调材料。

### P2：长期能力

- **用户画像与个性化**：用户标签、历史摘要、回复风格偏好。
- **运营分析看板**：热点问题、转人工原因、时段波动、知识库效果趋势。
- **合规与审计**：敏感数据识别、内容风险、操作审计、数据保留策略。

## 3. 暂不声明为当前事实

- 线上 RAG 准确率、召回率、人工复核通过率
- 真实成本节省比例、自动 provider 账单拉取和完整租户结算
- QPS、p95/p99、SLA 等压测指标
- 多实例原子认领与生产级队列一致性
- 真实外部 provider 与业务系统联调通过

## 4. 验证命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
powershell -ExecutionPolicy Bypass -File scripts\interview-package.ps1
.venv\Scripts\python.exe scripts\eval_rag.py --json --output .codex\rag-eval-report.json
.venv\Scripts\python.exe scripts\check_external_readiness.py --json --output .codex\external-readiness-report.json
.venv\Scripts\python.exe scripts\eval_online_rag.py examples\online_rag_sample.jsonl --json --output .codex\online-rag-eval-report.json
.venv\Scripts\python.exe examples\interview_demo.py
# 可选：需要本机安装 k6 且服务已启动
k6 run deploy\k6-smoke.js
```

本地 provider 会打印估算成本和 eval 结果；readiness 脚本在缺少外部配置或未启用对应 provider 时会返回 `skipped`，并通过 `audit` 字段说明检查口径。这些结果只代表当前本地样例、输入样本、配置一致性和配置就绪态，不代表线上指标、生产压测结果或真实外部联调通过。

## 5. 维护规则

- 新增 TODO 必须能对应到具体代码、测试或文档入口。
- 已完成事项及时移出待办，转入 `docs/progress-control.md` 或面试材料。
- future target 必须显式标注，不能写成已落地能力。
- 不在本文堆长篇实现方案；复杂方案放到对应设计文档。
