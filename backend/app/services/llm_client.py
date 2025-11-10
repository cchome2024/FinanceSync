from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Dict, Iterable

import httpx

from app.core.config import get_settings


class LLMClientError(RuntimeError):
    """LLM 调用失败时抛出的异常。"""


class LLMClientParseError(LLMClientError):
    """LLM 返回内容无法解析为结构化 JSON 时抛出的异常。"""

    def __init__(self, message: str, raw_text: str) -> None:
        super().__init__(message)
        self.raw_text = raw_text


class LLMClient:
    """封装与 LLM 服务的交互。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = settings.llm_endpoint.rstrip("/")
        self._deployment = settings.llm_deployment
        self._api_key = settings.llm_api_key
        self._provider = settings.llm_provider
        timeout = getattr(settings, "llm_timeout_seconds", 0) or 120
        self._client = httpx.AsyncClient(timeout=timeout)

    async def parse_financial_payload(self, prompt: str, attachments: Iterable[bytes] | None = None) -> Dict[str, Any]:
        if self._provider == "mock":
            print("[LLM MOCK] parse_financial_payload invoked; returning empty records")
            return {
                "records": []
            }

        payload: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        attach_list = list(attachments or [])
        if attach_list:
            payload["attachments"] = [f"<binary:{len(item)}>" for item in attach_list]

        print(f"[LLM REQUEST] provider={self._provider}, endpoint={self._endpoint}, payload={json.dumps(payload, ensure_ascii=False)[:2000]}", flush=True)
        response = await self._request(payload)
        print(f"[LLM RESPONSE] provider={self._provider}, raw={str(response)[:2000]}", flush=True)
        try:
            content = response["choices"][0]["message"]["content"]
            return self._parse_json_content(content)
        except (KeyError, ValueError) as exc:
            raise LLMClientError("Failed to parse LLM response") from exc

    async def run_nlq(self, question: str, schema_snapshot: Dict[str, Any]) -> str:
        if self._provider == "mock":
            print("[LLM MOCK] run_nlq invoked; returning empty JSON string")
            return "{}"

        payload = {
            "messages": [
                {"role": "system", "content": self._build_nlq_prompt(schema_snapshot)},
                {"role": "user", "content": question},
            ],
            "temperature": 0.0,
        }
        print(f"[LLM REQUEST] provider={self._provider}, endpoint={self._endpoint}, payload={json.dumps(payload, ensure_ascii=False)[:2000]}", flush=True)
        response = await self._request(payload)
        print(f"[LLM RESPONSE] provider={self._provider}, raw={str(response)[:2000]}", flush=True)
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise LLMClientError("LLM response missing content") from exc

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._provider == "azure_openai":
            url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions?api-version=2024-02-01"
            headers = {
                "api-key": self._api_key,
                "Content-Type": "application/json",
            }
        elif self._provider == "mock":
            print("[LLM MOCK] _request bypassed")
            return {"choices": [{"message": {"content": "{}"}}]}
        else:
            url = f"{self._endpoint.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            payload = dict(payload)
            payload.setdefault("model", self._deployment)

        print(f"[LLM HTTP] POST {url} headers={headers}", flush=True)
        response = await self._client.post(url, headers=headers, json=payload)
        print(f"[LLM HTTP] status={response.status_code}", flush=True)
        if response.status_code >= 400:
            print(f"[LLM ERROR] body={response.text[:2000]}", flush=True)
            raise LLMClientError(f"LLM request failed: {response.status_code} {response.text}")
        return response.json()

    def _parse_json_content(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except JSONDecodeError as exc:
                    raise LLMClientParseError("LLM response is not valid JSON", text) from exc
            raise LLMClientParseError("LLM response is not valid JSON", text)

    def _build_system_prompt(self) -> str:
        return (
            "你是 FinanceSync 的财务数据解析助手。请从用户提供的原始文本或表格中，"
            "抽取结构化财务信息，并严格按照下述 JSON Schema 输出。"
            "结果必须是单个 JSON 对象，且仅包含一个顶层键 `records`。不可输出解释性文字。\n"
            "JSON 结构示例：\n"
            "{\n"
            "  \"records\": [\n"
            "    {\n"
            "      \"record_type\": \"account_balance\",\n"
            "      \"payload\": { ... },\n"
            "      \"confidence\": 0.93,\n"
            "      \"warnings\": []\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "字段说明：\n"
            "- `record_type`: 必填，使用以下枚举之一：\n"
            "  - `account_balance`: 账户余额。\n"
            "  - `revenue`: 收入明细（按发生日期逐条记录）。\n"
            "  - `expense`: 支出记录（按月份统计）。\n"
            "  - `income_forecast`: 未来收入预测（兼容旧格式）。\n"
            "  - `revenue_forecast`: 预测收入明细，字段与 `revenue` 类似，但代表未来款项。\n"
            "  - `expense_forecast`: 未来支出预测明细，字段与 `income_forecast` 类似，但现金流为支出。\n"
            "- `payload`: 对应记录的详细字段。不同 record_type 需要的字段如下：\n"
            "  * account_balance: `company_id`(字符串，若未知留空), `reported_at`(ISO8601日期时间), `cash_balance`(数字), `investment_balance`(数字, 可为0), `total_balance`(数字), `currency`(字符串, 缺省填 \"CNY\"), `notes`(可选字符串)。\n"
            "  * revenue: `company_id`, `occurred_on`(YYYY-MM-DD), `amount`(数字，单位为人民币元，若原始数据以“万元”等需要先换算成元), `currency`(默认 \"CNY\"), `category_path`(数组或\"大类/二类/...\" 字符串，表示收入分类层级), `description`(可选，款项内容或备注), `account_name`(可选到账账户), `confidence`(可选0-1小数), `notes`(可选)。\n"
            "  * expense: `company_id`, `month`, `category`, `amount`, `currency`(默认 \"CNY\"), `confidence`(可选), `notes`(可选)。\n"
            "  * income_forecast / revenue_forecast: `company_id`, `cash_in_date` 或 `occurred_on`(YYYY-MM-DD，表示预计到账日期), `expected_amount` 或 `amount`(数字，单位为人民币元), `currency`(默认 \"CNY\"), `category_path`(数组或\"大类/二类/...\" 字符串，表示收入分类层级), `description`(可选), `account_name`(可选), `certainty`(`certain` 或 `uncertain`，默认 `certain`), `confidence`(可选0-1小数), `notes`(可选)。\n"
            "  * expense_forecast: `company_id`, `cash_out_date` 或 `occurred_on`(YYYY-MM-DD，表示预计支出日期), `expected_amount` 或 `amount`(数字，单位为人民币元), `currency`(默认 \"CNY\"), `category_path`(数组或\"大类/二类/...\" 字符串，表示支出分类层级), `description`(可选), `account_name`(可选付款账户), `certainty`(`certain` 或 `uncertain`，默认 `certain`), `confidence`(可选0-1小数), `notes`(可选)。\n"
            "- `confidence`: 可选，若给出需为 0-1 之间的小数。\n"
            "- `warnings`: 可选字符串数组，若无预警请输出空数组。\n"
            "其它要求：\n"
            "1. 所有数字字段输出十进制数字，不要包含单位或千分符。\n"
            "2. 若文本中无法确认某字段，请省略该字段或使用合理默认值，不要编造。\n"
            "3. 如果无法提取任何记录，返回 `{\"records\": []}`。"
        )

    def _build_nlq_prompt(self, schema_snapshot: Dict[str, Any]) -> str:
        return (
            "你是一名 SQL 生成专家。请参考以下数据库结构并生成安全、只读的 SQL。"
            f" 数据结构: {json.dumps(schema_snapshot)}"
        )


async def get_llm_client() -> LLMClient:
    return LLMClient()

