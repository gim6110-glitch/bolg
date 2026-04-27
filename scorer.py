"""
modules/scorer.py
지역별/거래유형별 분리된 점수화 엔진
전세: 지하철 최우선
매매: 출퇴근 + 시세차익 + 학군
"""

import json
import os
from modules.kakao_analyzer import analyze_location, count_nearby

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)


# ══════════════════════════════════════════════════════════════════════
# 전세 점수화 (총 100점)
# 지하철 25점 / 가격 25점 / 대전역접근 15점 / 산부인과 15점 / 신축 20점
# ══════════════════════════════════════════════════════════════════════

def score_jeonse(item: dict, location: dict = None) -> dict:
    scores = {}

    # 1. 지하철 도보 거리 (25점) ─ 가장 중요
    if location and location.get("coord_found"):
        walk_min = location["subway"]["walk_min"]
        if walk_min <= 5:        scores["subway"] = 25
        elif walk_min <= 10:     scores["subway"] = 20
        elif walk_min <= 15:     scores["subway"] = 10
        elif walk_min <= 20:     scores["subway"] = 3
        else:                    scores["subway"] = 0   # 20분 초과 사실상 탈락
    else:
        scores["subway"] = 12  # 좌표 없을 때 중간값

    # 2. 가격 저렴도 (25점)
    deposit = item.get("deposit", 0)
    max_p   = CFG["jeonse"]["max_price"]
    ratio   = deposit / max_p
    if ratio <= 0.70:       scores["price"] = 25
    elif ratio <= 0.80:     scores["price"] = 20
    elif ratio <= 0.90:     scores["price"] = 12
    else:                   scores["price"] = 5

    # 3. 대전역 접근성 (15점) ─ 지하철 역명으로 판단
    if location and location.get("coord_found"):
        station = location["subway"].get("station", "")
        # 대전역까지 1~3 정거장 이내 역들
        near_daejeon_station = ["대전역", "중앙로역", "대동역", "신흥역", "판암역",
                                 "중구청역", "서대전네거리역"]
        if station in near_daejeon_station:
            scores["daejeon_access"] = 15
        elif location["subway"]["walk_min"] <= 10:
            scores["daejeon_access"] = 8   # 어느 역이든 가까우면 부분점수
        else:
            scores["daejeon_access"] = 3
    else:
        scores["daejeon_access"] = 7

    # 4. 산부인과 접근성 (15점)
    if location and location.get("coord_found"):
        car_min = location["hospital"]["car_min"]
        if car_min <= 10:       scores["hospital"] = 15
        elif car_min <= 20:     scores["hospital"] = 10
        elif car_min <= 30:     scores["hospital"] = 5
        else:                   scores["hospital"] = 0
    else:
        scores["hospital"] = 7

    # 5. 신축 / 연식 (20점)
    age = item.get("age", 10)
    if age <= 2:     scores["age"] = 20
    elif age <= 4:   scores["age"] = 17
    elif age <= 6:   scores["age"] = 13
    elif age <= 8:   scores["age"] = 9
    elif age <= 10:  scores["age"] = 5
    else:            scores["age"] = 0

    total = sum(scores.values())
    return {
        "total":  round(total, 1),
        "detail": scores,
    }


# ══════════════════════════════════════════════════════════════════════
# 매매 점수화 (총 100점)
# 출퇴근 25점 / 가격 20점 / 시세차익 20점 / 학군 20점 / 인프라 15점
# ══════════════════════════════════════════════════════════════════════

