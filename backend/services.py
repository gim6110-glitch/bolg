from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from typing import Any

import anthropic
from fastapi import HTTPException

from prompts.builder import build_review_prompt, build_similarity_prompt, build_write_prompt, get_max_chars, normalize_area

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1500

PERSONAL_INFO_PATTERNS = [
    r"\d{6}[-]\d{7}",
    r"\d{2,3}[-]\d{3,4}[-]\d{4}",
    r"[가-힣]{2,4}\s*\d{1,2}번",
    r"\d{6,}",
]


def ensure_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")


def mask_personal_info(text: str) -> tuple[str, bool]:
    detected = False
    for pattern in PERSONAL_INFO_PATTERNS:
        if re.search(pattern, text):
            text = re.sub(pattern, "[개인정보 제거]", text)
            detected = True
    return text, detected


def mask_payload(value: Any) -> tuple[Any, bool]:
    detected = False
    if isinstance(value, str):
        return mask_personal_info(value)
    if isinstance(value, list):
        output = []
        for item in value:
            masked, item_detected = mask_payload(item)
            output.append(masked)
            detected = detected or item_detected
        return output, detected
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            masked, item_detected = mask_payload(item)
            output[key] = masked
            detected = detected or item_detected
        return output, detected
    return value, False


def call_claude(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        response_text = response.content[0].text
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail={"error": "AI 응답 파싱 실패", "raw": response_text}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": "AI 호출 실패", "message": str(exc)}) from exc


def generate_record(area: str, input_data: dict[str, Any]) -> dict[str, Any]:
    masked_input, detected = mask_payload(input_data)
    system_prompt, user_prompt = build_write_prompt(area, masked_input)
    result = call_claude(system_prompt, user_prompt)
    if detected:
        result.setdefault("제외한항목", []).append({"내용": "개인정보 패턴", "사유": "업로드 또는 입력 자료에서 개인정보를 마스킹함."})
    return result


def review_record(area: str, text: str) -> dict[str, Any]:
    masked_text, detected = mask_personal_info(text)
    system_prompt, user_prompt = build_review_prompt(area, masked_text)
    result = call_claude(system_prompt, user_prompt)
    if detected:
        result.setdefault("위반사항", []).append({
            "유형": "개인정보",
            "심각도": "높음",
            "원문위치": "개인정보 패턴",
            "수정제안": "삭제 또는 마스킹",
            "근거": "학생 이름·학번·주민등록번호·연락처 등 개인정보는 출력에 포함할 수 없음.",
        })
    return result


def find_local_similarities(sentences: list[dict[str, str]]) -> dict[str, Any]:
    pairs = []
    for i, left in enumerate(sentences):
        for right in sentences[i + 1:]:
            a = left.get("문장", "")
            b = right.get("문장", "")
            matcher = SequenceMatcher(None, a, b)
            match = matcher.find_longest_match(0, len(a), 0, len(b))
            if match.size >= 10:
                phrase = a[match.a:match.a + match.size]
                pairs.append({
                    "학생들": [left.get("식별자", str(i + 1)), right.get("식별자", "")],
                    "유사구절": phrase,
                    "심각도": "높음" if match.size >= 20 else "중간",
                })
    return {"유사쌍": pairs, "이상없음": not pairs}


def check_similarity(sentences: list[dict[str, str]], use_ai: bool = False) -> dict[str, Any]:
    if use_ai:
        system = "대한민국 학교생활기록부 문장 유사도 검사를 수행하는 보조자입니다. JSON만 출력합니다."
        return call_claude(system, build_similarity_prompt(sentences))
    return find_local_similarities(sentences)


def safe_area(area: str) -> str:
    try:
        return normalize_area(area)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def max_chars_for(area: str) -> int:
    try:
        return get_max_chars(area)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
