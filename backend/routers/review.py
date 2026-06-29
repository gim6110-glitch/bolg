from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import review_record, safe_area

router = APIRouter(prefix="/api", tags=["review"])


class ReviewRequest(BaseModel):
    영역: str = Field(..., examples=["진로활동"])
    문구: str


@router.post("/review")
def review(request: ReviewRequest) -> dict[str, Any]:
    area = safe_area(request.영역)
    return review_record(area, request.문구)
