# TODO 精简版

> 最后更新：2026-06-06
> 本文只保留下一步要做的事项；已完成能力详见 `docs/progress-control.md`，阶段路线详见 `docs/roadmap.md`，面试表达详见 `docs/interview-playbook.md`。

## 1. 当前基线

当前本地面试基线已完成：

- 文本、语音、RTC 三端客服链路
- RAG 知识库、版本管理、健康巡检、检索失败分析
- 实时业务工具、行业适配、插件注册与启停
- Auth Bridge：API Key / Session / JWT / Custom Token / 自定义桥接
- 路由置信度分层、`intent_stack`、页面上下文感知
- 成本治理：LLM usage、知识问答安全缓存、业务查询不缓存、成本摘要
- RAG eval：本地 case、失败明细、可复现脚本
- 单实例人工接管队列：技能组、优先级、`claim-next`
- 面试演示与 STAR / 简历材料

## 2. 优先待办

### P0：面试可讲深度

- **工具编排链路**：支持“订单状态 -> 物流轨迹 -> 售后建议”这类多工具顺序调用，并保留失败降级。
- **交接包增强**：在 handoff package 中补充情绪、问题摘要、建议回复和相关业务对象。
- **RAG eval 扩样**：增加更贴近行业场景的 eval cases，覆盖错误路由、引用缺失、低分召回和多知识库。

### P1：生产化增强

- **多实例人工队列**：将当前 Session 轻量队列迁移为 Redis sorted set 或数据库事务认领。
- **真实成本配置**：接入 provider usage、模型价格表、租户预算阈值和告警策略。
- **外部系统联调**：补充 OpenAI / Qdrant / 真实业务 API / 客服工单系统的可选联调材料。
- **部署材料完善**：细化环境变量模板、Docker Compose、启动检查和常见故障排查。

### P2：长期能力

- **用户画像与个性化**：用户标签、历史摘要、回复风格偏好。
- **运营分析看板**：热点问题、转人工原因、时段波动、知识库效果趋势。
- **合规与审计**：敏感数据识别、内容风险、操作审计、数据保留策略。

## 3. 暂不声明为当前事实

- 线上 RAG 准确率、召回率、人工复核通过率
- 真实成本节省比例和模型账单
- QPS、p95/p99、SLA 等压测指标
- 多实例原子认领与生产级队列一致性
- 真实外部 provider 与业务系统联调通过

## 4. 验证命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
.venv\Scripts\python.exe scripts\eval_rag.py
.venv\Scripts\python.exe examples\interview_demo.py
```

本地 provider 会打印估算成本和 eval 结果；这些结果只代表当前本地样例，不代表线上指标。

## 5. 维护规则

- 新增 TODO 必须能对应到具体代码、测试或文档入口。
- 已完成事项及时移出待办，转入 `docs/progress-control.md` 或面试材料。
- future target 必须显式标注，不能写成已落地能力。
- 不在本文堆长篇实现方案；复杂方案放到对应设计文档。
