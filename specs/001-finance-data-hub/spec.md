# Feature Specification: 财务数据统一平台

**Feature Branch**: `001-finance-data-hub`  
**Created**: 2025-11-08  
**Status**: In Progress  
**Input**: User description: "我想做一个内部财务数据录入、存储和查看的平台，数据能够进行统一展示。财务数据包括账户余额、收入、支出以及收入预测，需要支持手工录入、图片/文件导入、目录自动读取，并在录入与展示界面提供 AI 解析与查询能力。"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - 财务数据采集与校验 (Priority: P1)

财务人员能够通过专用的“数据录入”AI 对话窗口粘贴文本、输入自然语言或上传附件，完成账户余额、收入、支出和收入预测的数据采集，并在确认前得到结构化预览与校验反馈。

**Why this priority**: 数据采集是平台价值的基础，若无法稳定录入，则后续的展示与分析均无从实现。

**Independent Test**: 通过手工录入、文件上传、目录导入三种方式完成数据采集，并验证数据库中产生的记录及校验反馈。

**Acceptance Scenarios**:

1. **Given** 财务人员打开 AI 对话框，**When** 在聊天输入框粘贴账户余额描述并发送“请入库”，**Then** 系统返回待确认的结构化条目，用户确认后记录写入并显示成功提示。
2. **Given** 财务人员在对话框上传包含收入与支出的 Excel/CSV 文件，**When** 系统完成解析，**Then** 聊天窗口展示分组结果与差异提醒，允许用户通过追加消息修改或确认后入库。
3. **Given** 平台已配置自动读取目录，**When** 指定目录出现新文件，**Then** 系统触发解析并生成待审核条目，通知财务人员确认。

---

### User Story 2 - 管理层查看统一看板 (Priority: P2)

管理层能够在可视化看板中查看最新财务数据，并按时间节点、公司、类别等维度切换，获取关键指标对比。

**Why this priority**: 决策层需要快速了解财务现状，平台必须提供即时准确的展示能力。

**Independent Test**: 从空白环境导入样例数据，登录管理页面，验证看板默认呈现最新数据，并可切换到历史日期获取对应视图。

**Acceptance Scenarios**:

1. **Given** 看板加载完成，**When** 用户选择“最新数据”，**Then** 展示最近一次记录的余额、收入、支出、预测概览。
2. **Given** 用户选择历史月份并按大类筛选，**When** 点击应用筛选，**Then** 图表与表格均更新为对应时间段和类别数据。
3. **Given** 用户需要导出报表，**When** 点击导出按钮，**Then** 系统生成包含当前筛选条件的标准财务报表文件。（当前迭代暂缓实施导出能力，需求保留）

---

### User Story 3 - AI 辅助解析与查询 (Priority: P3)

财务与业务人员可以在独立的“查询分析”AI 对话窗口中上传原始资料、提出自然语言问题，系统返回结构化结果或数据洞察。

**Why this priority**: AI 辅助能显著提升录入效率与分析体验，是平台差异化能力。

**Independent Test**: 通过聊天窗口上传原始文本触发解析，并提出多种自然语言问题，验证系统能够返回正确的整理结果与图表。

**Acceptance Scenarios**:

1. **Given** 用户在 AI 聊天窗口粘贴银行对账单文本，**When** 发送“解析为账户余额”，**Then** 系统调用解析端点并返回可确认的结构化金额条目。
2. **Given** 用户提出“展示本季度收入趋势并标注预测”，**When** 系统完成查询，**Then** 返回趋势图和摘要说明，同时提供数据来源链接。
3. **Given** AI 无法解析或结果存在冲突，**When** 系统检测到异常，**Then** 返回人类可读的错误提示并允许用户改用手动录入。

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- 上传文件编码或表头不符合约定时，系统应给出可修复建议并阻止入库。
- 自动目录读取遇到重复文件时需识别并避免重复入库，同时提示审核。
- AI 解析返回低置信度结果时，平台应标记为“待人工确认”，并提供手动编辑入口。
- 历史数据缺失某月份时，看板应以缺口示意并允许补录。
- 自然语言问题超出权限范围（如请求敏感账户），系统需要拒绝并提示权限不足。

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: 系统必须在 AI 聊天窗口中支持财务人员以自然语言或表格文本描述账户余额、收入、支出、收入预测，解析后给出结构化预览并允许用户确认或编辑后入库。
- **FR-002**: 系统必须允许在 AI 聊天窗口中上传 CSV、Excel、PDF、图片等文件，调用解析器返回结构化结果与校验提示，用户通过后续消息确认才写入正式库。
- **FR-003**: 系统必须支持配置指定文件目录进行周期性扫描，发现新文件后自动触发解析流程并生成待审核记录。
- **FR-004**: 系统必须对所有入库数据执行完整性校验（金额为数值、日期合法、类别匹配预设字典），校验失败时给出准确错误提示。
- **FR-005**: 系统必须记录每次数据变更的来源、时间、操作者/AI 任务，供后续追溯。
- **FR-006**: 平台必须提供仪表板，默认展示最近一次审核通过的数据，并允许按时间、公司主体、费用/收入类别切换视图。
- **FR-007**: 平台必须支持收入预测数据按确定性与非确定性分类展示，并在资管类别下细分到具体产品。
- **FR-008**: 系统必须提供自然语言查询入口，用户输入问题后，平台根据授权生成对应的数据汇总与推荐图表，并以可下载形式输出。
- **FR-009**: 前端必须提供两个独立的 AI 对话入口——“数据录入”用于触发采集/确认流程，“查询分析”用于自然语言提问；系统需分别记录对话上下文并允许切换历史会话。
- **FR-010**: 平台必须提供导出功能，将当前筛选条件下的财务数据生成标准报表（含 CSV 与可读版 PDF）。*当前迭代暂缓实施，待后续 Phase 4.2 处理。*
- **FR-011**: 系统必须维护收入、支出、预期收入共用的多层级分类树，分类节点可在导入时自动创建或映射，业务记录需引用分类 ID 以支持树形汇总。

### Key Entities *(include if feature involves data)*

- **AccountBalance**: 记录各公司账户在特定时间点的余额与理财金额，包含来源文件及确认状态。
- **RevenueDetail**: 存储收入原子明细，包含发生日期、金额（以元为单位）、多级分类路径、到账账户、描述及置信度；所有收入汇总数据均由该表聚合计算，仪表板默认展示到分类树的第二层。
- **ExpenseRecord**: 记录各大类月度支出金额和备注，支持多币种换算。
- **IncomeForecast**: 管理确定性与非确定性预测，细化到资管产品与现金流时间点。
- **ImportJob**: 描述一次手工或自动导入的元数据，包括触发方式、处理日志、AI 解析结果。
- **NlqQuery**: 保存自然语言问题、解析出的查询模型、返回的数据视图与生成的图表类型。
- **FinanceCategory**: 描述收入/支出/预期收入的多层级分类结构，包含节点路径、层级、启用状态，供录入与看板汇总复用。

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: 财务人员可在 10 分钟内完成一次包含至少 20 条记录的导入与审核，且错误率低于 5%。
- **SC-002**: 仪表板在选择任意时间节点后 3 秒内刷新完成，数据准确率达到 100%（与数据库对比无误差）。
- **SC-003**: AI 解析对样例财务文件能够在首次尝试时提供可用结构化结果的比例不低于 85%。
- **SC-004**: 自然语言查询能够覆盖至少 10 个高频问题场景，用户满意度调查中“获得所需答案”选项得分≥4/5。
- **SC-005**: 系统完成上线后一个财务周期内，管理层对比传统报表准备时间减少至少 50%。

## Assumptions

- LLM 供应商与模型选择由公司既有合规策略决定，本规格默认可调用已有企业版 API。
- 财务数据权限遵循公司现行角色体系：财务人员负责录入与审核，管理层拥有查看与分析权限。
- 默认支持人民币记账，其他币种通过后台配置扩展并自动换算。
