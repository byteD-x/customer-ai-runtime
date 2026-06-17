# 岗位数据驱动的项目增强方案

> 目标项目：`E:\Project\customer-ai-runtime`  
> 岗位数据源：`E:\Project\resume-new`  
> 数据快照：`normalized-jobs.json` 记录 `snapshotDate=2026-06-11`  
> 生成目的：把岗位数据、当前仓库事实、增强路线和面试包装对齐到同一份可执行材料。

## 0. 关键假设与边界

- 用户请求中的目标项目路径模板未填写；本文基于当前工作区，将 `E:\Project\customer-ai-runtime` 视为目标项目。
- `E:\Project\resume-new` 仅作为岗位数据源读取，不作为目标项目代码，不在本文任务中修改。
- 当前标准化岗位数据以 `E:\Project\resume-new\data\jobs\normalized-jobs.json` 为准：`meta.sampleCount=332`，实际 `jobs.length=332`。
- 岗位源项目中部分历史文档仍写 333 条；扩容记录还提到 383 条，但当前 `normalized-jobs.json` 与 `job-market-stats.json` 尚未体现 383 条口径。本文统计只使用当前标准化 JSON 的 332 条。
- 本文不宣称线上准确率、真实成本节省、生产 SLA 或外部 provider 端到端联调结果；这些只能在真实凭据、真实样本和真实运行输出存在后补充。

## 1. 岗位数据画像

### 1.1 样本总览

| 维度 | 结论 |
| --- | --- |
| 岗位总数 | 332 |
| 数据来源 | 12 个公开来源平台 |
| 样本范围 | 已按本科、2025 届、约 1 年经验背景筛选；移除了学历硬卡、5 年以上硬卡和明显纯算法/CV/语音方向岗位 |
| 全局数据风险 | 332 条 `verificationStatus` 均为“需人工核验”；332 条薪资解析均为“需人工核验” |

### 1.2 来源平台分布

| 来源平台 | 样本数 | 占比 |
| --- | ---: | ---: |
| Boss直聘 | 172 | 51.8% |
| 智联招聘 | 71 | 21.4% |
| 猎聘 | 66 | 19.9% |
| 实习僧 | 6 | 1.8% |
| 牛客网 | 5 | 1.5% |
| 企业官网 | 5 | 1.5% |
| 其他公开来源 | 7 | 2.1% |

### 1.3 城市分布

| 城市 | 样本数 | 占比 |
| --- | ---: | ---: |
| 上海 | 86 | 25.9% |
| 北京 | 48 | 14.5% |
| 深圳 | 37 | 11.1% |
| 杭州 | 30 | 9.0% |
| 广州 | 19 | 5.7% |
| 成都 | 13 | 3.9% |
| 南京 | 12 | 3.6% |
| 长沙 | 12 | 3.6% |
| 苏州 | 11 | 3.3% |
| 合肥 | 9 | 2.7% |

结论：上海、北京、深圳、杭州仍是主投城市；广州、成都、南京、长沙、苏州适合作为补充池。二线城市样本要更重视 JD 深度和外包属性核验。

### 1.4 薪资阶段分布

| 薪资阶段 | 样本数 | 占比 |
| --- | ---: | ---: |
| 主投 15-25K | 153 | 46.1% |
| 进阶 25-40K | 65 | 19.6% |
| 保底 7-15K | 49 | 14.8% |
| 冲刺 40K+ | 42 | 12.7% |
| 实习/日薪 | 21 | 6.3% |
| 不确定 | 2 | 0.6% |

项目包装应优先服务 15-25K 与 25-40K：前者看端到端交付，后者看系统设计、评测、稳定性、成本、安全和可观测。

### 1.5 经验与学历分布

| 经验要求 | 样本数 | 占比 |
| --- | ---: | ---: |
| 3-5年 | 114 | 34.3% |
| 1-3年 | 70 | 21.1% |
| 未明确 | 52 | 15.7% |
| 经验不限 | 39 | 11.7% |
| 实习 | 18 | 5.4% |

| 学历要求 | 样本数 | 占比 |
| --- | ---: | ---: |
| 本科 | 306 | 92.2% |
| 大专 | 8 | 2.4% |
| 统招本科 | 8 | 2.4% |
| 学历不限 | 7 | 2.1% |
| 未明确 | 3 | 0.9% |

结论：学历不是主要短板；主要挑战在于用项目复杂度弥补 3-5 年岗位对工程成熟度和系统边界的期待。

