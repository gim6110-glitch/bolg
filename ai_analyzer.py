"""
modules/ai_analyzer.py
Claude AI 최종 분석
규칙 기반 점수 70점+ 매물만 AI에 전달 (하루 5회 한도)
"""

import os
from datetime import datetime
import anthropic
from dotenv import load_dotenv
from modules.db import can_call_ai, log_ai_call, get_today_ai_calls

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"
MAX_DAILY = 5  # 부동산 AI 하루 최대 호출


def _fmt_jeonse(item: dict) -> str:
    loc  = item.get("location", {})
    sub  = loc.get("subway", {}) if loc else {}
    hosp = loc.get("hospital", {}) if loc else {}
    return (
        f"단지: {item.get('name','')} ({item.get('district','')} {item.get('dong','')})\n"
        f"전세: {item.get('deposit',0)//10000}만원 / "
        f"{item.get('area',0):.0f}m² / {item.get('age',0)}년차 / {item.get('floor','')}층\n"
        f"지하철: {sub.get('station','?')} 도보 {sub.get('walk_min','?')}분\n"
        f"병원: {hosp.get('name','?')} 차량 {hosp.get('car_min','?')}분\n"
        f"규칙점수: {item.get('score',0)}점"
    )


def _fmt_sale(item: dict) -> str:
    loc  = item.get("location", {})
    return (
        f"단지: {item.get('name','')} ({item.get('district','')} {item.get('dong','')})\n"
        f"매매: {item.get('price',0)//10000}만원 / "
        f"{item.get('area',0):.0f}m² / {item.get('age',0)}년차 / {item.get('floor','')}층\n"
        f"1순위지역: {'예' if item.get('is_priority') else '아니오'}\n"
        f"규칙점수: {item.get('score',0)}점"
    )


def analyze_top_listings(jeonse_top: list, sale_top: list) -> str:
    """상위 매물 종합 AI 분석"""
    if not can_call_ai(MAX_DAILY):
        left = MAX_DAILY - get_today_ai_calls()
        return f"AI 호출 한도 초과 (오늘 {MAX_DAILY}회 완료)\n내일 다시 분석합니다."

    today = datetime.now().strftime("%Y년 %m월 %d일")
    jeonse_text = "\n\n".join([_fmt_jeonse(i) for i in jeonse_top[:3]]) or "해당 없음"
    sale_text   = "\n\n".join([_fmt_sale(i)   for i in sale_top[:3]])   or "해당 없음"

    prompt = f"""한국 부동산 전문 분석가로서 오늘({today}) 조건에 맞는 매물을 분석해주세요.

사용자 조건:
- 전세: 2억5천만원 이하 / 전용 56~62m2 / 10년 이내 / 대전 지하철 도보 10분 이내 / 2025년 9월 입주 목표
- 매매: 6억 이하 / 전용 81~87m2 / 10년 이내 / 반석동,관저동,세종 1순위
- 가족: 아내 세종 정부청사 근무, 본인 대전 근무, 출산 계획 있음 (산부인과 접근 중요)

전세 상위 매물:
{jeonse_text}

매매 상위 매물:
{sale_text}

분석 요청 (마크다운 사용 금지, 볼드 사용 금지, 텔레그램 일반 텍스트):
1. 전세 추천 1~2곳과 이유 (지하철 거리, 산부인과 접근, 전세사기 위험 포함)
2. 매매 추천 1~2곳과 이유 (출퇴근, 시세차익 가능성 포함)
3. 지금 시점 (2025년 4~5월) 전세 계약이 유리한지 기다리는 게 유리한지
4. 주의사항 1~2가지"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        log_ai_call("top_listings")
        left = MAX_DAILY - get_today_ai_calls()
        return f"{resp.content[0].text}\n\nAI 분석 완료 | 오늘 남은 호출: {left}회"
    except Exception as e:
        return f"AI 분석 오류: {e}"


def analyze_single(item: dict, fraud_info: dict = None, hug_info: dict = None) -> str:
    """단일 매물 상세 분석 (/detail 명령어용)"""
    if not can_call_ai(MAX_DAILY):
        return "AI 호출 한도 초과"

    trade_type = item.get("trade_type", "")
    if trade_type == "jeonse":
        price_str = f"전세 {item.get('deposit',0)//10000}만원"
    else:
        price_str = f"매매 {item.get('price',0)//10000}만원"

    fraud_text = ""
    if fraud_info:
        fraud_text = (
            f"\n전세가율: {fraud_info.get('jeonse_ratio',0)}% "
            f"({fraud_info.get('ratio_risk','')})"
        )
    hug_text = ""
    if hug_info:
        hug_text = f"\nHUG 보증보험: {'가입가능' if hug_info.get('eligible') else '가입불가'} — {hug_info.get('reason','')}"

    prompt = f"""한국 부동산 전문가로서 이 매물을 상세 평가해주세요.

매물 정보:
{_fmt_jeonse(item) if trade_type == 'jeonse' else _fmt_sale(item)}
{fraud_text}{hug_text}

분석 (마크다운 볼드 사용 금지, 텔레그램 일반 텍스트):
1. 가격 적정성 (시세 대비)
2. 실거주 장단점
3. 주의사항 (전세사기, 하자 체크포인트 등)
4. 종합 의견 (추천 / 보통 / 비추천)"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        log_ai_call("single_detail")
        return resp.content[0].text
    except Exception as e:
        return f"AI 분석 오류: {e}"


def weekly_report(region_stats: dict) -> str:
    """주간 지역별 시세 리포트"""
    if not can_call_ai(MAX_DAILY):
        return "AI 호출 한도 초과"

    import json as _json
    stats_text = _json.dumps(region_stats, ensure_ascii=False, indent=2)
    today = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""한국 부동산 전문가로서 이번 주({today}) 시세 동향 리포트를 작성해주세요.

지역별 통계:
{stats_text}

리포트 (마크다운 볼드 테이블 사용 금지, 텔레그램 일반 텍스트):
1. 대전/세종 이번 주 전세/매매 시세 요약
2. 서울 주요 지역 동향 (투자 관점)
3. 내 조건 기준 (전세 2.5억 이하 59m2, 매매 6억 이하 84m2) 이번 주 기회 지역
4. 다음 주 주목 포인트"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}]
        )
        log_ai_call("weekly_report")
        return resp.content[0].text
    except Exception as e:
        return f"주간 리포트 오류: {e}"


if __name__ == "__main__":
    print(f"오늘 AI 호출: {get_today_ai_calls()}/{MAX_DAILY}회")
