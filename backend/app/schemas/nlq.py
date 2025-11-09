from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NlqRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class NlqResponse(BaseModel):
    query_id: str = Field(alias="queryId")
    answer: str
    highlights: List[str] = Field(default_factory=list)
    chart: Optional[Dict[str, Any]] = None