### 1.6 投递优先级分布

| 匹配等级 | 样本数 | 占比 |
| --- | ---: | ---: |
| 强投 | 137 | 41.3% |
| 可投 | 77 | 23.2% |
| 冲刺 | 48 | 14.5% |
| 可投/冲刺 | 15 | 4.5% |
| 强投/冲刺 | 14 | 4.2% |
| 其他复合或低优先级 | 41 | 12.3% |

主投策略应以强投和可投为基本盘，少量穿插冲刺岗位；不建议为了 40K+ 岗位把项目硬改成算法训练或推理底层项目。

### 1.7 主要岗位方向分布

| 标准方向 | 样本数 | 占比 |
| --- | ---: | ---: |
| AI应用/RAG | 106 | 31.9% |
| AI Agent/智能体 | 104 | 31.3% |
| Python/FastAPI后端 | 52 | 15.7% |
| AI平台/模型服务化 | 26 | 7.8% |
| Dify/Coze/MCP/工作流 | 5 | 1.5% |
| 内容生成/多媒体AI | 5 | 1.5% |
| 算法/微调/RL | 4 | 1.2% |
| 行业AI实施/解决方案 | 2 | 0.6% |
| Java后端+AI | 2 | 0.6% |

最值得围绕当前项目强化的方向是：AI应用/RAG、AI Agent/智能体、Python/FastAPI后端、AI平台/模型服务化。Dify/Coze/MCP 可以作为工作流与工具协议补充，不建议单独变成主线。

### 1.8 数据质量风险

- 所有标准化岗位均需人工核验，不能把来源链接、薪资、是否仍在招、是否外包、JD 完整度当成已确认事实。
- 薪资字段均标记为需人工核验，不能基于当前 JSON 直接推导 offer 区间。
- 部分样本来自公开搜索列表页或摘要，可能存在 JD 不完整、岗位已下线、活跃信号不等于发布时间等问题。
- 冲刺岗位中的 3-5 年、平台化、算法或高薪岗位需要逐条确认是否真实适合当前背景。

## 2. 重点岗位方向拆解

### 2.1 AI应用/RAG

- 样本规模：106 条，占 31.9%，为第一主投方向。
- 常见标题：AI应用开发工程师、大模型应用开发工程师、RAG方向 Python 后端、LLM 应用开发工程师。
- 常见技术关键词：RAG、知识库、向量检索、Embedding、rerank、引用溯源、拒答、RAG eval。
- 常见业务场景：企业知识库、智能客服、售后政策问答、内部知识助手、行业知识检索。
- 必备能力：文档入库、切片、检索、引用、拒答、权限隔离、接口化服务。
- 加分能力：检索失败分析、faithfulness、citation alignment、golden dataset、回归测试。
- 当前项目可承接能力：`KnowledgeService`、`HallucinationCheckService`、`scripts/eval_rag.py`、`examples/rag_eval_cases.json`、引用与拒答测试。
- 不建议硬凑：复杂微调、端到端训练、视觉模型训练。

### 2.2 AI Agent/智能体

- 样本规模：104 条，占 31.3%；若合并 Planning/Memory/Tool-use 编排相邻样本，约 105 条。
- 常见标题：AI Agent 开发工程师、Agent 全栈工程师、智能体应用开发工程师、商业增长 AI-agent 后端。
- 常见技术关键词：工具调用、任务拆解、工作流编排、记忆、trace、人工接管、interrupt/resume。
- 常见业务场景：客服工具流、订单查询、售后处理、内部流程自动化、运营协同。
- 必备能力：工具白名单、参数校验、失败停止、步骤轨迹、权限控制。
- 加分能力：checkpoint、人机协同、可恢复执行、长任务状态管理。
- 当前项目可承接能力：`AgentWorkflowService`、`POST /api/v1/agents/tool-workflow`、`tests/test_agent_workflow.py`、人工接管队列。
- 不建议硬凑：完全自主 Agent、任意工具调用、无权限边界的开放式执行。

### 2.3 Python/FastAPI后端

