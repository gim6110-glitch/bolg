"""
modules/data_collector.py
국토부 실거래가 API + 한국부동산원 시세 API 수집
"""

import os
import time
import requests
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

MOLIT_KEY = os.getenv("MOLIT_API_KEY")
KREB_KEY  = os.getenv("KREB_API_KEY")

import json
with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

CURRENT_YEAR = datetime.now().year

# 구군코드 전체 (대전+세종+서울 관심지역)
ALL_DISTRICT_CODES = {}
for region in CFG["regions"].values():
    ALL_DISTRICT_CODES.update(region["districts"])


# ── 공통 유틸 ────────────────────────────────────────────────────────

def _parse_price(text: str) -> int:
    """'50,000' → 500000000 (만원 → 원)"""
    try:
        return int(text.replace(",", "").replace(" ", "")) * 10000
    except:
        return 0


def _safe_int(text: str) -> int:
    try:
        return int(str(text).strip())
    except:
        return 0


def _safe_float(text: str) -> float:
    try:
        return float(str(text).strip())
    except:
        return 0.0


def _get_year_months(months: int) -> list[str]:
    now = datetime.now()
    return [(now - timedelta(days=30 * i)).strftime("%Y%m") for i in range(months)]


# ── 국토부 아파트 전세 실거래가 ──────────────────────────────────────

