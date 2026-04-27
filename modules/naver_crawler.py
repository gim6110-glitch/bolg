"""
modules/naver_crawler.py
네이버 부동산 현재 매물 크롤링
전세 / 매매 실시간 매물 수집
"""

import time
import random
import requests
import json
import os
from datetime import datetime

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

CURRENT_YEAR = datetime.now().year

# 네이버 부동산 API 헤더 (브라우저 흉내)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Referer":    "https://new.land.naver.com/apartments",
    "Accept":     "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# 네이버 부동산 지역코드 (법정동코드 앞 5자리)
NAVER_REGION_CODES = {
    # 대전
    "유성구": "3020000000",
    "서구":   "3017000000",
    "중구":   "3011000000",
    "동구":   "3014000000",
    "대덕구": "3023000000",
    # 세종
    "세종시": "3611000000",
    # 서울
    "마포구":   "1144000000",
    "성동구":   "1120000000",
    "동작구":   "1159000000",
    "영등포구": "1156000000",
    "강서구":   "1150000000",
}

# 거래유형 코드
TRADE_TYPE = {
    "jeonse": "B2",   # 전세
    "sale":   "A1",   # 매매
}


def _parse_price(price_str: str) -> int:
    """
    '2억', '2억5천', '5억3,000' 등 → 원 단위 변환
    """
    if not price_str:
        return 0
    try:
        price_str = str(price_str).replace(",", "").replace(" ", "")
        result = 0
        if "억" in price_str:
            parts = price_str.split("억")
            result += int(parts[0]) * 100000000
            if parts[1]:
                remain = parts[1].replace("천", "000").replace("만", "0000")
                if remain.isdigit():
                    result += int(remain) * (10000 if len(remain) <= 4 else 1)
        elif "천" in price_str:
            result = int(price_str.replace("천", "")) * 1000 * 10000
        elif "만" in price_str:
            result = int(price_str.replace("만", "")) * 10000
        else:
            result = int(price_str) * 10000
        return result
    except:
        return 0


def _random_delay():
    time.sleep(random.uniform(2.0, 4.0))


def fetch_naver_listings(district: str, trade_type: str) -> list[dict]:
    """
    네이버 부동산 현재 매물 수집
    district: '유성구', '세종시' 등
    trade_type: 'jeonse' or 'sale'
    """
    cortar_no = NAVER_REGION_CODES.get(district)
    if not cortar_no:
        print(f"[네이버] {district} 지역코드 없음")
        return []

    trade_code = TRADE_TYPE.get(trade_type, "B2")
    cfg        = CFG["jeonse"] if trade_type == "jeonse" else CFG["sale"]
    results    = []

    # 페이지 순회 (최대 5페이지)
    for page in range(1, 6):
        url = "https://new.land.naver.com/api/articles"
        params = {
            "cortarNo":      cortar_no,
            "order":         "rank",
            "realEstateType": "APT",
            "tradeType":     trade_code,
            "page":          page,
            "pageSize":      20,
        }
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=10)

            if resp.status_code == 401:
                # 인증 필요 시 다른 엔드포인트 시도
                results.extend(_fetch_fallback(district, trade_type, page))
                break

            if resp.status_code != 200:
                print(f"[네이버] {district} {trade_type} 상태코드: {resp.status_code}")
                break

            data     = resp.json()
            articles = data.get("articleList", [])

            if not articles:
                break

            for a in articles:
                item = _parse_article(a, district, trade_type)
                if item and _passes_filter(item, cfg):
                    results.append(item)

            # 마지막 페이지 체크
            if not data.get("isMoreData", False):
                break

            _random_delay()

        except Exception as e:
            print(f"[네이버] {district} {trade_type} p{page} 오류: {e}")
            break

    return results