def score_sale(item: dict, location: dict = None) -> dict:
    scores = {}

    # 1. 출퇴근 편의 (25점)
    # 아내: 세종 정부청사 / 본인: 대전 직장 → 둘 다 차로 이동
    # 1순위 지역(반석/관저/세종 등)은 기본 점수 높게
    is_priority = item.get("is_priority", False)
    district    = item.get("district", "")
    dong        = item.get("dong", "")

    if "세종" in district:
        scores["commute"] = 25  # 아내 직장 최근접
    elif any(p in dong for p in ["반석", "관저", "노은", "지족", "도안"]):
        scores["commute"] = 22
    elif "유성" in district or "서구" in district:
        scores["commute"] = 15
    else:
        scores["commute"] = 8

    # 2. 가격 저렴도 (20점)
    price = item.get("price", 0)
    max_p = CFG["sale"]["max_price"]
    ratio = price / max_p
    if ratio <= 0.70:       scores["price"] = 20
    elif ratio <= 0.80:     scores["price"] = 15
    elif ratio <= 0.90:     scores["price"] = 9
    else:                   scores["price"] = 3

    # 3. 시세차익 가능성 (20점)
    # 신축 + 1순위 지역 + 세종 = 높음
    age = item.get("age", 10)
    capital_gain = 0
    if "세종" in district:       capital_gain += 10
    elif is_priority:            capital_gain += 7
    if age <= 3:                 capital_gain += 10
    elif age <= 5:               capital_gain += 7
    elif age <= 7:               capital_gain += 4
    scores["capital_gain"] = min(capital_gain, 20)

    # 4. 학군 (20점) ─ 카카오 주변 초등학교 개수로 근사
    if location and location.get("coord_found"):
        lat, lng = location["lat"], location["lng"]
        elem = count_nearby(lat, lng, "초등학교", 800)
        if elem >= 2:      scores["school"] = 20
        elif elem == 1:    scores["school"] = 13
        else:              scores["school"] = 5
    else:
        scores["school"] = 10

    # 5. 인프라 (15점)
    if location and location.get("coord_found"):
        mart = location.get("mart_count", 0)
        park = location.get("park_count", 0)
        infra = min(mart * 4, 8) + min(park * 2, 7)
        scores["infra"] = min(infra, 15)
    else:
        scores["infra"] = 7

    total = sum(scores.values())
    return {
        "total":  round(total, 1),
        "detail": scores,
    }


# ══════════════════════════════════════════════════════════════════════
# 전세사기 위험 분석
# ══════════════════════════════════════════════════════════════════════

def fraud_risk(jeonse_price: int, sale_price: int,
               official_price: int = 0) -> dict:
    """
    전세사기 위험도 종합 분석
    - 전세가율 (jeonse/sale)
    - HUG 보증보험 가능 여부 (jeonse <= official * 1.26)
    """
    result = {}

    # 전세가율
    if sale_price > 0:
        ratio = jeonse_price / sale_price * 100
        result["jeonse_ratio"] = round(ratio, 1)
        if ratio >= 90:    result["ratio_risk"] = "매우위험"
        elif ratio >= 80:  result["ratio_risk"] = "위험"
        elif ratio >= 70:  result["ratio_risk"] = "주의"
        else:              result["ratio_risk"] = "안전"
    else:
        result["jeonse_ratio"] = 0
        result["ratio_risk"] = "확인불가"

    # HUG 보증보험 가능 여부
    if official_price > 0:
        hug_limit = official_price * 1.26
        result["hug_possible"] = jeonse_price <= hug_limit
        result["hug_limit"]    = int(hug_limit)
    else:
        result["hug_possible"] = None  # 공시가격 없으면 판단 불가

    # 종합 위험도
    ratio_risk = result.get("ratio_risk", "확인불가")
    hug_ok     = result.get("hug_possible", True)

    if ratio_risk == "매우위험" or hug_ok is False:
        result["overall_risk"] = "위험"
    elif ratio_risk == "위험":
        result["overall_risk"] = "주의"
    elif ratio_risk == "주의":
        result["overall_risk"] = "확인필요"
    else:
        result["overall_risk"] = "안전"

    return result


# ══════════════════════════════════════════════════════════════════════
# 통합 파이프라인
# ══════════════════════════════════════════════════════════════════════

def run_scoring(items: list[dict], fetch_location: bool = True) -> list[dict]:
    """
    수집된 매물 전체에 점수화 적용
    fetch_location=True 면 카카오 API로 위치 분석 (API 호출 발생)
    """
    results = []
    for item in items:
        trade_type = item.get("trade_type")
        location   = None

        if fetch_location:
            location = analyze_location(
                item.get("name", ""),
                item.get("district", ""),
            )

        if trade_type == "jeonse":
            scored = score_jeonse(item, location)
        elif trade_type == "sale":
            scored = score_sale(item, location)
        else:
            continue

        item["score"]    = scored["total"]
        item["score_detail"] = scored["detail"]
        item["location"] = location
        results.append(item)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


if __name__ == "__main__":
    # 테스트
    test_jeonse = {
        "trade_type": "jeonse", "name": "반석 힐스테이트",
        "district": "유성구", "dong": "반석동",
        "deposit": 210_000_000, "area": 59, "age": 5,
    }
    test_sale = {
        "trade_type": "sale", "name": "세종 나성 푸르지오",
        "district": "세종시", "dong": "나성동",
        "price": 520_000_000, "area": 84, "age": 4,
        "is_priority": True,
    }
    print("[전세 점수]", score_jeonse(test_jeonse))
    print("[매매 점수]", score_sale(test_sale))
    print("[전세사기]",  fraud_risk(210_000_000, 350_000_000, 290_000_000))
