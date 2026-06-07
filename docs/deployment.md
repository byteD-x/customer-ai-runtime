# 部署文档

## 1. 当前可部署形态

当前仓库已落地的是单体 FastAPI 运行时，适用于：

- 本地开发与联调
- 单实例测试环境
- 宿主系统挂载验证
- 基于 Docker Compose 的小规模部署

当前事实：

- 已提供 [Dockerfile](../Dockerfile)
- 已提供 [docker-compose.yml](../deploy/docker-compose.yml)
- 已提供 `.env` 方式的环境变量配置
- 已提供管理接口用于运行时配置热更新、诊断与指标查看

## 2. Docker Compose 配置

仓库内 Compose 文件包含以下服务：

- `customer-ai-runtime`
  用途：运行时主服务，默认暴露 `8000`
- `qdrant`
  用途：向量检索依赖，默认暴露 `6333/6334`

说明：Compose 已提供 Qdrant 服务和默认 `CUSTOMER_AI_QDRANT_URL=http://qdrant:6333`；应用默认仍使用 `local` Vector provider，若要实际联调 Qdrant，需要显式配置 `CUSTOMER_AI_VECTOR_PROVIDER=qdrant` 及必要凭据。

关键配置点：

- `customer-ai-runtime` 默认通过 `build.args.CUSTOMER_AI_PIP_EXTRAS=providers` 安装可选提供商依赖
- 通过 `env_file: ../.env` 加载环境变量
- 默认挂载命名卷 `customer-ai-data` 持久化 `storage_root`
- 已配置健康检查：`GET /healthz`
- 已配置容器日志轮转：`json-file + max-size/max-file`

启动命令：

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

停止命令：

```bash
docker compose -f deploy/docker-compose.yml down
```

查看日志：

```bash
docker compose -f deploy/docker-compose.yml logs -f customer-ai-runtime
docker compose -f deploy/docker-compose.yml logs -f qdrant
```

## 3. 环境变量说明

### 3.1 基础运行

- `CUSTOMER_AI_ENV`
  建议：`prod`
- `CUSTOMER_AI_HOST`
  容器内建议：`0.0.0.0`
- `CUSTOMER_AI_PORT`
  默认：`8000`
- `CUSTOMER_AI_LOG_LEVEL`
  建议生产环境：`INFO`
- `CUSTOMER_AI_STORAGE_ROOT`
  容器内建议：`/data`
- `CUSTOMER_AI_API_KEYS_JSON`
  管理与客户调用 API Key 映射，建议通过密钥管理系统注入

### 3.2 提供商选择

- `CUSTOMER_AI_LLM_PROVIDER`
  可选：`local`、`openai`
- `CUSTOMER_AI_ASR_PROVIDER`
  可选：`local`、`openai`、`aliyun`、`tencent`
- `CUSTOMER_AI_TTS_PROVIDER`
  可选：`local`、`openai`、`aliyun`、`tencent`
- `CUSTOMER_AI_VECTOR_PROVIDER`
  可选：`local`、`qdrant`、`pinecone`、`milvus`
- `CUSTOMER_AI_BUSINESS_PROVIDER`
  可选：`local`、`http`、`graphql`、`grpc`

### 3.3 常见提供商凭据

- OpenAI
  `CUSTOMER_AI_OPENAI_API_KEY`
  `CUSTOMER_AI_OPENAI_ADMIN_API_KEY`
  `CUSTOMER_AI_OPENAI_ADMIN_USAGE_PATH`
  `CUSTOMER_AI_OPENAI_ADMIN_COSTS_PATH`
- 阿里云语音
  `CUSTOMER_AI_ALIYUN_ACCESS_KEY_ID`
  `CUSTOMER_AI_ALIYUN_ACCESS_KEY_SECRET`
  `CUSTOMER_AI_ALIYUN_APP_KEY`
- 腾讯云语音
  `CUSTOMER_AI_TENCENT_SECRET_ID`
  `CUSTOMER_AI_TENCENT_SECRET_KEY`
- Qdrant
  `CUSTOMER_AI_QDRANT_URL`
  `CUSTOMER_AI_QDRANT_API_KEY`
- 外部业务 HTTP API
  `CUSTOMER_AI_BUSINESS_API_BASE_URL`
  `CUSTOMER_AI_BUSINESS_API_KEY`
- 外部客服工单 API readiness 检查
  `CUSTOMER_AI_TICKET_API_BASE_URL`
  `CUSTOMER_AI_TICKET_API_KEY`
