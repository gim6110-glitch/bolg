"""
modules/kakao_analyzer.py
카카오맵 API - 지하철 거리 + 산부인과 근접도 계산
"""

import os
import math
import requests
from dotenv import load_dotenv

load_dotenv()
KAKAO_KEY = os.getenv("KAKAO_API_KEY")

import json
with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

SUBWAY_STATIONS = CFG["daejeon_subway"]["line1_stations"]
KEY_HOSPITALS   = CFG["key_hospitals"]
HEADERS = {"Authorization": f"KakaoAK {KAKAO_KEY}"}


# ── 주소 → 좌표 변환 ────────────────────────────────────────────────

def addr_to_coord(address: str) -> tuple[float, float]:
    """주소 → (lat, lng) 반환. 실패 시 (None, None)"""
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    try:
        r = requests.get(url, headers=HEADERS,
                         params={"query": address}, timeout=5)
        docs = r.json().get("documents", [])
        if docs:
            return float(docs[0]["y"]), float(docs[0]["x"])
    except Exception as e:
        print(f"[카카오 지오코더] {address} 오류: {e}")
    return None, None


# ── 직선 거리 계산 (Haversine) ───────────────────────────────────────

def haversine_distance(lat1, lng1, lat2, lng2) -> float:
    """두 좌표 간 직선거리 (km)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlng/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def km_to_walk_min(km: float) -> int:
    """직선거리 → 도보 시간 추정 (분, 평균 4km/h 보정계수 1.3)"""
    return int(km * 1.3 / 4 * 60)


# ── 카카오 도보 경로 (정확한 도보 시간) ─────────────────────────────

def get_walk_time(origin_lat, origin_lng, dest_lat, dest_lng) -> int:
    """카카오 모빌리티 도보 경로 → 분 반환. 실패 시 직선거리 추정값"""
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    try:
        r = requests.get(url, headers=HEADERS, params={
            "origin":      f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "priority":    "RECOMMEND",
        }, timeout=5)
        routes = r.json().get("routes", [])
        if routes:
            duration = routes[0].get("summary", {}).get("duration", 0)
            return max(1, duration // 60)
    except Exception as e:
        print(f"[카카오 도보] 오류: {e}")
    # 폴백: 직선거리 추정
    dist = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    return km_to_walk_min(dist)


# ── 지하철 거리 분석 ────────────────────────────────────────────────

def nearest_subway(lat: float, lng: float) -> dict:
    """
    대전 1호선 기준 가장 가까운 역 + 도보 시간 반환
    반환: {"station": "반석역", "walk_min": 8, "dist_km": 0.5}
    """
    if lat is None or lng is None:
        return {"station": "알수없음", "walk_min": 99, "dist_km": 99}

    nearest = None
    min_dist = float("inf")

    for station in SUBWAY_STATIONS:
        dist = haversine_distance(lat, lng, station["lat"], station["lng"])
        if dist < min_dist:
            min_dist = dist
            nearest = station

    walk_min = get_walk_time(lat, lng, nearest["lat"], nearest["lng"])

    return {
        "station":  nearest["name"],
        "walk_min": walk_min,
        "dist_km":  round(min_dist, 2),
    }


# ── 산부인과 근접도 ──────────────────────────────────────────────────

def nearest_hospital(lat: float, lng: float) -> dict:
    """
    주요 대형 산부인과까지 거리 + 도보/차량 시간
    반환: {"name": "충남대병원", "dist_km": 2.1, "car_min": 8}
    """
    if lat is None or lng is None:
        return {"name": "알수없음", "dist_km": 99, "car_min": 99}

    nearest = None
    min_dist = float("inf")

    for hospital in KEY_HOSPITALS:
        dist = haversine_distance(lat, lng, hospital["lat"], hospital["lng"])
        if dist < min_dist:
            min_dist = dist
            nearest = hospital

    # 차량 시간 (산부인과는 도보보다 차량 기준이 현실적)
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    car_min = int(min_dist / 30 * 60)  # 기본 추정 (30km/h)
    try:
        r = requests.get(url, headers=HEADERS, params={
            "origin":      f"{lng},{lat}",
            "destination": f"{nearest['lng']},{nearest['lat']}",
            "priority":    "TIME",
        }, timeout=5)
        routes = r.json().get("routes", [])
        if routes:
            car_min = max(1, routes[0].get("summary", {}).get("duration", 0) // 60)
    except:
        pass

    return {
        "name":     nearest["name"],
        "dist_km":  round(min_dist, 2),
        "car_min":  car_min,
    }


# ── 주변 편의시설 개수 ───────────────────────────────────────────────

def count_nearby(lat: float, lng: float, keyword: str, radius: int = 1000) -> int:
    """카카오 키워드 검색으로 반경 내 시설 개수"""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    try:
        r = requests.get(url, headers=HEADERS, params={
            "query":  keyword,
            "x":      lng,
            "y":      lat,
            "radius": radius,
            "size":   15,
        }, timeout=5)
        return r.json().get("meta", {}).get("total_count", 0)
    except:
        return 0


# ── 아파트 단지 좌표 조회 ────────────────────────────────────────────

def get_complex_coord(complex_name: str, district: str) -> tuple[float, float]:
    """단지명 + 지역으로 좌표 조회"""
    address = f"{district} {complex_name} 아파트"
    lat, lng = addr_to_coord(address)
    if lat is None:
        # 단지명만으로 재시도
        lat, lng = addr_to_coord(complex_name)
    return lat, lng


# ── 통합 교통/인프라 분석 ────────────────────────────────────────────

def analyze_location(complex_name: str, district: str,
                     lat: float = None, lng: float = None) -> dict:
    """
    단지 위치 종합 분석
    좌표 없으면 카카오 지오코더로 자동 조회
    """
    if lat is None or lng is None:
        lat, lng = get_complex_coord(complex_name, district)

    if lat is None:
        return {
            "subway":   {"station": "알수없음", "walk_min": 99, "dist_km": 99},
            "hospital": {"name": "알수없음", "dist_km": 99, "car_min": 99},
            "mart_count":    0,
            "park_count":    0,
            "coord_found":   False,
        }

    subway   = nearest_subway(lat, lng)
    hospital = nearest_hospital(lat, lng)
    mart     = count_nearby(lat, lng, "대형마트", 1500)
    park     = count_nearby(lat, lng, "공원", 800)

    return {
        "subway":        subway,
        "hospital":      hospital,
        "mart_count":    mart,
        "park_count":    park,
        "lat":           lat,
        "lng":           lng,
        "coord_found":   True,
    }


if __name__ == "__main__":
    print("[테스트] 반석역 근처 가상 아파트")
    result = analyze_location("반석 힐스테이트", "유성구",
                               lat=36.385, lng=127.338)
    print(f"지하철: {result['subway']['station']} 도보 {result['subway']['walk_min']}분")
    print(f"병원: {result['hospital']['name']} 차량 {result['hospital']['car_min']}분")
    print(f"마트: {result['mart_count']}개 / 공원: {result['park_count']}개")
