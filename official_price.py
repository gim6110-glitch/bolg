"""
modules/official_price.py
브이월드 공동주택가격속성조회 API
HUG 전세보증보험 가능 여부 체크용 공시가격 조회
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
VWORLD_KEY = os.getenv("VWORLD_API_KEY")

BASE_URL = "https://api.vworld.kr/req/data"


def get_official_price(complex_name: str, dong: str, district: str) -> int:
    """
    공동주택 공시가격 조회
    반환: 공시가격 (원). 조회 실패 시 0
    """
    params = {
        "service":    "data",
        "request":    "GetFeature",
        "data":       "LT_C_APTS_INDVLS",  # 공동주택가격 레이어
        "key":        VWORLD_KEY,
        "format":     "json",
        "size":       10,
        "page":       1,
        "geometry":   "false",
        "attribute":  "true",
        "cql":        f"apt_nm LIKE '%{complex_name}%'",
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        features = (data.get("response", {})
                        .get("result", {})
                        .get("featureCollection", {})
                        .get("features", []))

        if not features:
            return 0

        # 여러 동/호가 나올 수 있으므로 평균값 사용
        prices = []
        for f in features:
            props = f.get("properties", {})
            # 공시가격 필드명 (레이어에 따라 다를 수 있음)
            price_str = (props.get("pblntfpc") or
                         props.get("indvls_pc") or
                         props.get("publis_pric") or "0")
            try:
                price = int(str(price_str).replace(",", "")) * 10000
                if price > 0:
                    prices.append(price)
            except:
                continue

        return int(sum(prices) / len(prices)) if prices else 0

    except Exception as e:
        print(f"[공시가격] {complex_name} 조회 오류: {e}")
        return 0


def check_hug_eligibility(jeonse_price: int, official_price: int) -> dict:
    """
    HUG 전세보증보험 가입 가능 여부
    조건: 전세가 <= 공시가격 * 1.26
    """
    if official_price <= 0:
        return {
            "eligible": None,
            "reason":   "공시가격 조회 실패 — 직접 확인 필요",
            "limit":    0,
        }

    limit = int(official_price * 1.26)
    eligible = jeonse_price <= limit

    return {
        "eligible": eligible,
        "limit":    limit,
        "official": official_price,
        "reason":   (
            f"전세 {jeonse_price//10000}만원 / 한도 {limit//10000}만원 → 가입가능"
            if eligible else
            f"전세 {jeonse_price//10000}만원 > 한도 {limit//10000}만원 → 가입불가"
        ),
    }


if __name__ == "__main__":
    # 테스트
    official = get_official_price("힐스테이트", "반석동", "유성구")
    print(f"공시가격: {official//10000}만원")
    result = check_hug_eligibility(210_000_000, official or 280_000_000)
    print(f"HUG: {result}")