- Redis/Postgres 队列依赖 readiness 检查
  `CUSTOMER_AI_REDIS_HOST`
  `CUSTOMER_AI_REDIS_PORT`
  `CUSTOMER_AI_POSTGRES_HOST`
  `CUSTOMER_AI_POSTGRES_PORT`

### 3.4 宿主桥接与认证

- `CUSTOMER_AI_HOST_SESSION_COOKIE_NAME`
- `CUSTOMER_AI_HOST_SESSION_MAP_JSON`
- `CUSTOMER_AI_HOST_TOKEN_MAP_JSON`
- `CUSTOMER_AI_HOST_JWT_SECRET`
- `CUSTOMER_AI_HOST_JWT_ISSUER`
- `CUSTOMER_AI_HOST_JWT_AUDIENCE`

## 4. 生产环境配置建议

### 4.1 入口与网络

- 在运行时前面放置反向代理或 API Gateway，统一处理 TLS、限流、来源 IP 和审计
- 仅暴露应用入口端口，不直接对公网暴露内部向量库
- 若使用 Docker Compose，建议将 Qdrant 仅绑定在内网网络，不映射宿主端口

### 4.2 密钥与配置

- 不要把真实密钥写入 Git
- 优先通过 CI/CD Secret、Kubernetes Secret、云 Secret Manager 或宿主机注入环境变量
- 管理员 API Key 与客户 API Key 分离，最少权限分配

### 4.3 存储与持久化

- 生产环境不要依赖临时文件系统
- 至少挂载持久卷保存 `storage/state/*.json`
- 当会话量和知识量增长时，应迁移到外部持久化存储，不建议长期使用本地 JSON 作为主存储

### 4.4 外部依赖保护

- 为 LLM、ASR、TTS、业务 API 和向量库设置合理超时
- 通过管理接口观察 `providers/health`，在未就绪时阻断流量切换
- 对计费型提供商单独设置调用配额和告警

## 5. 监控与日志配置

当前仓库已落地的观测能力：

- 应用日志：标准输出日志，格式由 [logging.py](../src/customer_ai_runtime/core/logging.py) 配置
- 指标计数：内存计数器，可通过管理接口获取
- 诊断事件：持久化到 `storage/state/diagnostics.json`
- 提供商健康：可通过管理接口查看配置就绪态

建议接入方式：

- 日志采集
  通过 Docker `json-file` 或宿主日志采集器接入 ELK / Loki / 云日志服务
- 指标采集
  通过 `GET /api/v1/admin/metrics` 和 `GET /api/v1/admin/metrics/summary` 采集业务计数
- 诊断排障
  通过 `GET /api/v1/admin/diagnostics` 和 `GET /api/v1/admin/sessions/{session_id}/monitor` 定位会话异常
- 成本与缓存观察
  通过 `GET /api/v1/admin/costs/summary` 查看当前诊断样本中的 token、估算成本、provider billing 样本金额、诊断样本成本差异、缓存命中和预算告警
- 人工接管队列
  通过 `GET /api/v1/admin/handoff/queue` 查看等待队列，通过 `POST /api/v1/admin/handoff/claim-next` 做管理端认领。默认 `CUSTOMER_AI_HANDOFF_QUEUE_BACKEND=local`，可设置为 `sqlite` 验证共享队列表事务认领。
- 告警拉取
  通过 `GET /api/v1/admin/alerts` 拉取 provider 未就绪、错误诊断、等待人工会话等告警线索
  告警阈值可通过 `PUT /api/v1/admin/runtime-config` 的 `alerts` 字段热更新

## 6. 部署后验证

基础健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

管理面检查：

```bash
# 请使用你在 CUSTOMER_AI_API_KEYS_JSON 中配置的管理员 Key。
# 注意：生产环境禁止使用 demo-admin-key / demo-public-key。
curl -H "X-API-Key: <your-admin-key>" http://127.0.0.1:8000/api/v1/admin/providers/health
curl -H "X-API-Key: <your-admin-key>" http://127.0.0.1:8000/api/v1/admin/metrics/summary
curl -H "X-API-Key: <your-admin-key>" http://127.0.0.1:8000/api/v1/admin/alerts

# 以下接口沿用上方管理端认证 Header：
# http://127.0.0.1:8000/api/v1/admin/costs/summary
# http://127.0.0.1:8000/api/v1/admin/handoff/queue?tenant_id=demo-tenant
```

