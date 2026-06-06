# 文档收尾核验记录

日期：2026-05-18

## 范围

- README 与 docs 下的面试强化相关文档
- `STAR-HIGHLIGHTS.md`
- `RESUME_SNIPPETS.md`

## 本轮核验结论

- 成本治理、RAG eval、人工接管队列、面试演示与 STAR 材料均已在文档中形成闭环说明。
- 已修正不存在的远端 CI 口径，改为当前可验证的 `scripts/test.ps1` 本地质量门禁。
- 已将 `docs/TODO.md` 中已落地的路由增强与单实例智能排队能力改为当前基线已完成。
- 已将简历片段中的职责措辞调整为可按真实经历校准的表达。
- 线上准确率、真实成本节省、QPS、SLA 等仍保留为待确认指标或 future target。

## 已执行检查

```powershell
rg -n "<旧 CI、旧职责、旧待办口径关键词>" README.md docs STAR-HIGHLIGHTS.md RESUME_SNIPPETS.md
git diff --check
```

`rg` 检查无命中。`git diff --check` 无空白错误，仅提示仓库中若干文件下次由 Git 触碰时会按 CRLF 处理。

## 未重复执行

本轮只改文档，未重新运行完整测试门禁。前序实现阶段已验证：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
.venv\Scripts\python.exe scripts\eval_rag.py
.venv\Scripts\python.exe examples\interview_demo.py
```

---

## 2026-06-06 文档一致性复核

### 范围

- README 文档入口与认证口径
- `docs/api.md` API 契约字段、权限说明和章节编号
- `docs/deployment.md` 部署后验证、成本摘要、人工队列和本地 eval/demo 边界
- `docs/slo.md` 当前可观测指标与 Future Target
- `docs/plugin-system.md` 插件管理接口当前事实与远程插件边界
- `docs/business-enhancement.md` 知识缓存、实时业务数据和 RAG eval 约束
- `docs/adapter-design.md` 当前业务适配器与评测/运营边界
- `docs/TODO.md` 更新时间

### 事实来源

- `pyproject.toml`
- `src/customer_ai_runtime/api/routes.py`
- `src/customer_ai_runtime/api/schemas.py`
- `src/customer_ai_runtime/application/chat.py`
- `src/customer_ai_runtime/application/admin.py`
- `src/customer_ai_runtime/domain/models.py`
- `src/customer_ai_runtime/evaluation.py`
- `scripts/eval_rag.py`
- `examples/interview_demo.py`
- `tests/`

### 本轮核验结论

- API 文档已改为当前本地参考实现契约，并修正知识版本快照、切片优化字段与当前 schema 的不一致。
- README 已补齐主要 docs 入口，并把 SSO 内置能力口径收紧为 Custom Token / 自定义桥接。
- 部署、SLO、插件、业务增强和适配器文档已补充成本治理、知识缓存、RAG eval、单实例人工接管队列与 Future Target 边界。
- 线上准确率、真实成本节省、多实例原子认领、真实外部 provider 联调仍未声明为当前事实。

### 已执行检查

```powershell
rg -n "当前仓库 CI|\.github/workflows/ci|已通过|线上准确率[^不]|真实成本节省[^或]|多实例.*已落地|消息总线|conversation|version_name|optimization_report" README.md docs AGENTS.md .codex
git diff --check
python -m compileall -q src tests
.venv\Scripts\python.exe -m pytest tests\test_interview_artifacts.py tests\test_runtime_api.py -q
.venv\Scripts\python.exe scripts\eval_rag.py
.venv\Scripts\python.exe examples\interview_demo.py
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

结果：

- API 路由与 `docs/api.md` 端点标题覆盖一致：`routes=54 docs=54 missing=0 extra=0`。
- 冲突词搜索只命中 AGENTS 或文档中的防护性表述，例如“不代表线上准确率”“不与 conversation 混用”。
- `git diff --check` 无空白错误；仅提示部分文件下次由 Git 触碰时会按 CRLF 处理。
- `compileall` 通过。
- 重点测试通过：`38 passed in 15.81s`。
- RAG eval 通过：`case_count=3`、`passed=3`、`failed=0`。
- interview demo 通过，并输出 route、citations、tool_result、handoff_queue、claimed_session、cost_summary、rag_eval_summary。
- 完整本地门禁通过：`58 passed in 5.50s`。
