from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.schemas.imports import CandidateRecord, RecordType
from app.services.llm_client import LLMClient, LLMClientError, LLMClientParseError


class AIParserService:
    """调用 LLM 将非结构化内容转换为结构化财务数据。"""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def parse_prompt(self, prompt: str, attachments: Iterable[bytes] | None = None) -> Tuple[List[CandidateRecord], Dict[str, Any]]:
        raw = await self._llm_client.parse_financial_payload(prompt, attachments or [])
        records = raw.get("records")
        if not isinstance(records, list):
            raise LLMClientError("LLM response missing `records` field")

        preview: List[CandidateRecord] = []
        for item in records:
            record_type = item.get("record_type") or item.get("recordType")
            payload = item.get("payload", {})
            try:
                preview.append(
                    CandidateRecord(
                        record_type=RecordType(record_type),
                        payload=payload,
                        confidence=item.get("confidence"),
                        warnings=item.get("warnings") or [],
                    )
                )
            except ValueError as exc:
                raise LLMClientError(f"Unsupported record type: {record_type}") from exc

        return preview, raw