- 样本规模：52 条，占 15.7%。
- 常见标题：Python后端、FastAPI 后端开发、大模型方向后端开发、AI 后端工程师。
- 常见技术关键词：FastAPI、API 设计、异步、SSE、数据库、缓存、限流、测试。
- 常见业务场景：AI 服务 API、知识库管理、任务平台、业务系统集成。
- 必备能力：Pydantic schema、认证鉴权、错误响应、接口测试、部署脚本。
- 加分能力：速率限制、可观测、分组测试、自动选择快速测试。
- 当前项目可承接能力：FastAPI 路由、`pyproject.toml`、`scripts/test-fast.ps1`、测试套件、Dockerfile。
- 不建议硬凑：为展示而新增前端 UI 或复杂后台管理页。

### 2.4 AI平台/模型服务化

- 样本规模：26 条，占 7.8%；若合并 Model Serving、AI 服务网关等相邻方向，约 29 条。
- 常见标题：AI 平台开发工程师、模型服务化工程师、AI MaaS 平台开发、AI 服务网关。
- 常见技术关键词：provider 接入、模型路由、成本统计、健康检查、限流、降级、token usage。
- 常见业务场景：企业模型接入层、统一模型网关、成本治理、外部依赖 readiness。
- 必备能力：模型 provider 抽象、配置管理、健康检查、成本与 token 统计。
- 加分能力：账单样本对账、预算阈值、readiness 审计、provider fallback。
- 当前项目可承接能力：OpenAI/local provider、模型价格表、provider billing 样本导入、`check_external_readiness.py`、限流配置。
- 不建议硬凑：大规模微服务拆分、GPU 集群调度、推理框架优化。

### 2.5 Dify/Coze/MCP/工作流

- 样本规模：5 条，占 1.5%；若合并 AI 工作流/营销自动化，约 6 条。
- 常见标题：Dify AI 开发、AI 工作流工程师、MCP 工具接入工程师。
- 常见技术关键词：工作流节点、工具、知识库配置、插件、API、MCP。
- 常见业务场景：低代码 AI 工作流、营销自动化、内部流程编排。
- 必备能力：理解工具和知识库底层链路，能把工作流输出接回业务系统。
- 加分能力：MCP 安全边界、只读工具、审计、失败兜底。
- 当前项目可承接能力：插件注册、受控工具流、业务工具 API。
- 不建议硬凑：把项目改成 Dify/Coze 平台本身。

### 2.6 Java后端+AI

- 样本规模：2 条，占 0.6%；标题中 Java 相关样本仍可作为补充池。
- 常见标题：Java开发工程师（AI-agent）、中高级 Java 开发工程师（AI 应用优先）。
- 常见技术关键词：Spring Boot、状态机、事务、幂等、业务系统、AI 能力嵌入。
- 当前项目可承接能力：当前仓库主栈不是 Java，但可以在面试中把 AI Runtime 与已有 Java 后端经验组合讲。
- 不建议硬凑：在本 Python 仓库新增 Java 服务。

### 2.7 行业AI实施/解决方案

- 样本规模：2 条；若合并智能制造、内部系统 AI、财务知识库、智能客服等相邻方向，约 9 条。
- 常见标题：AI 解决方案工程师、行业 AI 实施、智能客服方案工程师。
- 常见技术关键词：业务对象、行业适配、知识库、工具调用、交付文档、客户现场问题。
- 当前项目可承接能力：行业适配器、业务工具、智能客服、宿主系统挂载。
- 不建议硬凑：只写方案不提供本地可验证演示。

### 2.8 算法/微调/RL 或多模态

- 样本规模：算法/微调/RL 4 条；合并内容生成、多媒体、AI 视频、深度学习应用等相邻方向约 12 条。
- 常见标题：算法工程师、大模型算法工程师、多模态应用开发。
- 常见技术关键词：微调、RL、训练、推理、多模态、模型评估。
- 当前项目可承接能力：应用层 eval、模型接入和服务治理。
- 不建议硬凑：纯算法训练、RLHF、视觉模型训练、推理算子优化。

## 3. 高频能力模型

