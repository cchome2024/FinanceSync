from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from backend.app.core.config import get_settings


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    """LLM 客户端封装，负责与供应商通信并输出结构化结果�?""

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = settings.llm_endpoint.rstrip("/")
        self._deployment = settings.llm_deployment
        self._api_key = settings.llm_api_key
        self._provider = settings.llm_provider
        self._client = httpx.AsyncClient(timeout=60)

    async def parse_financial_payload(self, prompt: str, attachments: List[bytes] | None = None) -> Dict[str, Any]:
        """调用 LLM 将非结构化数据解析为财务结构化条目�?""

        payload: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        if attachments:
            payload["attachments"] = ["<binary:{}>".format(len(item)) for item in attachments]

        response = await self._request(payload)
        try:
            return json.loads(response["choices"][0]["message"]["content"])
        except (KeyError, ValueError) as exc:
            raise LLMClientError("Failed to parse LLM response") from exc

    async def run_nlq(self, question: str, schema_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "messages": [
                {"role": "system", "content": self._build_nlq_prompt(schema_snapshot)},
                {"role": "user", "content": question},
            ],
            "temperature": 0.0,
        }
        response = await self._request(payload)
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise LLMClientError("LLM response missing content") from exc

    async def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._provider != "azure_openai":
            raise LLMClientError(f"Unsupported LLM provider: {self._provider}")

        url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions?api-version=2024-02-01"
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        response = await self._client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMClientError(f"LLM request failed: {response.status_code} {response.text}")
        return response.json()

    def _build_system_prompt(self) -> str:
        return (
            "你是一名财务数据解析助手。根据用户提供的文本或表格，"
            "输出包含账户余额、收入、支出、收入预测的 JSON，字段需符合平台 schema�?
        )

    def _build_nlq_prompt(self, schema_snapshot: Dict[str, Any]) -> str:
        return (
            "你是一�?SQL 生成专家。请参考以下数据库结构并生成安全、只读的 SQL�?
            f" 数据结构: {json.dumps(schema_snapshot)}"
        )


async def get_llm_client() -> LLMClient:
    return LLMClient()
