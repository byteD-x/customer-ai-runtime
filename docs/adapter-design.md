# 适配器设计

## 1. 设计范围

本设计覆盖：

- `Business Adapter`
- `Industry Adapter`
- `Business Context Builder`
- `Knowledge Domain Manager`
- `Real-time Business Data Provider`
- `Response Enhancement Orchestrator`

## 2. Business Adapter

### 职责

- 对接宿主业务系统或外部业务 API
- 提供统一工具执行入口
- 统一错误包装、超时、鉴权与脱敏

### 抽象

```python
class BusinessAdapter(ABC):
    async def execute(self, query: BusinessQuery) -> BusinessResult: ...
```

### 当前实现

- `LocalBusinessAdapter`
- `HttpBusinessAdapter`
- `GraphQLBusinessAdapter`
- `GrpcBusinessAdapter`

### Target State

- 作为工具插件的默认下游适配器
- 支持宿主换票、宿主透传、重试与熔断策略
- 真实业务系统联调结果必须基于外部配置与可复现调用，readiness 脚本只检查配置和健康状态，不能只凭本地 provider 或 `skipped` 结果声明通过

## 3. Industry Adapter

### 职责

- 识别行业
- 提供行业默认知识域
- 提供行业默认工具集合
- 提供行业上下文规范

### 抽象

```python
class IndustryAdapterPlugin(Plugin):
    async def match(self, context: PluginContext) -> IndustryMatchResult: ...
    async def enrich(self, context: PluginContext) -> dict[str, Any]: ...
```

## 4. Business Context Builder

### 输入

- `HostAuthContext`
- `integration_context`
- `session`
- Context Enricher 插件结果

### 输出

- `BusinessContext`

### 字段建议

- `tenant_id`
- `host_user_id`
- `host_roles`
- `host_permissions`
- `industry`
- `page_context`
- `business_objects`
- `user_profile`
- `behavior_signals`
- `session_summary`

## 5. Knowledge Domain Manager

### 职责

- 管理不同租户、行业、场景下的知识库选择
- 支持显式 `knowledge_base_id`
- 支持按行业自动兜底知识域

### 解析顺序

1. 显式请求参数
2. 租户插件配置
3. 行业默认知识域
4. 平台默认知识域

## 6. Real-time Business Data Provider

### 职责

- 统一封装实时业务查询
- 优先调业务工具插件
- 无命中时回退 `BusinessAdapter`

### 失败策略

- 工具不可用：记录诊断并回退
- 参数缺失：显式返回缺失参数
- 业务接口失败：返回 `provider_error` 或建议转人工
- 业务查询默认保持实时，不进入知识问答响应缓存

## 7. Response Enhancement Orchestrator

### 输入

- LLM 原始回复
- 引用
- 业务工具结果
- `BusinessContext`
- 回复后处理插件

### 输出

- 增强后回复
- 增强元数据

### 能力

- 引用附加
- 回复格式化
- 风险脱敏
- 多语言转换
- 结构化输出
- 成本与缓存元数据透传：保留 Chat 链路返回的 `usage`、`usage_source`、`billing_currency`、`billing_period`、`tenant_budget_estimated_cents`、`cache_hit`、`estimated_cost_cents` 和 `budget_status`

## 8. 与插件系统关系

- Industry Adapter 是插件。
- Context Builder 消费 `ContextEnricherPlugin`。
- Real-time Business Data Provider 消费 `BusinessToolPlugin`。
- Response Enhancement Orchestrator 消费 `ResponsePostProcessorPlugin`。

## 9. 与评测和运营的关系

- 业务适配器负责实时数据，不参与 RAG eval 的引用命中判断。
- RAG eval 主要评估本地标注样例中的知识路由、引用关键词、上下文 precision/recall、有效命中、cohort 和人工复核状态；业务工具链路应通过集成测试、readiness 脚本或外部系统联调验证。
- 成本摘要当前来自 Chat 诊断事件；真实业务 API 成本、客服工单成本和外部调用账单属于 future target。