| 层级 | 能力维度 | 岗位依据 | 当前项目状态 |
| --- | --- | --- | --- |
| 主投必备 | RAG 基础链路 | AI应用/RAG 106 条 | 已有知识库、检索、引用、拒答、eval |
| 主投必备 | Agent 工具调用 | AI Agent 104 条 | 已有受控工具流、trace、失败停止 |
| 主投必备 | FastAPI 后端 API | Python/FastAPI 52 条 | 已有 FastAPI、schema、鉴权、测试 |
| 主投必备 | 权限与多租户 | 企业知识库和客服类岗位共性要求 | 已有 `tenant_id`、API Key、宿主桥接 |
| 主投必备 | 本地演示闭环 | 投递和面试要求可讲可验 | 已有 `examples/interview_demo.py` |
| 进阶强化 | RAG 评测 | 25-40K 关注质量闭环 | 已有 8 个 eval cases 和失败明细 |
| 进阶强化 | 成本治理 | 平台化岗位关注 usage 和成本 | 已有 token usage、成本摘要、账单样本导入 |
| 进阶强化 | 可观测性 | Agent/RAG 工程化岗位高频追问 | 已有 diagnostics、metrics、step trace |
| 进阶强化 | 稳定性治理 | 高薪岗位关注超时、限流、降级 | 已有限流、readiness、测试脚本；熔断和降级可继续补 |
| 冲刺加分 | Provider 抽象和模型路由 | AI平台/模型服务化 26 条 | 已有 local/OpenAI/语音/向量 provider，路由仍偏静态 |
| 冲刺加分 | 外部依赖 readiness | 平台工程和交付岗位加分 | 已有 readiness 脚本，外部联调需真实环境 |
| 冲刺加分 | 行业方案表达 | 行业 AI 实施和解决方案岗位 | 已有行业适配，需按行业补演示材料 |

## 4. 目标项目分析

### 4.1 技术栈

- Python 3.13+
- FastAPI、Pydantic、pydantic-settings
- OpenAI、Qdrant、Pinecone、Milvus 等可选 provider
- structlog、OpenTelemetry API/SDK、tenacity
- pytest、pytest-asyncio、ruff、mypy
- Dockerfile、docker-compose、k6 smoke 模板

### 4.2 当前核心功能

- 文本客服、语音轮次、RTC 实时通话。
- 多租户知识库、文档上传、切片、版本管理、检索、引用。
- RAG 拒答、启发式 faithfulness 检查、本地离线评测。
- 业务工具插件、行业适配、宿主系统鉴权桥接。
- 受控 Agent 工具流，支持白名单、最大步骤、失败停止和 trace。
- 人工接管、交接包、local/SQLite 队列认领。
- 成本治理、usage 记录、provider billing 样本导入和对账摘要。
- readiness 检查、面试演示脚本、快速测试脚本。

### 4.3 已有岗位匹配点

| 岗位方向 | 当前项目证据 |
| --- | --- |
| AI应用/RAG | `src/customer_ai_runtime/application/chat.py`、`rag_quality.py`、`evaluation.py`、`scripts/eval_rag.py`、`tests/test_rag_quality.py` |
| AI Agent/智能体 | `src/customer_ai_runtime/application/agent_workflow.py`、`tests/test_agent_workflow.py`、`docs/interview-playbook.md` |
| Python/FastAPI后端 | `src/customer_ai_runtime/api/routes.py`、`pyproject.toml`、`tests/test_runtime_api.py` |
| AI平台/模型服务化 | `providers/`、`core/config.py`、`scripts/check_external_readiness.py`、成本摘要相关测试 |
| 行业AI解决方案 | `application/business.py`、`application/plugins.py`、行业适配与业务工具示例 |

### 4.4 关键缺口

- 项目能力已经很多，但岗位数据驱动的“优先级取舍”不够集中；面试时容易讲散。
- 模型路由当前更适合讲静态策略和治理入口，不适合夸成完整模型网关。
- RAG eval 是本地标注样例，不应包装成线上准确率。
- readiness 脚本能说明外部依赖配置和可达性，不等于真实外部系统端到端业务联调。
- Dify/Coze 直接经验不强，适合用“底层工作流和工具能力可迁移”表达，不适合写成主项目能力。

### 4.5 最适合包装的岗位作品定位

第一定位：企业级 AI 客服 Runtime（AI应用/RAG + Agent 工程化）。  
第二定位：Python/FastAPI AI 后端服务。  
第三定位：AI 平台/模型服务治理参考实现。  
不建议主打：纯算法、微调、RLHF、多模态训练、GPU 集群调度。

## 5. 按优先级排序的增强方案

### P0-1 补齐岗位数据驱动的项目讲法

