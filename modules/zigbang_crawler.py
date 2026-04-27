"""
modules/zigbang_crawler.py
직방 아파트 현재 매물 크롤링
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

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Origin":          "https://www.zigbang.com",
    "Referer":         "https://www.zigbang.com/",
}

# 직방 지역코드 (시군구 코드)
ZIGBANG_REGION_CODES = {
    # 대전
    "유성구": "30200",
    "서구":   "30170",
    "중구":   "30110",
    "동구":   "30140",
    "대덕구": "30230",
    # 세종
    "세종시": "36110",
    # 서울
    "마포구":   "11440",
    "성동구":   "11200",
    "동작구":   "11590",
    "영등포구": "11560",
    "강서구":   "11500",
}

# 거래유형
TRADE_TYPE = {
    "jeonse": "전세",
    "sale":   "매매",
}


def _random_delay():
    time.sleep(random.uniform(1.0, 2.5))


def _parse_price(price_val) -> int:
    """직방 가격 → 원 단위 변환 (만원 단위로 옴)"""
    try:
        return int(str(price_val).replace(",", "")) * 10000
    except:
        return 0


def _get_geohash(district: str) -> list[str]:
    """
    직방은 geohash 기반 위치 검색
    지역명 → 좌표 → geohash 변환
    """
    # 지역별 중심 좌표 (미리 계산)
    COORDS = {
        "유성구": (36.3624, 127.3560),
        "서구":   (36.3554, 127.3830),
        "중구":   (36.3251, 127.4208),
        "동구":   (36.3121, 127.4545),
        "대덕구": (36.3464, 127.4154),
        "세종시": (36.4801, 127.2890),
        "마포구":   (37.5663, 126.9010),
        "성동구":   (37.5633, 127.0369),
        "동작구":   (37.5124, 126.9393),
        "영등포구": (37.5263, 126.8961),
        "강서구":   (37.5509, 126.8496),
    }

    coord = COORDS.get(district)
    if not coord:
        return []

    lat, lng = coord
    return _coord_to_geohashes(lat, lng)


def _coord_to_geohashes(lat: float, lng: float, precision: int = 5) -> list[str]:
    """좌표 → geohash 변환 (중심 + 주변 8개)"""
    try:
        import pygeohash as pgh
        center = pgh.encode(lat, lng, precision)
        neighbors = pgh.neighbors(center)
        return [center] + list(neighbors.values())
    except ImportError:
        # pygeohash 없으면 직접 계산
        return _manual_geohash(lat, lng, precision)


def _manual_geohash(lat: float, lng: float, precision: int = 5) -> list[str]:
    """pygeohash 없을 때 수동 geohash 계산"""
    BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

    def encode(lat, lng, precision):
        lat_range = [-90.0, 90.0]
        lng_range = [-180.0, 180.0]
        geohash = []
        bits = [16, 8, 4, 2, 1]
        bit = 0
        ch = 0
        even = True

        while len(geohash) < precision:
            if even:
                mid = (lng_range[0] + lng_range[1]) / 2
                if lng > mid:
                    ch |= bits[bit]
                    lng_range[0] = mid
                else:
                    lng_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat > mid:
                    ch |= bits[bit]
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid

            even = not even
            if bit < 4:
                bit += 1
            else:
                geohash.append(BASE32[ch])
                bit = 0
                ch = 0

        return ''.join(geohash)

    center = encode(lat, lng, precision)
    # 중심만 반환 (이웃 계산 생략)
    return [center]


def fetch_zigbang_items(district: str, trade_type: str) -> list[dict]:
    """
    직방 아파트 매물 수집
    district: '유성구' 등
    trade_type: 'jeonse' or 'sale'
    """
    geohashes = _get_geohash(district)
    if not geohashes:
        print(f"[직방] {district} geohash 변환 실패")
        return []

    results = []

    for gh in geohashes[:3]:  # 중심 + 주변 2개만
        # 1단계: geohash로 아이템 ID 목록 조회
        item_ids = _fetch_item_ids(gh, trade_type)
        if not item_ids:
            continue

        # 2단계: 아이템 상세 정보 조회
        items = _fetch_item_details(item_ids, district, trade_type)
        results.extend(items)
        _random_delay()

    # 중복 제거
    seen = set()
    unique = []
    for item in results:
        key = item.get("listing_id", "")
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"[직방] {district} {trade_type}: {len(unique)}건")
    return unique


def _fetch_item_ids(geohash: str, trade_type: str) -> list[str]:
    """geohash로 매물 ID 목록 조회"""
    trade_kr = TRADE_TYPE.get(trade_type, "전세")
    url = "https://apis.zigbang.com/v2/items"
    params = {
        "domain":     "zigbang",
        "geohash":    geohash,
        "needHasAds": True,
        "serviceType": "아파트",
        "tradetype":  trade_kr,
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"[직방 ID] 상태코드: {resp.status_code}")
            return []
        data = resp.json()
        items = data.get("items", [])
        return [str(item.get("itemId", "")) for item in items if item.get("itemId")]
    except Exception as e:
        print(f"[직방 ID] 오류: {e}")
        return []


def _fetch_item_details(item_ids: list[str], district: str, trade_type: str) -> list[dict]:
    """매물 ID로 상세 정보 조회"""
    if not item_ids:
        return []

    # 직방은 최대 900개씩 처리
    chunk_size = 100
    results = []
    cfg = CFG["jeonse"] if trade_type == "jeonse" else CFG["sale"]

    for i in range(0, len(item_ids), chunk_size):
        chunk = item_ids[i:i+chunk_size]
        url = "https://apis.zigbang.com/v2/items/list"
        payload = {
            "domain":  "zigbang",
            "itemIds": chunk,
        }
        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
            if resp.status_code != 200:
                continue
            data  = resp.json()
            items = data.get("items", [])

            for item in items:
                parsed = _parse_zigbang_item(item, district, trade_type)
                if parsed and _passes_filter(parsed, cfg):
                    results.append(parsed)

        except Exception as e:
            print(f"[직방 상세] 오류: {e}")
        _random_delay()

    return results


def _parse_zigbang_item(item: dict, district: str, trade_type: str) -> dict | None:
    """직방 매물 JSON → 정제된 dict"""
    try:
        item_id   = str(item.get("itemId", ""))
        name      = item.get("aptName") or item.get("buildingName") or ""
        area      = float(item.get("전용면적") or item.get("area") or 0)
        floor_val = item.get("floorInfo") or item.get("floor") or ""
        floor     = str(floor_val).split("/")[0].strip()

        # 가격
        if trade_type == "jeonse":
            price_raw = item.get("depositPrice") or item.get("deposit") or 0
        else:
            price_raw = item.get("price") or item.get("salePrice") or 0
        price = _parse_price(price_raw)

        # 건축연도
        built_year = int(item.get("builtIn") or item.get("buildingYear") or 0)
        age        = CURRENT_YEAR - built_year if built_year > 1990 else 99

        # 향
        direction = item.get("direction") or ""

        # 주소
        address = item.get("address") or item.get("roadAddress") or ""

        # 입주 가능일
        move_in = item.get("moveInDate") or "협의"

        # 설명
        desc = item.get("description") or ""

        return {
            "source":      "zigbang",
            "trade_type":  trade_type,
            "name":        name,
            "district":    district,
            "dong":        address,
            "price":       price if trade_type == "sale"   else 0,
            "deposit":     price if trade_type == "jeonse" else 0,
            "area":        area,
            "built_year":  built_year,
            "age":         age,
            "floor":       floor,
            "direction":   direction,
            "move_in":     move_in,
            "description": desc,
            "listing_id":  f"Z_{trade_type}_{district}_{item_id}",
            "url":         f"https://www.zigbang.com/home/apt/items/{item_id}",
            "is_priority": any(p in address or p in name
                               for p in CFG["priority_areas"]["sale"]),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        print(f"[직방 파싱] 오류: {e}")
        return None


def _passes_filter(item: dict, cfg: dict) -> bool:
    """조건 필터"""
    area  = item.get("area", 0)
    age   = item.get("age", 99)
    price = item.get("deposit", 0) or item.get("price", 0)

    # 면적
    if not (cfg.get("min_area", 56) <= area <= cfg.get("max_area", 87)):
        return False

    # 가격
    if price > cfg.get("max_price", 999999999):
        return False
    if price < 10_000_000:
        return False

    # 연식 (모르면 통과)
    if age < 99 and age > cfg.get("max_age_years", 10):
        return False

    return True


def collect_zigbang_all(trade_type: str = "both") -> dict:
    """
    전체 관심 지역 직방 매물 수집
    trade_type: 'jeonse', 'sale', 'both'
    """
    all_jeonse, all_sale = [], []

    for district in ZIGBANG_REGION_CODES.keys():
        is_seoul = district in ["마포구", "성동구", "동작구", "영등포구", "강서구"]

        if trade_type in ("jeonse", "both") and not is_seoul:
            j = fetch_zigbang_items(district, "jeonse")
            all_jeonse.extend(j)
            _random_delay()

        if trade_type in ("sale", "both"):
            s = fetch_zigbang_items(district, "sale")
            all_sale.extend(s)
            _random_delay()

    print(f"\n[직방 수집 완료] 전세 {len(all_jeonse)}건 / 매매 {len(all_sale)}건")
    return {"jeonse": all_jeonse, "sale": all_sale}


if __name__ == "__main__":
    print("[테스트] 유성구 전세 매물")
    result = fetch_zigbang_items("유성구", "jeonse")
    print(f"결과: {len(result)}건")
    for r in result[:3]:
        price = r.get("deposit", 0) // 10000
        print(f"  {r['name']} {r['area']}m² {price}만원 {r['age']}년차 {r['floor']}층 입주:{r['move_in']}")