def _parse_article(a: dict, district: str, trade_type: str) -> dict | None:
    """네이버 매물 JSON → 정제된 dict"""
    try:
        name      = a.get("articleName", "")
        area_str  = a.get("area2", a.get("area1", "0"))  # 전용면적 우선
        price_raw = a.get("dealOrWarrantPrc", "0")
        floor_str = a.get("floorInfo", "")
        desc      = a.get("articleFeatureDesc", "")
        article_no = a.get("articleNo", "")
        direction = a.get("direction", "")  # 향

        # 면적 파싱
        try:
            area = float(str(area_str).replace("㎡", "").strip())
        except:
            area = 0.0

        # 가격 파싱
        price = _parse_price(price_raw)

        # 층 파싱 (예: "7/15" → "7")
        floor = floor_str.split("/")[0].strip() if "/" in floor_str else floor_str.strip()

        # 건축연도 파싱 (매물 설명에서 추출)
        built_year = _extract_built_year(a)
        age        = CURRENT_YEAR - built_year if built_year > 1900 else 99

        # 주차 정보
        parking = a.get("parkingCount", 0)

        # 입주 가능일 텍스트
        move_in = _extract_move_in(desc, a)

        return {
            "source":      "naver",
            "trade_type":  trade_type,
            "name":        name,
            "district":    district,
            "dong":        a.get("cortarAddress", ""),
            "price":       price if trade_type == "sale" else 0,
            "deposit":     price if trade_type == "jeonse" else 0,
            "area":        area,
            "built_year":  built_year,
            "age":         age,
            "floor":       floor,
            "direction":   direction,
            "parking":     parking,
            "move_in":     move_in,
            "description": desc,
            "article_no":  article_no,
            "url":         f"https://new.land.naver.com/articles/{article_no}",
            "listing_id":  f"N_{trade_type}_{district}_{article_no}",
            "is_priority": any(p in a.get("cortarAddress","") or p in name
                               for p in CFG["priority_areas"]["sale"]),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        print(f"[네이버 파싱] 오류: {e}")
        return None


def _extract_built_year(a: dict) -> int:
    """건축연도 추출 (매물 정보에서)"""
    # 네이버는 buildingName 또는 realtorName 등에 연도 포함
    candidates = [
        a.get("buildingName", ""),
        a.get("articleFeatureDesc", ""),
        a.get("tagList", ""),
    ]
    import re
    for text in candidates:
        if not text:
            continue
        # 20xx년 또는 19xx년 패턴 찾기
        matches = re.findall(r'(19|20)\d{2}', str(text))
        for m in matches:
            year = int(m)
            if 1990 <= year <= CURRENT_YEAR:
                return year
    return 0


def _extract_move_in(desc: str, a: dict) -> str:
    """입주 가능 시점 텍스트 추출"""
    keywords = ["즉시입주", "즉시 입주", "입주가능", "협의"]
    for kw in keywords:
        if kw in desc:
            return kw

    import re
    # "X월 입주", "X월말 입주" 패턴
    match = re.search(r'(\d{1,2})월\s*(말|초|중)?\s*입주', desc)
    if match:
        return match.group(0)

    return "협의"


def _passes_filter(item: dict, cfg: dict) -> bool:
    """조건 필터 (면적, 가격, 연식)"""
    area  = item.get("area", 0)
    age   = item.get("age", 99)
    price = item.get("deposit", 0) or item.get("price", 0)

    # 면적 체크
    min_area = cfg.get("min_area", 56)
    max_area = cfg.get("max_area", 87)
    if not (min_area <= area <= max_area):
        return False

    # 가격 체크
    if price > cfg.get("max_price", 999999999):
        return False
    if price < 10_000_000:  # 이상치
        return False

    # 연식 체크 (건축연도 모르면 통과)
    if age < 99 and age > cfg.get("max_age_years", 10):
        return False

    return True


def _fetch_fallback(district: str, trade_type: str, page: int) -> list[dict]:
    """
    네이버 차단 시 폴백
    직방 API 시도
    """
    print(f"[폴백] {district} {trade_type} 직방 시도")
    results = []
    try:
        # 직방 아파트 매물 API
        url = "https://apis.zigbang.com/v2/items/list"
        # 직방은 geohash 기반이라 좌표 필요 — 추후 구현
        pass
    except:
        pass
    return results


def collect_naver_all(trade_type: str = "both") -> dict:
    """
    전체 관심 지역 네이버 매물 수집
    trade_type: 'jeonse', 'sale', 'both'
    """
    all_jeonse, all_sale = [], []

    for district in NAVER_REGION_CODES.keys():
        is_seoul = district in ["마포구", "성동구", "동작구", "영등포구", "강서구"]

        if trade_type in ("jeonse", "both") and not is_seoul:
            j = fetch_naver_listings(district, "jeonse")
            all_jeonse.extend(j)
            print(f"[네이버 전세] {district}: {len(j)}건")
            _random_delay()

        if trade_type in ("sale", "both"):
            s = fetch_naver_listings(district, "sale")
            all_sale.extend(s)
            print(f"[네이버 매매] {district}: {len(s)}건")
            _random_delay()

    print(f"\n[네이버 수집 완료] 전세 {len(all_jeonse)}건 / 매매 {len(all_sale)}건")
    return {"jeonse": all_jeonse, "sale": all_sale}


if __name__ == "__main__":
    print("[테스트] 유성구 전세 매물")
    result = fetch_naver_listings("유성구", "jeonse")
    print(f"결과: {len(result)}건")
    for r in result[:3]:
        print(f"  {r['name']} {r['area']}m² {r['deposit']//10000}만원 {r['age']}년차 {r['floor']}층 입주:{r['move_in']}")
