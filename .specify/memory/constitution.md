# FinanceSync Constitution

<!--
Sync Impact Report
- Version change: — → 1.0.0
- Modified principles: (new document)
- Added sections: Core Principles, Implementation Constraints, Delivery Workflow, Governance
- Removed sections: None
- Template updates:
  - ✅ .specify/templates/plan-template.md
  - ✅ .specify/templates/spec-template.md
  - ✅ .specify/templates/tasks-template.md
- Follow-up TODOs: None
-->

## Core Principles

### P1. 分层协同的前后端边界
平台必须保持严格的前后端分离：所有前端资产置于 `frontend/`，所有后端资产置于 `backend/`。任何跨层交互必须通过公开的 REST API 完成，禁止共享数据库层或文件读写。每次集成都要验证接口契约与版本文档同步更新，确保可替换性与可独立部署性。

### P2. Expo TypeScript 前端统一性
前端代码必须基于 Expo (React Native) 并使用 TypeScript (`.tsx`/`.ts`)。样式优先采用 styled-components，必要时可使用 Expo StyleSheet 但需保持可主题化。路由统一使用 `expo-router`，全局状态优先 Context，如超出简单共享才引入 Zustand，并在评审中说明理由。

### P3. FastAPI + PostgreSQL 后端规范
后端必须使用 Python 3.10+ 与 FastAPI，实现完全无状态 REST API。数据持久化只能通过 PostgreSQL，所有模型与端点需具备类型注解与 Pydantic 校验。每个端点要提供 JSON 响应、明确的错误语义，并禁止将会话状态存储在服务器内存。

### P4. 合约优先的接口与测试策略
任何前后端通信都必须有 OpenAPI/JSON Schema 契约；契约更新需驱动对应客户端适配与测试。端点上线前必须具备自动化测试覆盖合同（contract）和关键路径的集成测试。测试与文档属于同一变更集，不得延后。

### P5. 现代化与 AI 感体验
界面设计必须体现现代、简洁与“AI”感：运用一致的主题、微交互、与语义化组件。所有用户可见的新特性都需要设计走查或视觉基准，并确保在 Web、iOS、Android 上保持一致体验。若需引入实验性 AI 功能，需提供回退方案与数据隐私说明。

## Implementation Constraints

- 代码仓库采用 Monorepo，顶层仅允许 `frontend/` 与 `backend/` 存放运行时代码，公共脚手架放置于各自目录 `shared/` 子层内。
- 配置文件必须通过环境变量管理：前端使用 Expo 配置插件，后端使用 `pydantic-settings`；不得将密钥写入仓库。
- 数据库迁移需使用 Alembic 并存放于 `backend/migrations/`；变更必须向后兼容并包含回滚脚本。
- 前端 API 调用封装在 `frontend/src/services/`，并在同路径维护契约类型定义，禁止直接在组件中发送裸请求。

## Delivery Workflow

- 需求立项前必须完成“Constitution Check”，确认技术栈、目录结构、测试与契约要求均已识别。
- Feature 研发流程遵循：研究 → 设计 → 契约 → 实现 → 验收；每阶段输出对齐 `.specify/templates/*.md`，任何偏离需治理组批准。
- 代码评审需显式确认：原则遵循情况、API 契约更新、测试覆盖、UI 设计一致性。未完成检查项时不得合入主分支。
- 发布管道需确保后端通过 CI 执行类型检查、单元/集成测试，前端通过 Expo EAS 构建与 UI 快照校验；构建失败阻断发布。

## Governance

- 本宪章优先级高于项目内其他文档；冲突时以宪章为准。
- 任一变更必须在 PR 描述中说明受影响的原则与检查项，审查者负责确认遵循性。
- 宪章修订流程：提出变更 → 撰写差异说明与版本影响 → 至少两名核心维护者批准 → 同步更新相关模板与指南 → 合入主分支。
- 版本语义化：新增原则或新增强制约为 MINOR 升级；破坏性调整或删除原则为 MAJOR；措辞澄清或非语义性更新为 PATCH。
- 宪章至少每季度复审一次；复审需记录决议并在 README 或治理日志中链接结果。

**Version**: 1.0.0 | **Ratified**: 2025-11-08 | **Last Amended**: 2025-11-08
