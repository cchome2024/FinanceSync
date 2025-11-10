# 数据模型设计：财务数据统一平台

## 实体概览

| 实体 | 描述 | 关键关系 |
|------|------|----------|
| AccountBalance | 各公司账户在特定时间点的余额与理财金额快照 | 属于 Company；由 ImportJob 生成 |
| RevenueDetail | 收入明细原子记录，按发生日期与多级分类存储 | 属于 Company；关联 ImportJob |
| ExpenseRecord | 支出明细，按大类/月份记录 | 属于 Company；关联 ImportJob |
| IncomeForecast | 收入预测，包含确定性/非确定性、资管产品维度 | 属于 Company；可与 RevenueDetail 做对比 |
| ExpenseForecast | 支出预测，记录未来现金流出时间与金额 | 属于 Company；可与 ExpenseRecord 做对比 |
| ImportJob | 描述一次 AI 导入任务（上传或目录监控）及状态 | 关联多条 AccountBalance/RevenueDetail/ExpenseRecord/IncomeForecast |
| ConfirmationLog | 记录用户或 AI 的确认操作、修改意见 | 关联 ImportJob 与具体财务记录 |
| NlqQuery | 自然语言问题及执行结果快照 | 可引用生成的报表或图表配置 |
| Company | 公司主体或账户归属信息 | 与所有财务数据实体关联 |
| Attachment | 存储原始文件或截取的 OCR 文本 | 关联 ImportJob |

## 实体详情

### Company
- **字段**: `id`, `name`, `display_name`, `currency`, `created_at`, `updated_at`
- **约束**: `name` 唯一；默认币种为 CNY。
- **关系**: `has_many` AccountBalance/RevenueDetail/ExpenseRecord/IncomeForecast/ExpenseForecast。

### ImportJob
- **字段**: `id`, `source_type` (manual_upload / watched_dir / ai_chat), `status` (pending_review / approved / rejected / failed), `initiator_id`, `initiator_role`, `llm_model`, `confidence_score`, `started_at`, `completed_at`, `raw_payload_ref`, `error_log`
- **行为**: 状态机允许 `pending_review → approved/rejected/failed`；失败可重试。
- **关系**: `has_many` attachments, confirmation_logs, financial records。

### Attachment
- **字段**: `id`, `import_job_id`, `file_type`, `storage_path`, `text_snapshot`, `checksum`, `created_at`
- **约束**: `checksum` 去重；`text_snapshot` 保存 OCR/解析后的文本。

### AccountBalance
- **字段**: `id`, `company_id`, `import_job_id`, `reported_at`, `cash_balance`, `investment_balance`, `total_balance`, `currency`, `notes`
- **验证**: 金额字段需为非负数；`total_balance = cash_balance + investment_balance`。

### RevenueDetail
- **字段**: `id`, `company_id`, `import_job_id`, `occurred_on`, `amount`, `currency`, `category_id`, `category_path_text`, `category_label`, `subcategory_label`, `description`, `account_name`, `confidence`, `notes`, `created_at`, `updated_at`
- **验证**: `occurred_on` 使用 ISO 日期；金额以人民币“元”为单位；`category_path_text` 记录原始多级分类（如 “资管/自主募集/管理费”）；`category_id` 自动与 `FinanceCategory` 对应；置信度 0-1。
- **说明**: 所有收入汇总（按月份、按分类）均通过 `RevenueDetail` 聚合计算，不再由人工直接录入汇总值。

### ExpenseRecord
- **字段**: `id`, `company_id`, `import_job_id`, `month`, `category`, `amount`, `currency`, `confidence`, `notes`
- **验证**: 同收入；金额允许为零但不能为负。

### IncomeForecast
- **字段**: `id`, `company_id`, `import_job_id`, `cash_in_date`, `product_line`, `product_name`, `certainty` (certain/uncertain), `category`, `expected_amount`, `currency`, `confidence`, `notes`
- **验证**: `expected_amount` > 0；`certainty` 枚举；`cash_in_date` 允许历史月份（回填预测数据时保持原始日期）。

### ExpenseForecast
- **字段**: `id`, `company_id`, `import_job_id`, `cash_out_date`, `category`, `category_path_text`, `category_label`, `subcategory_label`, `certainty`, `expected_amount`, `currency`, `account_name`, `description`, `confidence`, `notes`
- **约束**: 以公司、日期、分类、描述、账户为自然键，避免重复；金额必须大于 0。
- **用途**: 与 IncomeForecast 一同驱动预测现金流卡片，支出侧按月份聚合，提示确定性。

### ConfirmationLog
- **字段**: `id`, `import_job_id`, `record_type`, `record_id`, `actor_id`, `actor_role`, `action` (confirmed/edited/rejected), `diff_snapshot`, `