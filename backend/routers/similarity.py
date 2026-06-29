from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from services import check_similarity, safe_area

router = APIRouter(prefix="/api", tags=["similarity"])


class SentenceItem(BaseModel):
    식별자: str
    문장: str


class SimilarityRequest(BaseModel):
    영역: str
    문장목록: list[SentenceItem]
    ai사용: bool = False


@router.post("/similarity")
def similarity(request: SimilarityRequest) -> dict[str, Any]:
    safe_area(request.영역)
    return check_similarity([item.model_dump() for item in request.문장목록], use_ai=request.ai사용)