def fetch_jeonse(district_code: str, year_month: str) -> list[dict]:
    """국토부 아파트 전월세 자료 조회"""
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent"
    params = {
        "serviceKey": MOLIT_KEY,
        "LAWD_CD":    district_code,
        "DEAL_YMD":   year_month,
        "numOfRows":  1000,
        "pageNo":     1,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            def g(tag):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            # 전용면적 파싱
            area = _safe_float(g("전용면적"))
            # 조건 범위 체크 (56~62m²)
            jeonse_cfg = CFG["jeonse"]
            if not (jeonse_cfg["min_area"] <= area <= jeonse_cfg["max_area"]):
                continue

            deposit = _parse_price(g("보증금액"))
            built_year = _safe_int(g("건축년도"))
            age = CURRENT_YEAR - built_year if built_year > 1900 else 99

            # 하드 필터
            if deposit > jeonse_cfg["max_price"]:      continue
            if age > jeonse_cfg["max_age_years"]:      continue
            if deposit < 30_000_000:                   continue  # 이상치

            items.append({
                "trade_type":   "jeonse",
                "name":         g("아파트"),
                "dong":         g("법정동"),
                "district_code": district_code,
                "deposit":      deposit,
                "area":         area,
                "built_year":   built_year,
                "age":          age,
                "floor":        g("층"),
                "year_month":   year_month,
                "listing_id":   f"J_{district_code}_{g('아파트')}_{g('층')}_{year_month}_{deposit}",
            })
        return items
    except Exception as e:
        print(f"[전세수집] {district_code} {year_month} 오류: {e}")
        return []


# ── 국토부 아파트 매매 실거래가 ──────────────────────────────────────

def fetch_sale(district_code: str, year_month: str) -> list[dict]:
    """국토부 아파트매매 실거래가 상세 자료 조회"""
    url = "http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
    params = {
        "serviceKey": MOLIT_KEY,
        "LAWD_CD":    district_code,
        "DEAL_YMD":   year_month,
        "numOfRows":  1000,
        "pageNo":     1,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            def g(tag):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            area = _safe_float(g("전용면적"))
            # 조건 범위 체크 (81~87m²)
            sale_cfg = CFG["sale"]
            if not (sale_cfg["min_area"] <= area <= sale_cfg["max_area"]):
                continue

            price = _parse_price(g("거래금액"))
            built_year = _safe_int(g("건축년도"))
            age = CURRENT_YEAR - built_year if built_year > 1900 else 99

            # 하드 필터
            if price > sale_cfg["max_price"]:          continue
            if age > sale_cfg["max_age_years"]:        continue
            if price < 100_000_000:                    continue  # 이상치

            # 1순위 여부
            dong = g("법정동")
            is_priority = any(p in dong or p in g("아파트")
                              for p in CFG["priority_areas"]["sale"])

            items.append({
                "trade_type":   "sale",
                "name":         g("아파트"),
                "dong":         dong,
                "district_code": district_code,
                "price":        price,
                "area":         area,
                "built_year":   built_year,
                "age":          age,
                "floor":        g("층"),
                "year_month":   year_month,
                "is_priority":  is_priority,
                "listing_id":   f"S_{district_code}_{g('아파트')}_{g('층')}_{year_month}_{price}",
            })
        return items
    except Exception as e:
        print(f"[매매수집] {district_code} {year_month} 오류: {e}")
        return []


# ── 한국부동산원 주간 시세 ───────────────────────────────────────────

def fetch_kreb_weekly_price(district_code: str, trade_type: str = "jeonse") -> dict:
    """
    한국부동산원 아파트 시세 조회
    trade_type: 'jeonse' or 'sale'
    """
    # 부동산통계 조회 서비스 엔드포인트
    url = "http://openapi.reb.or.kr/OpenAPI_ToolInstallPackage/service/rest/AptPriceInfoSvc/getRealEstatePriceIndex"
    params = {
        "serviceKey": KREB_KEY,
        "지역코드":    district_code,
        "매물종별구분": "01",  # 아파트
        "매매전세구분": "02" if trade_type == "jeonse" else "01",
        "numOfRows":   10,
        "pageNo":      1,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = list(root.iter("item"))
        if not items:
            return {}
        item = items[0]
        def g(tag):
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else ""
        return {
            "district_code": district_code,
            "trade_type":    trade_type,
            "price_index":   _safe_float(g("지수")),
            "change_rate":   _safe_float(g("변동률")),
            "base_date":     g("기준일"),
        }
    except Exception as e:
        print(f"[부동산원] {district_code} {trade_type} 오류: {e}")
        return {}


# ── 통합 수집 ────────────────────────────────────────────────────────

def collect_all(months: int = 3) -> dict:
    """
    전체 관심 지역 실거래 수집
    반환: {"jeonse": [...], "sale": [...]}
    """
    year_months = _get_year_months(months)
    all_jeonse, all_sale = [], []

    total = len(ALL_DISTRICT_CODES) * len(year_months)
    done = 0

    for district_name, code in ALL_DISTRICT_CODES.items():
        # 서울은 모니터링 전용 → 매매만 수집
        is_seoul = code.startswith("11")

        for ym in year_months:
            if not is_seoul:
                jeonse = fetch_jeonse(code, ym)
                for i in jeonse:
                    i["district"] = district_name
                all_jeonse.extend(jeonse)

            sale = fetch_sale(code, ym)
            for i in sale:
                i["district"] = district_name
            all_sale.extend(sale)

            done += 1
            time.sleep(0.2)  # API 레이트 리밋
            if done % 10 == 0:
                print(f"[수집] {done}/{total} 완료...")

    print(f"[수집 완료] 전세 {len(all_jeonse)}건 / 매매 {len(all_sale)}건")
    return {"jeonse": all_jeonse, "sale": all_sale}


def collect_watchlist_prices(watchlist: list) -> list:
    """관심 단지 가격 추이 수집"""
    results = []
    year_months = _get_year_months(6)  # 6개월

    for watch in watchlist:
        name = watch["complex_name"]
        for code in ALL_DISTRICT_CODES.values():
            for ym in year_months:
                sale = fetch_sale(code, ym)
                matched = [s for s in sale if name in s.get("name", "")]
                results.extend(matched)
                time.sleep(0.1)

    return results


if __name__ == "__main__":
    print("[테스트] 대전 유성구 2개월 전세 수집")
    jeonse = fetch_jeonse("30200", datetime.now().strftime("%Y%m"))
    print(f"결과: {len(jeonse)}건")
    for item in jeonse[:3]:
        print(f"  {item['name']} {item['area']}m² {item['deposit']//10000}만원 {item['age']}년차")
