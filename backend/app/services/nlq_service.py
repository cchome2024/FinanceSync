from __future__ import annotations

from datetime import UTC, datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.financial import NlqQuery
from app.schemas.nlq import NlqResponse


class NLQService:
    """Stub implementation for natural language query handling."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def run_query(self, question: str) -> NlqResponse:
        """Persist query intent and return a placeholder response."""

        answer = (
            "智能分析功能正在建设中，我们已记录你的问题。"
            "后续可在“查询分析”对话中查看更新。"
        )
        highlights: List[str] = [
            f"问题：{question}",
            "提示：当前版本返回占位回答，用于验证前后端流程。",
        ]

        record = NlqQuery(
            question=question,
            generated_sql=None,
            execution_result_ref=None,
            chart_type=None,
            chart_config=None,
            responded_at=datetime.now(UTC),
            latency_ms=None,
        )
        self._session.add(record)
        self._session.commit()

        return NlqResponse(queryId=record.id, answer=answer, highlights=highlights)



