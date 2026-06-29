from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import generate_record, safe_area

router = APIRouter(prefix="/api", tags=["generate"])


class GenerateRequest(BaseModel):
    영역: str = Field(..., examples=["자율활동"])
    입력: dict[str, Any]


@router.post("/generate")
def generate(request: GenerateRequest) -> dict[str, Any]:
    area = safe_area(request.영역)
    return generate_record(area, request.입력)
