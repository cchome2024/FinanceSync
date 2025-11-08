# Implementation Plan: 财务数据统一平台

**Branch**: `001-finance-data-hub` | **Date**: 2025-11-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-finance-data-hub/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

构建一个面向财务与管理层的统一数据平台：通过单一 AI 对话窗采集账户余额、收入、支出、收入预测，并将 AI 解析结果在人工确认后写入 PostgreSQL；提供自然语言查询与现代化仪表板，实现跨时间节点对比及报表导出。技术上采用“预处理 + LLM 函数调用”解析流程、NL2SQL + SQLGlot 校验机制，以及基于 Expo 的多端聊天与看板体验。

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Frontend Expo (React Native + TypeScript 5.x); Backend Python 3.11 (FastAPI)  
**Primary Dependencies**: Expo Router, styled-components, React Query, Zustand（按需）；FastAPI, Pydantic v2, SQLAlchemy, Alembic, Celery, Redis, PostgreSQL, Azure OpenAI (兼容 API), SQLGlot, watchfiles, pandas  
**Storage**: PostgreSQL 14+（财务数据与审计日志）；S3 兼容对象存储（附件）  
**Testing**: 前端 Jest + React Testing Library + Playwright；后端 pytest + httpx + pytest-asyncio；契约测试使用 schemathesis  
**Target Platform**: Expo Web、iOS、Android（统一代码基）  
**Project Type**: Monorepo，`frontend/` + `backend/` 严格分离  
**Performance Goals**: 看板刷新 ≤3 秒；AI 解析任务 ≤2 分钟完成；NLQ 响应 ≤10 秒（含 LLM 调用）  
**Constraints**: 必须经 REST JSON 通信；所有密钥通过环境变量注入；AI 结果需人工确认后入库；遵守财务数据访问权限  
**Scale/Scope**: 内部 3-5 名财务人员 + 5-10 名管理层；日均导入文件 < 50 个，NLQ 查询 < 200 次

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **P1 分层协同**：前后端保持在 `frontend/`、`backend/`，接口均为 REST JSON，计划通过 OpenAPI 保持契约同步 —— ✅
- **P2 Expo TypeScript**：前端方案基于 Expo + TypeScript，使用 styled-components、expo-router、按需 Zustand —— ✅
- **P3 FastAPI + PostgreSQL**：后端采用 FastAPI + PostgreSQL + Alembic，保证无状态 API，Celery worker 仅处理异步任务 —— ✅
- **P4 合约优先与测试**：开放 `/contracts/openapi.yaml`，计划使用 schemathesis、pytest 集成测试覆盖解析/查询端点 —— ✅
- **P5 现代化 + AI 感**：设计统一 AI 聊天体验、趋势图表与主题化 UI；Victory + 设计走查纳入任务 —— ✅
- **Implementation Constraints**：环境变量/密钥管理、Alembic 迁移、前端服务封装、监控目录通过 worker 异步处理 —— ✅
> 评估结果：无违例，允许进入 Phase 0 研究。

## Project Structure

### Documentation (this feature)

```text
specs/001-finance-data-hub/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md              # 由 /speckit.tasks 生成
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

backend/
frontend/
├── app/
│   ├── api/
│   │   └── v1/
│   ├── services/
│   ├── schemas/
│   ├── repositories/
│   └── workers/
├── migrations/
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── app/                  # expo-router routes
│   ├── (app)/ai-chat/
│   ├── (app)/dashboard/
│   └── (app)/history/
├── components/
├── hooks/
├── services/
├── themes/
└── tests/
    ├── unit/
    └── e2e/
```

**Structure Decision**: 延续宪章要求的前后端分离结构；后端新增 `workers/` 处理 Celery 任务、`schemas/` 管理 Pydantic 模型；前端围绕 expo-router 的 `(app)` 目录组织 AI 聊天与仪表板页面，所有 API 调用位于 `services/`。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

当前无违例，无需记录复杂度豁免。