- 优化目标：把项目从“功能很多”收敛成“AI 客服 RAG + Agent 工程化闭环”。
- 对应岗位要求：RAG、Agent、FastAPI、评测、可观测、成本、人工兜底。
- 对应岗位方向：AI应用/RAG、AI Agent、Python/FastAPI 后端。
- 修改范围：文档与面试材料。
- 实现思路：新增本文档，明确岗位数据、项目证据、主投关键词、面试讲法和验证命令。
- 为什么值得做：岗位样本中 AI应用/RAG 与 AI Agent 合计超过 60%，这是最高收益的包装方向。
- 为什么不过度设计：不改核心代码，不新增依赖，只整理已有事实。
- 验证方式：阅读本文档；运行关键测试和 demo。
- 简历表达价值：能把 RAG、Agent、评测、成本治理和人工接管讲成一条链路。
- 面试讲述价值：回答“为什么不是 Demo”“怎么验证质量”“失败怎么办”。
- 预计耗时：0.5-1 天。
- 风险和限制：不能替代真实线上指标。

### P0-2 固化本地演示闭环

- 优化目标：让面试现场能快速展示 route、citations、tool_result、handoff、cost_summary、rag_eval_summary。
- 对应岗位要求：可演示、可验证、能解释业务闭环。
- 对应岗位方向：AI应用/RAG、Agent、后端工程。
- 修改范围：优先使用 `examples/interview_demo.py`、`scripts/eval_rag.py`、README 演示段落。
- 实现思路：默认使用 local provider 和临时 storage；保留 JSON 输出用于录屏或面试展示。
- 为什么值得做：比新增功能更直接提高可信度。
- 为什么不过度设计：复用已有脚本，不引入新服务。
- 验证方式：`.venv\Scripts\python.exe examples\interview_demo.py --json`。
- 简历表达价值：可写“通过本地演示脚本串联知识问答、业务工具、转人工、成本摘要与 RAG eval”。
- 面试讲述价值：能现场解释每个字段的业务含义。
- 预计耗时：0.5 天。
- 风险和限制：只代表本地样例，不代表线上准确率。

### P1-1 强化 RAG 评测与 badcase 分析

- 优化目标：把 RAG 从“能答”强化为“能评、能复盘、能回归”。
- 对应岗位要求：Recall@K、faithfulness、citation alignment、golden dataset、badcase。
- 对应岗位方向：AI应用/RAG、AI平台。
- 修改范围：`examples/rag_eval_cases.json`、`scripts/eval_rag.py`、`tests/test_interview_artifacts.py`。
- 实现思路：在现有 8 个本地 cases 基础上补更多行业样例和失败类型；输出 `badcase_categories`、`suggested_actions` 与汇总级 `badcase_breakdown`。
- 为什么值得做：25-40K 岗位会追问质量闭环。
- 为什么不过度设计：先扩样例和失败分类，不引入复杂评测平台。
- 验证方式：`.venv\Scripts\python.exe scripts\eval_rag.py --json`。
- 简历表达价值：可写“建立本地标注评测集，覆盖引用、拒答、上下文 precision/recall、失败分类与修复建议”。
- 面试讲述价值：能讲清如何定位检索、引用或拒答问题。
- 预计耗时：1-2 天。
- 风险和限制：指标仍是本地样例，不是线上全量。

### P1-2 补模型路由和稳定性治理口径

- 优化目标：更好承接 AI平台/模型服务化岗位。
- 对应岗位要求：provider 抽象、模型路由、限流、降级、成本统计、健康检查。
- 对应岗位方向：AI平台/模型服务化。
- 修改范围：`application/chat.py`、`providers/`、`scripts/check_external_readiness.py`、相关测试。
- 实现思路：优先补路由策略文档和测试口径；代码层只在确有必要时加最小模型策略选择。
- 为什么值得做：进阶岗位最关心服务治理和边界。
- 为什么不过度设计：不拆模型网关，不做微服务化。
- 验证方式：provider、costs、external suite。
- 简历表达价值：可写“实现 provider readiness 与成本对账样本入口”。
- 面试讲述价值：能说明哪些已验证、哪些依赖真实外部系统。
- 预计耗时：2-3 天。
- 风险和限制：真实 provider 联调需要凭据和网络。

### P2-1 行业场景演示包

- 优化目标：强化行业 AI 实施、解决方案岗位适配。
- 对应岗位要求：业务对象、行业知识库、工具调用、人工兜底。
- 对应岗位方向：行业AI实施/解决方案、智能客服。
- 修改范围：`examples/`、`docs/interview-playbook.md`。
- 实现思路：围绕电商售后或 SaaS 工单补演示数据、业务对象和问答脚本。
- 为什么值得做：能把抽象 AI 能力落到具体业务场景。
- 为什么不过度设计：只补样例和演示，不扩后台管理系统。
- 验证方式：`examples/interview_demo.py --json`。
- 简历表达价值：可写“覆盖电商售后知识问答、订单查询、风险转人工场景”。
- 面试讲述价值：能回答业务落地而非只讲技术名词。
- 预计耗时：1-2 天。
- 风险和限制：不能编造真实客户或线上收益。