预期结果：

- `/healthz` 返回 `status=ok`
- `providers/health` 返回各提供商 `ready` 状态
- `metrics/summary` 返回计数器、会话摘要和诊断摘要
- `costs/summary` 返回当前样本的 token、估算成本、缓存命中和预算告警
- `handoff/queue` 返回当前租户等待人工接管队列；无等待会话时为空数组，并通过 `queue_backend` / `consistency_scope` 暴露当前后端口径
- `alerts` 返回需要运维关注的问题列表；无异常时可为空数组

本地演示与评测验证：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
.venv\Scripts\python.exe scripts\eval_rag.py --json
.venv\Scripts\python.exe scripts\check_external_readiness.py --json
.venv\Scripts\python.exe scripts\eval_online_rag.py path\to\online-rag.jsonl --json
.venv\Scripts\python.exe examples\interview_demo.py
# 可选：需要本机安装 k6 且服务已启动
k6 run deploy\k6-smoke.js
```

当前本地实测基线为：`scripts/test.ps1` 通过、RAG eval 8 cases passed、`examples/interview_demo.py` 跑通；`pytest` 数量以实际门禁输出为准。

上述脚本默认使用本地 provider 和临时存储，适合部署前后做演示闭环检查；输出不代表线上 RAG 准确率、真实成本节省、外部 provider 联调通过或生产压测结果。`scripts/check_external_readiness.py` 只检查可选外部依赖的配置、HTTP/TCP 可达性和部分权限探针；JSON 输出会在顶层 `audit` 标明检查范围、生成时间、超时和证据等级，并在每个检查项 `audit` 标明依赖环境变量、探针类型和证据口径；未配置凭据时返回 `skipped`。`deploy/k6-smoke.js` 是模板，只有保留真实 k6 输出后才能讨论 p95/p99、QPS 或 SLA。

## 7. 当前限制

当前可验证限制：

- 观测能力以管理接口和本地持久化事件为主，尚未内建 Prometheus exporter
- Docker Compose 适合单机或小规模环境，不等同于高可用生产集群方案
- 当前存储层仍以本地 JSON 仓储为主，更适合开发、演示和轻量部署
- 当前人工接管队列默认基于本地 `Session` 状态排序，提供单进程认领；可选 SQLite 队列表提供事务认领，但不代表 JSON Session 仓储已具备完整多实例强一致
- 当前成本统计支持本地模型价格表估算和 provider usage 治理入口，未接入真实租户账单结算
- 当前 RAG eval 为离线本地标注样例脚本，包含 cohort、人工复核状态、引用准确率、上下文 precision/recall、拒答准确率和 faithfulness 字段；online eval 只代表输入的脱敏样本，未接入真实业务标注集、线上灰度流量和人工复核系统

## 7.1 安全与保护性配置（当前实现）

- 生产环境禁止使用 demo API key，必须显式配置 `CUSTOMER_AI_API_KEYS_JSON`，或禁用 API key 鉴权（`CUSTOMER_AI_ENABLE_API_KEY_AUTH=false`）。
- 请求体大小限制：`CUSTOMER_AI_MAX_REQUEST_BYTES`（基于 `Content-Length` 拦截）。
- 简易限流：`CUSTOMER_AI_RATE_LIMIT_ENABLED`、`CUSTOMER_AI_RATE_LIMIT_PER_MINUTE`、`CUSTOMER_AI_RATE_LIMIT_BURST`。
- 代理真实 IP（可选）：若服务部署在反向代理/API Gateway 后，可启用 `CUSTOMER_AI_TRUST_X_FORWARDED_FOR=true` 让限流使用 `X-Forwarded-For` 的首个 IP。
- 诊断事件导出（可选）：`CUSTOMER_AI_DIAGNOSTICS_EXPORT_PATH`，会以 JSONL 追加写入文件，便于日志采集器摄取。

## 8. Future Target

以下属于未来目标，不代表当前仓库已落地：

- 多实例无状态部署与共享持久化后端
- Redis/Postgres 多实例人工队列、原子认领与共享 Session 存储
- 基于 provider 原生 usage、租户预算、币种和账单周期的真实成本结算
- 基于业务标注集和线上灰度流量的 RAG 质量评估
- Prometheus / Grafana 原生指标暴露
- 专用告警推送通道（Webhook、短信、IM）
- 更细粒度的审计日志与租户级运维视图
