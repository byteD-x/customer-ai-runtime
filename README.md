# Customer AI Runtime

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 面向真实业务场景的智能客服能力平台，支持文本、语音、RTC实时通话，可挂载、可插件化、可行业增强。

`customer-ai-runtime` 是一个企业级智能客服平台参考实现。它不是简单的 RAG 问答服务，而是一个能够处理知识问答、实时业务查询、AI/人工协同的完整客服引擎。

## 核心特性

![Multimodal](https://img.shields.io/badge/Multimodal-文本%20|%20语音%20|%20RTC-blue)
![Plugin](https://img.shields.io/badge/Plugin-可插件化架构-green)
![Host](https://img.shields.io/badge/Host-宿主系统挂载-orange)
![Industry](https://img.shields.io/badge/Industry-行业增强-purple)

- **多模态客服** - 支持文本、语音轮次、RTC 实时通话三种接入模式
- **宿主系统挂载** - 可作为 FastAPI 子应用挂载，复用宿主登录态（Session/Cookie/JWT/Custom Token/自定义桥接）
- **插件化架构** - 路由策略、业务工具、行业适配、鉴权桥接、回复后处理均可插件扩展
- **行业增强** - 内置电商、SaaS、教育、物流、CRM 等行业适配器，支持自定义行业
- **RAG 知识增强** - 多租户知识库管理，支持向量检索与引用溯源
- **实时业务数据** - 通过业务工具插件查询订单、物流、工单等动态数据
- **AI/人工协同** - 智能路由决策，支持高风险识别与人工接管
- **智能路由增强** - 支持路由置信度分层、`intent_stack` 多轮追踪、`page_context` / `business_objects` 场景感知
- **运营管理** - Prompt/Policy 管理、Prompt 版本历史、只读 revision 摘要与安全 diff、会话监控、诊断接口、插件管理
- **质量反馈闭环** - 会话关闭时支持提交满意度评分与解决状态，管理端可汇总平均分、分布与解决状态统计
- **用户反馈采集** - 消息级支持点赞、点踩、转人工反馈，转人工反馈可生成结构化交接包并切换会话状态
- **响应时效追踪** - 会话级记录首响和平均响应时长，管理端支持按渠道汇总
- **知识库健康巡检** - 管理端支持查看文档数、切片数、平均切片长度、重复切片率、空文档数与健康分
- **检索失败分析** - 记录知识检索未命中的查询、最高分和渠道，支持按知识库聚合 Top 缺口问题
- **自动切片优化** - 基于当前切片统计给出推荐 `chunk_max_tokens` / `chunk_overlap`，并可一键生成优化版本
- **知识版本管理** - 支持版本快照、激活切换与回滚，检索与引用按激活版本隔离
- **知识库效果分析** - 管理端汇总命中率、有效命中率、满意度、负反馈率，并输出优化建议
- **低成本治理** - 文本链路记录 LLM token、usage 来源、币种、账期、可配置模型价格估算、缓存命中与预算告警；支持导入 provider billing 样本并在管理端区分本地估算成本与 provider 账单样本金额；知识问答安全缓存，业务查询保持实时不缓存，并输出单实例缓存运行时统计
- **可复现 RAG 评测** - 提供 8 个本地标注 eval cases 与脚本，覆盖多知识库、标注集元数据、灰度 cohort、人工复核状态、离线准确率、引用关键词、上下文 precision/recall、有效命中率和失败明细
- **人工接管队列** - 入队动作已收敛到 `HandoffQueueBackend.enqueue` 并支持容器注入；默认 `local` 后端基于 Session 单进程认领，可选 `sqlite` 后端提供共享队列表事务认领
- **受控 Agent 工具流** - 支持白名单工具顺序编排、步骤上限、失败停止和 HTTP trace 返回，默认仅 `admin` / `operator` 可调用

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│ 渠道接入层                                                   │
│ HTTP Chat │ Voice API │ RTC WebSocket │ Host Mount / SDK    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 宿主桥接层                                                   │
│ Auth Bridge │ Host Auth Context Mapper │ Context Injection   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 核心客服引擎层                                               │
│ Session │ Route Orchestrator │ LLM Orchestrator            │
│ Voice Runtime │ RTC State Machine │ Handoff Orchestrator    │
└─────────────────────────────────────────────────────────────┘
            │                          │
            ▼                          ▼
┌─────────────────────────┐  ┌──────────────────────────────┐
│ 业务增强层              │  │ 插件平台层                   │
│ Industry Adapter        │  │ Plugin Registry              │
│ Business Context Builder│  │ Route / Tool / Auth /        │
│ Knowledge Domain Manager│  │ Industry / Handoff /         │
│ Real-time Data Provider │  │ Context / Response Plugins   │
└─────────────────────────┘  └──────────────────────────────┘
            │                          │
            └──────────────┬───────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 提供商适配层                                                 │
│ LLM │ ASR │ TTS │ RTC │ Vector Store │ Business API        │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.13+
- 可选：OpenAI API Key、Qdrant 向量数据库

### 提供商扩展

当前仓库已落地的可选提供商包括：

- 语音识别（ASR）：`local`、`openai`、`aliyun`、`tencent`
- 语音合成（TTS）：`local`、`openai`、`aliyun`、`tencent`
- 向量库：`local`、`qdrant`、`pinecone`、`milvus`
- 业务适配器：`local`、`http`、`graphql`、`grpc`

其中语音提供商的最小配置如下：

- 阿里云：`CUSTOMER_AI_ASR_PROVIDER=aliyun` / `CUSTOMER_AI_TTS_PROVIDER=aliyun`，并填写 `CUSTOMER_AI_ALIYUN_ACCESS_KEY_ID`、`CUSTOMER_AI_ALIYUN_ACCESS_KEY_SECRET`、`CUSTOMER_AI_ALIYUN_APP_KEY`
- 腾讯云：`CUSTOMER_AI_ASR_PROVIDER=tencent` / `CUSTOMER_AI_TTS_PROVIDER=tencent`，并填写 `CUSTOMER_AI_TENCENT_SECRET_ID`、`CUSTOMER_AI_TENCENT_SECRET_KEY`

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/customer-ai-runtime.git
cd customer-ai-runtime

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
# 国内网络环境可选：使用镜像源
# export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e ".[dev]"

# 若需 Pinecone / Milvus / gRPC / 阿里云 / 腾讯云 提供商
# providers extra 同时包含 PDF / Word 文档解析依赖
pip install -e ".[dev,providers]"
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 文件，配置你的 API Key 和数据库连接
```

阿里云语音默认走官方智能语音交互 RESTful 接口，一句话识别与语音合成都使用 `AppKey + Token` 链路，运行时会在服务端自动换取短期 Token。腾讯云语音默认走官方 Python SDK，请确保已安装 `providers` extra。

### 启动服务

```bash
# 方式1：直接运行
python -m customer_ai_runtime

# 方式2：使用脚本（Windows）
.\scripts\run-dev.ps1

# 方式3：Docker
docker-compose -f deploy/docker-compose.yml up
```

服务默认运行在 `http://127.0.0.1:8000`

### 验证安装

```bash
# 健康检查
curl http://127.0.0.1:8000/healthz

# 查看 API 文档
open http://127.0.0.1:8000/docs
```

## 使用示例

### 文本客服

```python
import httpx

response = httpx.post("http://127.0.0.1:8000/api/v1/chat/messages", json={
    "tenant_id": "demo-tenant",
    "channel": "web",
    "message": "我的订单什么时候发货？",
    "knowledge_base_id": "kb_support",
    "integration_context": {
        "industry": "ecommerce",
        "page_context": {"page_type": "order_detail"},
        "business_objects": {"order_id": "ORD-1001"}
    }
}, headers={"X-API-Key": "your-api-key"})

print(response.json())
```

文本客服响应会额外返回：

- `route_confidence`：本轮路由决策置信度
- `route_confidence_band`：`high` / `medium` / `low`
- `intent`：当前识别到的主意图
- `route_decision`：包含 `tool_name`、`reason`、`matched_signals`

### 知识库文件上传

```python
import httpx

with open("support-policy.md", "rb") as file:
    response = httpx.post(
        "http://127.0.0.1:8000/api/v1/knowledge-bases/kb_support/documents/upload",
        data={"tenant_id": "demo-tenant"},
        files={"file": ("support-policy.md", file, "text/markdown")},
        headers={"X-API-Key": "your-api-key"},
    )

print(response.json())
```

上传入口会将 UTF-8 文本 / Markdown 文件解析为知识库文档，并复用现有切片、版本与向量写入链路；PDF / Word 解析需要安装 `providers` extra。

### 路由增强策略

运行时热配置中的 `policies` 支持以下路由增强字段：

- `route_fallback_confidence_threshold`
- `route_handoff_confidence_threshold`
- `intent_stack_max_depth`
- `intent_return_keywords`

系统会先聚合插件候选结果，再结合当前页面、业务对象和会话 `intent_stack` 做动态加权。低于兜底阈值时优先进入澄清回复；若连续低置信度或存在挫败信号，则升级为转人工。

### 宿主系统挂载

```python
from fastapi import FastAPI
from customer_ai_runtime.integration import CustomerAIRuntimeModule

app = FastAPI()

# 挂载客服平台
runtime = CustomerAIRuntimeModule()
app.mount("/customer-ai", runtime.app)

# 注册自定义鉴权桥接
runtime.register_plugin(MyAuthBridgePlugin())
```

更多示例见 [examples/](examples/) 目录。

### 面试演示快速验证（5 分钟）

本仓库提供不依赖付费外部服务的本地演示闭环，默认使用 `local` LLM / Vector / Business provider。在已创建 `.venv` 且依赖安装完成后，面试前可用下面命令快速复跑：

```powershell
# 快速目标化测试：默认跑文本知识问答 + 流式 Chat 正常/错误事件，内置超时保护
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1

# 根据当前 git status 自动选择最小 pytest 目标；无法识别时回退完整 pytest
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite auto

# 本地质量门禁：ruff、format check、compileall、mypy、pytest
powershell -ExecutionPolicy Bypass -File scripts\test.ps1

# RAG 质量评测：route、引用关键词、上下文 precision/recall、有效命中率、失败明细（JSON 输出）
.venv\Scripts\python.exe scripts\eval_rag.py --json

# 外部联调 readiness：未配置凭据时返回 skipped，不宣称真实联调通过
.venv\Scripts\python.exe scripts\check_external_readiness.py --json

# 可选：真实线上脱敏标注样本评估，需要传入 JSON/JSONL 导出文件
.venv\Scripts\python.exe scripts\eval_online_rag.py path\to\online-rag.jsonl --json

# 面试演示：知识问答、缓存命中、业务工具、结构化交接包、转人工队列、成本摘要、RAG eval
.venv\Scripts\python.exe examples\interview_demo.py
# 可选：使用脚本封装演示命令
powershell -ExecutionPolicy Bypass -File scripts\interview-demo.ps1
```

当前本地实测基线以本节命令输出为准；演示输出包含 `route`、`citations`、`tool_result`、`handoff_package`、`handoff_queue`、`claimed_session`、`cost_summary`、`rag_eval_summary`，便于在面试中现场说明“低成本、高效率、可治理”的 AI 客服链路。`cost_summary` 会区分 `estimated_cost_cents`（本地模型价格表估算）与 `provider_billed_cost_cents`（导入的 provider billing 样本金额）。RAG eval 中的 `context_precision` / `context_recall` 是基于本地标注关键词和返回引用文本的启发式离线指标，用于暴露额外无关引用或上下文遗漏，不代表线上真实检索精度。`check_external_readiness.py` 会检查 OpenAI models、OpenAI Admin usage/costs、Qdrant health/collections、业务 API、客服工单 API、Redis/Postgres 队列依赖的配置与可达性，未配置时返回 `skipped`；只有真实凭据、网络和外部系统可达时才能声明对应联调通过。`eval_online_rag.py` 只基于你提供的脱敏线上标注样本计算 `online_accuracy`，没有样本时不代表线上准确率。上述结果只代表当前本地样例、导入样本或输入样本，不代表真实成本节省、自动 provider 账单拉取、外部 provider 端到端联调结果或生产 SLA。

## 插件扩展

平台提供以下扩展点：

| 插件类型 | 用途 | 示例 |
|---------|------|------|
| `RouteStrategyPlugin` | 路由决策 | 自定义分流策略 |
| `BusinessToolPlugin` | 业务工具 | 订单查询、物流追踪 |
| `IndustryAdapterPlugin` | 行业适配 | 电商、SaaS、教育 |
| `AuthBridgePlugin` | 鉴权桥接 | Custom Token、自定义桥接 |
| `ContextEnricherPlugin` | 上下文增强 | 用户画像注入 |
| `ResponsePostProcessorPlugin` | 回复后处理 | 脱敏、多语言 |
| `HumanHandoffPlugin` | 人工协同 | 转人工策略 |

### 注册插件示例

```python
from customer_ai_runtime.domain.platform import Plugin, PluginDescriptor

class OrderStatusTool(Plugin):
    descriptor = PluginDescriptor(
        plugin_id="order_status_tool",
        name="订单状态查询",
        kind="business_tool",
        priority=100
    )
    
    async def execute(self, parameters, context):
        order_id = parameters.get("order_id")
        # 查询订单状态...
        return {"status": "shipped", "tracking_no": "SF123456"}

# 注册插件
runtime.register_plugin(OrderStatusTool())
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/project-overview.md](docs/project-overview.md) | 项目总览与目标 |
| [docs/business-requirements.md](docs/business-requirements.md) | 业务需求、场景与成功指标 |
| [docs/architecture.md](docs/architecture.md) | 总体架构设计 |
| [docs/module-design.md](docs/module-design.md) | 模块详细设计 |
| [docs/adapter-design.md](docs/adapter-design.md) | 适配器与业务增强边界 |
| [docs/api.md](docs/api.md) | API 接口文档 |
| [docs/business-enhancement.md](docs/business-enhancement.md) | 业务增强设计 |
| [docs/auth-bridge.md](docs/auth-bridge.md) | 宿主桥接与鉴权 |
| [docs/plugin-system.md](docs/plugin-system.md) | 插件系统设计 |
| [docs/deployment.md](docs/deployment.md) | 部署指南 |
| [docs/events.md](docs/events.md) | 诊断事件与埋点约定 |
| [docs/slo.md](docs/slo.md) | 性能口径与 SLO |
| [docs/storage.md](docs/storage.md) | 存储与多实例说明 |
| [docs/testing.md](docs/testing.md) | 测试分层、命令与验收重点 |
| [docs/roadmap.md](docs/roadmap.md) | 实施路线图 |
| [docs/progress-control.md](docs/progress-control.md) | 当前进展、风险和交付检查 |
| [docs/TODO.md](docs/TODO.md) | 下一步待办和暂不声明能力 |
| [docs/interview-playbook.md](docs/interview-playbook.md) | 面试追问手册与本地验证路径 |

面试与简历材料：

- [STAR-HIGHLIGHTS.md](STAR-HIGHLIGHTS.md)：项目亮点、技术难点、解决方案与 STAR 表达
- [RESUME_SNIPPETS.md](RESUME_SNIPPETS.md)：简历和作品集可复用片段

## 测试

```powershell
# 开发中快速验证当前切片，默认 stream suite
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1

# 按预设场景快速回归：auto / stream / api / handoff / rag / agent / providers / smoke / external / selector / full
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite auto
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite handoff
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite selector
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Suite providers

# 直接跑某个 pytest node，脚本会自动使用 .venv Python 并设置超时
powershell -ExecutionPolicy Bypass -File scripts\test-fast.ps1 -Target "tests\test_runtime_api.py::test_chat_knowledge_stream_flow"

# 长测试分组诊断：每组独立日志，支持 heartbeat、总超时、idle timeout 和失败日志尾部
.venv\Scripts\python.exe scripts\quality\run_pytest_groups.py `
  --group selector=tests/test_select_fast_tests.py `
  --group api=tests/test_runtime_api.py `
  --idle-timeout-seconds 60 `
  --tail-lines-on-failure 60

# 提交前完整本地门禁
powershell -ExecutionPolicy Bypass -File scripts\test.ps1

# 覆盖率报告
.venv\Scripts\python.exe -m pytest --cov=src/customer_ai_runtime --cov-report=html
```

`scripts/test-fast.ps1` 用于开发中的目标化回归，不替代 `scripts/test.ps1` 完整质量门禁。`-Suite auto` 会基于当前 `git status` 自动选择最小 pytest 目标，包括未跟踪的新文件；当多个 suite 同时选中时，会剪掉已被整文件或目录目标覆盖的 nodeid，避免重复收集；无法安全归类的运行时代码、依赖、CI 或门禁脚本变更会回退到完整 `pytest tests`。默认超时为 120 秒，可通过 `-TimeoutSeconds` 调整；超时时脚本返回退出码 `124` 并输出已捕获的 pytest stdout/stderr。

`scripts/quality/run_pytest_groups.py` 用于把较长 pytest 任务拆成命名分组并定位卡住或失败的分组；每组保留 stdout/stderr 日志，heartbeat 输出日志字节数与 idle 秒数，失败或超时时只打印有限尾部。该工具用于提速排障，不替代提交前的完整 `scripts/test.ps1`。

人工接管队列默认使用 `CUSTOMER_AI_HANDOFF_QUEUE_BACKEND=local`；需要验证共享队列表事务认领时可设置为 `sqlite`，队列文件位于 `<storage_root>/state/handoff_queue.sqlite3`。该后端只覆盖人工接管队列的入队与 `claim-next` 认领，不代表 Session JSON 仓储已经具备完整多实例强一致能力。

## 行业支持

内置行业适配器：

- **电商 (ecommerce)** - 订单、商品、物流、售后、会员
- **SaaS** - 账号、组织、订阅、工单、权限
- **教育** - 课程、学习进度、考试、证书
- **物流** - 运单、轨迹、异常、签收、赔付
- **CRM** - 客户档案、服务记录、工单、跟进

## 认证方式

支持多种认证模式：

- `X-API-Key` - 平台 API Key
- `Cookie / Session` - 复用宿主会话
- `Authorization: Bearer <JWT>` - JWT Token
- `X-Host-Token` - 宿主自定义票据
- **自定义桥接** - 通过 `AuthBridgePlugin` 实现任意鉴权逻辑

## 项目结构

```
customer-ai-runtime/
├── src/customer_ai_runtime/    # 核心源码
│   ├── api/                    # FastAPI 路由与模型
│   ├── application/            # 业务编排与插件
│   ├── core/                   # 配置、日志、工具
│   ├── domain/                 # 领域模型
│   ├── providers/              # 外部服务适配
│   └── repositories/           # 数据持久化
├── docs/                       # 设计文档
├── examples/                   # 接入示例
├── tests/                      # 测试用例
├── deploy/                     # 部署配置
└── scripts/                    # 开发脚本
```

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发规范

- 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 提交规范
- 代码风格使用 `ruff` 进行格式化
- 类型检查：`mypy`
- 所有功能需包含测试用例

```bash
# 代码格式化
ruff format .
ruff check .

# 类型检查
mypy src
```

当前本地质量门禁由 `scripts/test.ps1` 串联执行：`ruff check`、`ruff format --check`、`python -m compileall`、`mypy`、`pytest`。当前仓库已包含 GitHub Actions workflow：`.github/workflows/ci.yml`，在 push / pull_request 时执行 `ruff check`、`ruff format --check`、`compileall`、`mypy`、`pytest`；远端是否通过以实际 Actions 运行结果为准。

## 许可证

本项目采用 [MIT](LICENSE) 许可证。

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [Pydantic](https://docs.pydantic.dev/) - 数据验证
- [OpenAI](https://openai.com/) - LLM 能力
- [Qdrant](https://qdrant.tech/) - 向量数据库

---

> **注意**：当前仓库为单体参考实现，具备完整运行能力。未来拆分为多服务架构属于 roadmap 规划，当前尚未落地。
