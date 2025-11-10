# Tasks: 财务数据统一平台

**Input**: Design documents from `/specs/001-finance-data-hub/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Contract与集成测试标注在各用户故事阶段，确保 AI 接口与仪表板数据符合宪章的契约优先要求。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/` 下分别存放 `api/`, `services/`, `repositories/`, `schemas/`, `workers/`
- **Frontend**: `frontend/app/`（expo-router 结构），共享组件位于 `frontend/components/`
- **Tests**: `backend/tests/{contract,integration,unit}`，`frontend/tests/{unit,e2e}`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 引入所需依赖与基础配置，为后续开发提供统一环境。

- [x] T001 更新 Celery、watchfiles、SQLGlot、pandas 依赖到 `backend/pyproject.toml`
- [x] T002 更新 Victory Native、React Query、Zustand 依赖到 `frontend/package.json`
- [x] T003 同步环境变量模板以支持 LLM/Redis/监控目录配置 `backend//.env.example`
- [x] T004 添加前端 API 基址与聊天助手配置项 `frontend/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 完成所有用户故事共享的底层能力，包含数据库结构、异步处理和通用服务。

- [x] T005 创建财务核心实体与审计日志的 Alembic 迁移 `backend/migrations/versions/`  
- [x] T006 实现导入任务与财务记录的 SQLAlchemy 模型 `backend/app/models/financial.py`
- [x] T007 构建统一的 LLM 客户端与解析器接口 `backend/app/services/llm_client.py`
- [x] T008 初始化 Celery 配置与任务入口 `backend/app/workers/__init__.py`
- [x] T009 实现文件存储适配器（本地/S3） `backend/app/services/storage_adapter.py`
- [x] T010 建立目录监控调度器骨架 `backend/app/workers/directory_watcher.py`
- [x] T011 配置前端全局状态容器（Context + Zustand） `frontend/src/state/financeStore.ts`
- [x] T012 搭建前端 API 客户端基础封装 `frontend/src/services/apiClient.ts`

---

## Phase 3: User Story 1 - 财务数据采集与校验 (Priority: P1) 🎯 MVP

**Goal**: 让财务人员通过 AI 对话窗口导入/解析多源财务数据并完成确认入库。

**Independent Test**: 通过聊天窗口粘贴样例文本、上传文件、触发目录监控各一次，确认候选记录生成、人工确认后写库，数据库产生审计日志。

### Tests for User Story 1 ⚠️

- [x] T013 [P] [US1] 编写 `/api/v1/parse/upload` 契约测试 `backend/tests/contract/test_parse_upload.py`
- [x] T014 [US1] 实现导入流程集成测试（上传→确认→入库） `backend/tests/integration/test_import_flow.py`

### Implementation for User Story 1

- [x] T015 [P] [US1] 定义导入与校验 Pydantic 模型 `backend/app/schemas/imports.py`
- [x] T016 [P] [US1] 实现 ImportJob 仓储层 `backend/app/repositories/import_jobs.py`
- [x] T017 [US1] 开发 AI 解析编排服务（包含预处理与 LLM 函数调用） `backend/app/services/ai_parser.py`
- [x] T018 [US1] 实现 Celery 导入处理任务逻辑 `backend/app/workers/import_processor.py`
- [x] T019 [US1] 构建 `/api/v1/parse/upload` 与 `/api/v1/import-jobs/{id}` API `backend/app/api/v1/imports.py`
- [x] T020 [P] [US1] 实现导入确认与审计记录写入 `backend/app/api/v1/imports_confirm.py`
- [x] T021 [US1] 完成目录监控触发与去重逻辑 `backend/app/workers/directory_watcher.py`
- [x] T022 [P] [US1] 实现 AI 聊天上传与解析 UI `frontend/app/(app)/ai-chat/index.tsx`
- [x] T023 [P] [US1] 创建候选记录预览与校验提示组件 `frontend/components/imports/ImportPreview.tsx`
- [x] T024 [US1] 构建导入历史视图供财务追溯 `frontend/app/(app)/history/index.tsx`
- [x] T024A [US1] 设计收入/支出/预期收入分类树结构表并更新模型、迁移脚本
- [x] T024B [US1] 调整业务记录引用新的分类表，确保导入与展示兼容
- [x] T024C [US1] 拆分“数据录入”与“查询分析”两套 AI 对话路由及状态管理 `frontend/app/(app)`
- [x] T024D [US1] 后端会话上下文与日志按对话类型区分存储，接口层暴露独立端点
- [x] T024E [US1] 扩展导入模型与仓储以支持收入/支出预测的去重与覆盖 `backend/app/repositories/import_jobs.py`
- [x] T024F [US1] 新增支出预测实体、迁移与导入测试 `backend/app/models/financial.py`, `backend/migrations/`, `backend/tests/integration/test_import_flow.py`

**Checkpoint**: AI 对话导入流程可从输入到确认全程跑通并写入数据库。

---

## Phase 4: User Story 2 - 管理层查看统一看板 (Priority: P2)

**Goal**: 提供现代化报表看板，支持时间、公司、类别维度筛选，并可导出报表。

**Independent Test**: 预置样例数据后，切换不同日期和公司查看图表刷新，导出报表并校验内容与筛选条件匹配。

### Tests for User Story 2 ⚠️

- [x] T025 [US2] 编写财务看板聚合集成测试 `backend/tests/integration/test_financial_overview.py`

### Implementation for User Story 2

- [x] T026 [P] [US2] 实现财务统计服务（缓存最新快照） `backend/app/services/financial_overview.py`
- [x] T027 [US2] 构建 `/api/v1/financial/overview` API 与权限校验 `backend/app/api/v1/overview.py`
- [ ] T028 [P] [US2] 开发报表导出服务（CSV + PDF） `backend/app/services/report_exporter.py`
- [ ] T029 [US2] 集成导出接口 `backend/app/api/v1/reports.py`
- [x] T030 [P] [US2] 实现看板页面与筛选控件 `frontend/app/(app)/dashboard/index.tsx`
- [x] T031 [P] [US2] 构建复用型图表组件 `frontend/components/charts/FinancialTrends.tsx`
- [x] T031A [US2] 优化仪表板收入汇总，对预测数据进行颜色标识与层级筛选 `frontend/app/(app)/dashboard/index.tsx`
- [x] T031B [US2] 聚合预测现金流卡片，整合收入/支出预测与全局汇总 `backend/app/services/financial_overview.py`
- [ ] T032 [US2] 在看板中接入导出与历史快照展示 `frontend/app/(app)/dashboard/export.tsx`

**Checkpoint**: 管理层可在前端查看最新与历史数据，并成功导出符合筛选条件的报表。

---

## Phase 5: User Story 3 - AI 辅助解析与查询 (Priority: P3)

**Goal**: 让用户通过自然语言查询财务数据并自动选择合适的可视化展示。

**Independent Test**: 在聊天窗口发起多个查询（趋势对比、预测解读），确认生成 SQL 安全、结果准确且图表类型匹配问题意图。

### Tests for User Story 3 ⚠️

- [ ] T033 [P] [US3] 编写 `/api/v1/query` 契约测试覆盖常见问题模板 `backend/tests/contract/test_nlq_query.py`
- [ ] T034 [US3] 实现 NLQ 解析到 SQL 的集成测试（含 SQLGlot 校验） `backend/tests/integration/test_nlq_flow.py`

### Implementation for User Story 3

- [ ] T035 [P] [US3] 定义 NLQ 请求/响应模型与安全约束 `backend/app/schemas/nlq.py`
- [ ] T036 [US3] 开发 NLQ 服务（提示模板、SQLGlot 校验、结果裁剪） `backend/app/services/nlq_service.py`
- [ ] T037 [US3] 实现 `/api/v1/query` API 并记录查询历史 `backend/app/api/v1/nlq.py`
- [ ] T038 [P] [US3] 增加 NLQ 查询仓储与审计记录 `backend/app/repositories/nlq_queries.py`
- [ ] T039 [P] [US3] 扩展前端 AI 聊天以支持查询意图与多轮上下文 `frontend/app/(app)/ai-chat/query.tsx`
- [ ] T040 [US3] 构建 NLQ 结果呈现组件（表格/图表自动切换） `frontend/components/charts/NlqResultPanel.tsx`
- [ ] T041 [P] [US3] 补充前端查询历史与反馈交互 `frontend/app/(app)/history/query-log.tsx`

**Checkpoint**: 自然语言查询能够稳定产出可信结果并在前端以合适图表展示。

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: 完成跨故事的性能、监控、安全与文档收尾。

- [ ] T042 [P] 增加后端速率限制与身份校验策略文档 `backend/app/api/deps/rate_limit.py`
- [ ] T043 整合日志与追踪（结构化日志 + TraceID） `backend/app/services/logging.py`
- [ ] T044 [P] 完善前端无障碍与主题适配 `frontend/themes/accessibility.ts`
- [ ] T045 验证 quickstart 步骤并更新样例数据 `specs/001-finance-data-hub/quickstart.md`
- [ ] T046 [P] 运行全量契约/集成测试并记录结果 `backend/tests/`
- [ ] T047 完成部署脚本与运维手册更新 `docs/operations/finance-sync.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，需要优先完成以锁定依赖与环境。
- **Foundational (Phase 2)**: 依赖 Phase 1；完成后 AI 解析、数据存储、队列等基础能力具备。
- **User Story 1 (Phase 3)**: 依赖 Phase 2，完成后可交付最小可用产品（MVP）。
- **User Story 2 (Phase 4)**: 依赖 Phase 3 导入的数据结构；可与部分 US3 前端工作并行。
- **User Story 3 (Phase 5)**: 依赖 Phase 2 与导入数据，建议在 US1 稳定后启动。
- **Polish (Final Phase)**: 所有故事完成后收尾。

