# Phase 0 Research: 财务数据统一平台

## 研究主题与结论

### 1. AI 解析非结构化财务资料的策略
- **Decision**: 采用“预处理 + LLM 函数调用”双阶段流程：首先根据文件类型做预解析（CSV/Excel 直接读取、PDF/图片走 OCR），随后调用企业合规的 OpenAI 兼容接口（假设 Azure OpenAI GPT-4o-mini）执行结构化提取，输出统一 JSON。
- **Rationale**: 先用专用工具提取原始文本能显著降低 LLM 成本并提高准确率；函数调用/JSON schema 约束可确保字段完整且便于校验。
- **Alternatives considered**:
  - 纯 LLM 解析原文件：对复杂表格准确率不稳定，且上传二进制成本高。
  - 基于规则的自定义解析：维护成本高，对模糊表达缺乏鲁棒性。

### 2. 自然语言查询转 SQL 的方案
- **Decision**: 构建基于提示模板的 NL2SQL 流程，使用数据库信息（表名、字段、示例记录）生成上下文，让 LLM 输出受约束的 SQL，再使用 SQLGlot 做语法校验与安全重写。
- **Rationale**: 结合 LLM 与语法检查能兼顾灵活度与安全性；SQLGlot 支持方言转换并可过滤潜在危险语句。
- **Alternatives considered**:
  - 直接执行 LLM 产出的 SQL：存在注入与性能风险。
  - 采用专用 NLQ 引擎（如 DBT Semantic Layer）：需要大量先期建模，目前数据量较小，超出范围。

### 3. 多格式文件导入与目录监控
- **Decision**: 后端使用 `watchfiles` 监控指定目录；文件上传与目录事件统一进入“导入任务队列”，通过后台 worker（Celery + Redis）异步处理，处理流程统一调用上述解析服务。
- **Rationale**: 异步队列可避免阻塞 API；统一任务模型可记录进度与审计，满足 FR-005。
- **Alternatives considered**:
  - 使用系统级计划任务读取目录：缺乏错误重试与任务追踪。
  - 同步处理上传：大文件可能导致超时，用户体验差。

### 4. 数据治理与审计日志
- **Decision**: 在每次 AI 入库前生成“待确认快照”，存储原文、解析结果、校验日志与操作者信息，审核通过后写入正式表并生成不可变审计记录（append-only）。
- **Rationale**: 满足财务合规要求，便于追溯；也支持失败回滚。
- **Alternatives considered**:
  - 覆盖写入：缺乏追溯能力。
  - 仅存日志：查询不便且无法恢复原始上下文。

### 5. 前端 AI 聊天体验
- **Decision**: 基于 Expo + React Query 构建统一聊天面板，复用后端 `/api/v1/parse/upload` 与 `/api/v1/query` 接口；对话历史存储在本地 Session 中，并在关键操作（确认写库、生成报表）前提示二次确认。
- **Rationale**: 单一聊天入口符合最新需求；React Query 便于处理轮询与乐观更新。
- **Alternatives considered**:
  - 多个独立表单：与用户更新需求冲突。
  - 使用第三方聊天 SDK：定制化受限，且可能无法满足企业安全要求。

### 6. 图表可视化与报表输出
- **Decision**: 前端使用 Victory Native 渲染图表，后端生成报表则采用 `pandas` + `xlsxwriter`/`pdfkit` 输出可下载文件。
- **Rationale**: Victory 与 Expo 兼容度高；pandas 可轻松处理财务数据透视。
- **Alternatives considered**:
  - D3 自实现：开发成本较高。
  - 仅导出 CSV：无法满足管理层 PDF 报表需求。