## 6. 三个实施版本

### 6.1 轻量版：1 天内完成

- 任务列表：
  - 新增本文档。
  - 运行 `compileall`、RAG/Agent 相关测试。
  - 跑一次 `examples/interview_demo.py --json` 或 `scripts/eval_rag.py --json`，保存本地输出摘要。
- 修改文件范围：
  - `docs/job-driven-enhancement-plan.md`
- 验收标准：
  - 能 3 分钟讲清项目定位、RAG 链路、Agent 工具流、评测与人工兜底。
  - 有本地命令证明关键链路可运行。
- 本地验证命令：
  - `.venv\Scripts\python.exe -m compileall -q src tests`
  - `.venv\Scripts\python.exe -m pytest tests\test_agent_workflow.py tests\test_rag_quality.py tests\test_interview_artifacts.py -q`
  - `.venv\Scripts\python.exe examples\interview_demo.py --json`
- 可写进简历的成果：
  - “整理岗位数据驱动的 AI 客服 Runtime 项目包装，形成 RAG、Agent、评测、成本治理和人工接管的可验证面试材料。”
- 不做什么：
  - 不做 Dify/Coze 重写，不做 UI，不做微调；因为 1 天内最大收益是材料收敛和验证闭环。

### 6.2 标准版：2-5 天完成

- 任务列表：
  - 扩充 RAG eval cases 到更多行业问题。
  - 增加 badcase 分类和失败修复建议。
  - 补一份行业演示数据和流程脚本。
  - 对 README、interview playbook 做少量交叉引用。
- 修改文件范围：
  - `examples/rag_eval_cases.json`
  - `scripts/eval_rag.py`
  - `tests/test_interview_artifacts.py`
  - `docs/interview-playbook.md`
- 验收标准：
  - eval 能输出失败明细和分类。
  - demo 能稳定展示知识问答、业务工具、转人工、成本摘要。
- 本地验证命令：
  - `.venv\Scripts\python.exe scripts\eval_rag.py --json`
  - `powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite rag`
  - `.venv\Scripts\python.exe examples\interview_demo.py --json`
- 可写进简历的成果：
  - “基于本地标注集搭建 RAG 回归评测，覆盖引用、拒答、faithfulness、上下文 precision/recall 和 badcase 明细。”
- 不做什么：
  - 不做完整 LLMOps 平台；当前目标是作品可信度和面试可讲性。

### 6.3 增强版：1-2 周完成

- 任务列表：
  - 加强模型策略：按 route、成本、健康状态做更明确的 provider/model 选择。
  - 增加更多 readiness 场景和降级说明。
  - 补充队列/Session 多实例边界设计文档，不急于实现完整分布式存储。
  - 增加行业场景演示包。
- 修改文件范围：
  - `src/customer_ai_runtime/application/chat.py`
  - `src/customer_ai_runtime/application/routing.py`
  - `src/customer_ai_runtime/providers/`
  - `scripts/check_external_readiness.py`
  - `docs/deployment.md`
  - `docs/interview-playbook.md`
- 验收标准：
  - provider 选择、成本、readiness 和降级边界可被测试覆盖。
  - 文档明确当前事实和 future target。
- 本地验证命令：
  - `powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite providers`
  - `powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite costs`
  - `powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite external`
  - `.venv\Scripts\python.exe -m pytest`
- 可写进简历的成果：
  - “实现 AI Runtime 的 provider readiness、成本对账样本、模型选择和降级边界验证，提升模型服务治理能力。”
- 不做什么：
  - 不做 GPU 集群、RLHF、训练流水线；这些不符合当前仓库主线和最小投入原则。

## 7. 可执行任务拆解