### User Story Dependencies

- **US1 (P1)**: 无故事依赖，提供数据来源与审计能力。
- **US2 (P2)**: 读取 US1 存储的数据，需 US1 完成。
- **US3 (P3)**: 需要 US1 的结构化数据，US2 的聚合逻辑可复用但非硬性依赖。

### Parallel Opportunities

- Setup 完成后，可并行处理 `T005`~`T012` 只要不同文件。
- US1 实施时，后端 Celery 任务（T018）与前端 UI（T022-T024）可并行开发。
- US2 中的图表组件（T031）与报表导出（T028）互不依赖。
- US3 的前端展示（T040-T041）可在后端 NLQ 服务（T036-T038）开发期间并行。

### Within Each User Story

- 优先完成契约/集成测试脚手架（T013-T014、T025、T033-T034）。
- 模型与服务（T015-T018、T026-T028、T035-T038）在端点与前端实现前完成。
- 前端任务在对应 API 准备就绪后联调；图表/展示组件可并行开发并通过 mock 数据验证。

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 + Phase 2，建立解析、队列与审计基础。
2. 实现并验证 AI 导入流程（US1），确保财务数据可入库。
3. 发布内部 MVP，收集财务团队反馈。

### Incremental Delivery

1. MVP（US1）上线并稳定运行。
2. 增量交付 US2 看板能力，满足管理层可视需求。
3. 引入 US3 自然语言查询，提升智能化体验。
4. Polish 阶段统一优化性能、监控与文档。

### Parallel Team Strategy

1. 团队完成 Setup 与 Foundational 阶段。
2. 后端一组专注 US1 导入与 Celery 流程，前端一组构建 AI 聊天与预览。
3. 待 US1 进入测试后，第二组后端/前端并行推进 US2 看板与 US3 NLQ。
4. 合并完成后共同处理 Polish 任务，准备上线。