| 任务 | 背景 | 输入 | 输出 | 修改点 | 依赖 | 验收标准 | 验证命令 | 可并行 | 可写简历 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 岗位驱动报告 | 项目能力多但讲法分散 | 岗位 JSON、目标仓证据 | 本文档 | `docs/job-driven-enhancement-plan.md` | 无 | 内容覆盖画像、方案、路线、任务、简历包装 | `python -m compileall -q src tests` | 否 | 是 |
| RAG eval 扩样例 | 岗位高频问评测 | 现有 eval cases | 更多本地 cases | `examples/rag_eval_cases.json` | 报告 | eval 通过且失败明细可解释 | `scripts/eval_rag.py --json` | 是 | 是 |
| badcase 分类 | 面试追问如何复盘 | eval failures | 失败类型统计 | `evaluation.py` 或脚本 | RAG cases | 输出 route/citation/context/refusal 分类 | pytest rag suite | 是 | 是 |
| 演示脚本固化 | 降低展示成本 | local provider | JSON 演示输出 | `examples/interview_demo.py` | 无 | 输出关键字段 | `examples/interview_demo.py --json` | 是 | 是 |
| 模型治理口径 | 进阶岗位关注模型服务化 | provider/config/cost | 路由与 readiness 说明 | docs 或少量代码 | 演示稳定后 | 不夸大外部联调 | external/providers suite | 否 | 是 |
| 行业演示包 | 行业 AI 岗位需要场景 | 电商/SaaS 样例 | demo 数据和讲法 | `examples/`、docs | 演示脚本 | 能讲业务对象和转人工 | interview demo | 是 | 是 |

## 8. 简历与面试包装

### 8.1 简历项目 bullet

- 基于 FastAPI 与 Pydantic 构建企业级智能客服 Runtime，支持多租户知识库、文本/语音/RTC 接入、宿主鉴权桥接和插件化业务工具，解决 AI 客服难以接入真实业务系统的问题。
- 基于知识库检索、引用溯源和 `HallucinationCheckService` 实现 RAG 回复证据门禁，支持无有效引用时拒答，并通过本地 RAG eval cases 验证 route、citation、context precision/recall、refusal 和 faithfulness。
- 设计受控 Agent 工具流，支持工具白名单、最大步骤限制、失败停止和逐步 trace，将订单查询、物流跟踪、风险转人工等场景从不可观测调用变为可追踪链路。
- 引入 usage、模型价格表、provider billing 样本导入和成本摘要机制，将 token、缓存命中、估算成本和账单样本差异纳入本地可验证的成本治理视图。
- 通过 `examples/interview_demo.py` 串联知识问答、缓存命中、业务工具、人工接管队列、成本摘要与 RAG eval，形成可复现的 AI 应用面试演示闭环。

### 8.2 项目介绍

`customer-ai-runtime` 是一个面向企业客服场景的 AI Runtime 参考实现，核心目标不是做单点 RAG Demo，而是把知识问答、实时业务查询、Agent 工具流、人工接管、成本治理、评测和外部依赖 readiness 串成可验证的后端系统。项目主栈是 Python/FastAPI，默认本地 provider 可跑通演示，也预留 OpenAI、Qdrant、Pinecone、Milvus、HTTP/GraphQL/gRPC 业务适配等扩展。

### 8.3 技术难点描述

难点在于客服场景同时要求答案有证据、业务数据实时、工具调用可控、成本可观测、失败可兜底。项目通过知识问答与业务查询分流、RAG 引用和拒答门禁、受控 Agent 工具流、人工接管队列、usage/cost 摘要和本地 eval，把“模型生成”约束在可解释、可复盘、可测试的工程边界内。

### 8.4 STAR 面试回答

- S：企业客服既有高频知识问答，也有订单、物流、售后等实时业务查询，单纯 RAG 容易无法处理动态状态，开放式 Agent 又存在越权和不可观测风险。
- T：设计一个可本地验证的 AI 客服 Runtime，覆盖知识问答、业务工具、转人工、成本治理和评测闭环。
- A：使用 FastAPI 建立统一 API；将知识问答走 RAG 检索、引用和拒答；业务查询走工具插件且不缓存；受控 Agent 工具流限制白名单、步骤数和失败停止；诊断事件记录 route、tool、retrieval miss、usage 和成本；用 eval cases 和 interview demo 做回归验证。
- R：当前仓库可通过本地测试和脚本验证核心链路；外部 provider 联调、线上准确率和真实成本节省仍需真实环境与样本确认。

### 8.5 为什么匹配 AI 应用岗位

因为岗位高频要求不是“会调用模型 API”，而是把模型、检索、工具、权限、评测、日志、成本和业务流程接成系统。当前项目正好覆盖 AI应用/RAG、AI Agent、Python/FastAPI 后端和模型服务治理四条主线，且能用本地脚本验证关键链路，适合主投 AI 应用工程师、RAG 工程师、Agent 后端工程师和 AI 平台应用层岗位。

### 8.6 为什么不只是 Demo

它不只返回一个模型答案，而是包含知识版本、引用来源、拒答、业务工具、人工接管、成本摘要、readiness 审计和测试脚本。项目仍是参考实现，不宣称生产 SLA，但它已经具备“输入、路由、检索/工具、输出、评测、诊断、兜底”的闭环，而不是一个单页面聊天 Demo。

### 8.7 高频面试追问与回答思路

1. 问：RAG 为什么要拒答？  
   答：企业知识库不能无证据强答；当前项目缺少有效 citation 或证据重叠不足时会返回拒答字段。
2. 问：怎么证明 RAG 质量？  
   答：用本地 eval cases 验证 route、citation keyword、context precision/recall、refusal 和 faithfulness；不把本地结果说成线上准确率。
3. 问：Agent 为什么不用完全自主？  
   答：客服场景更看重可控和审计；项目用白名单、最大步骤、失败停止和 trace 限定工具流。
4. 问：业务查询为什么不缓存？  
   答：订单、物流、售后状态实时变化，缓存会带来错误回答；知识问答才适合安全缓存。
5. 问：成本治理怎么做？  
   答：记录 usage、模型价格表估算、缓存命中和 provider billing 样本，摘要里区分估算成本和导入样本金额。
6. 问：多租户怎么隔离？  
   答：核心对象统一使用 `tenant_id`，认证上下文校验租户访问，知识库和会话按租户隔离。
7. 问：外部 provider 是否已经联调？  
   答：未配置真实凭据时只验证 readiness 口径；通过与否必须看真实环境输出，不能虚构。
8. 问：这个项目哪里体现 FastAPI 后端能力？  
   答：路由、schema、依赖注入、鉴权、streaming、上传、WebSocket、测试和 Docker 都在仓库里有实现。
9. 问：如果 eval 失败怎么修？  
   答：先看失败类型：route 错调路由，citation 缺失补知识或调切片，context precision 低调召回/重排，拒答错调阈值和证据门禁。
10. 问：距离生产还差什么？  
   答：真实业务系统联调、线上标注集、生产监控告警、共享 Session 存储、多实例队列和真实账单自动拉取。

## 9. 最终结论

### 9.1 最值得优先做的 3 件事

1. 固化本地演示闭环：跑通 `examples/interview_demo.py --json`，准备 3 分钟讲法。
2. 强化 RAG eval 和 badcase：扩充本地 cases，输出失败分类和修复建议。
3. 把成本治理、readiness 和人工接管讲法收敛到面试材料中，明确当前事实与 future target。

### 9.2 最不建议做的 3 件事

1. 不建议做纯算法训练、复杂微调或 RLHF；岗位主线和当前项目证据不匹配。
2. 不建议大规模微服务化或模型网关重构；会增加风险，短期不提升投递可信度。
3. 不建议只为了展示做 UI；当前岗位更看重后端闭环、评测、稳定性和业务落地。

### 9.3 主打岗位关键词

AI应用工程师、RAG 工程化、AI Agent 后端、FastAPI 后端、大模型应用开发、智能客服 Runtime、模型服务治理、RAG eval、引用溯源、拒答、工具调用、人工接管、成本治理、可观测性。

### 9.4 距离主投岗位还差什么

主投岗位已经基本匹配；主要差口在于项目讲法需要收敛、演示输出需要提前跑通、简历 bullet 需要使用可验证指标而非泛化描述。

### 9.5 距离进阶岗位还差什么

进阶岗位还需要更强的真实指标和外部联调证据：线上标注集、真实 provider 成本、真实业务 API、p95/TTFT、失败率、缓存命中率、多实例一致性和监控告警。

### 9.6 当前优先补什么

优先补文档和 Demo，其次补测试，再补少量代码。当前核心代码能力已经丰富，直接扩代码容易分散主线；先把可验证闭环和岗位讲法打磨清楚收益更高。

### 9.7 如果只能投入 1 天

完成本文档、跑通 RAG/Agent 关键测试和 interview demo，整理 3 分钟项目讲法与 5 条简历 bullet。

### 9.8 如果投入 1 周

扩充 RAG eval、补 badcase 分类、整理行业场景演示包、补 provider/readiness 讲法，并把 README 与面试手册交叉引用更新到一致。
