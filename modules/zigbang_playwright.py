"""
modules/zigbang_playwright.py
Playwright 브라우저 자동화로 직방 매물 수집
서버 IP 차단 우회 (실제 브라우저로 동작)
"""

import json
import os
import asyncio
import time
from datetime import datetime

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

CURRENT_YEAR = datetime.now().year

# 지역별 직방 검색 URL (평형 필터 포함)
# 전세: 15~20평 (56~62m²), 매매: 30~35평 (81~87m²)
REGION_URLS = {
    "jeonse": {
        "유성구": "https://www.zigbang.com/home/apt?cortarNo=3020000000&tradeType=charter&minArea=15&maxArea=20",
        "서구":   "https://www.zigbang.com/home/apt?cortarNo=3017000000&tradeType=charter&minArea=15&maxArea=20",
        "중구":   "https://www.zigbang.com/home/apt?cortarNo=3011000000&tradeType=charter&minArea=15&maxArea=20",
        "동구":   "https://www.zigbang.com/home/apt?cortarNo=3014000000&tradeType=charter&minArea=15&maxArea=20",
        "대덕구": "https://www.zigbang.com/home/apt?cortarNo=3023000000&tradeType=charter&minArea=15&maxArea=20",
        "세종시": "https://www.zigbang.com/home/apt?cortarNo=3611000000&tradeType=charter&minArea=15&maxArea=20",
    },
    "sale": {
        "유성구": "https://www.zigbang.com/home/apt?cortarNo=3020000000&tradeType=sales&minArea=30&maxArea=35",
        "서구":   "https://www.zigbang.com/home/apt?cortarNo=3017000000&tradeType=sales&minArea=30&maxArea=35",
        "중구":   "https://www.zigbang.com/home/apt?cortarNo=3011000000&tradeType=sales&minArea=30&maxArea=35",
        "동구":   "https://www.zigbang.com/home/apt?cortarNo=3014000000&tradeType=sales&minArea=30&maxArea=35",
        "대덕구": "https://www.zigbang.com/home/apt?cortarNo=3023000000&tradeType=sales&minArea=30&maxArea=35",
        "세종시": "https://www.zigbang.com/home/apt?cortarNo=3611000000&tradeType=sales&minArea=30&maxArea=35",
    }
}


def _parse_price(val) -> int:
    """만원 단위 → 원 단위"""
    try:
        return int(str(val).replace(",", "")) * 10000
    except:
        return 0


def _passes_filter(item: dict, trade_type: str) -> bool:
    """조건 필터"""
    cfg   = CFG["jeonse"] if trade_type == "jeonse" else CFG["sale"]
    area  = item.get("area", 0)
    price = item.get("deposit", 0) or item.get("price", 0)
    age   = item.get("age", 99)

    if not (cfg["min_area"] <= area <= cfg["max_area"]):
        return False
    if price > cfg["max_price"] or price < 10_000_000:
        return False
    if age < 99 and age > cfg["max_age_years"]:
        return False
    return True


async def _fetch_district(district: str, trade_type: str) -> list[dict]:
    """Playwright로 직방 단지 목록 + 매물 수집"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Playwright] 미설치. pip install playwright 후 playwright install chromium")
        return []

    url = REGION_URLS.get(trade_type, {}).get(district)
    if not url:
        return []

    results   = []
    api_data  = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",          # 라즈베리파이 메모리 절약
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        page = await context.new_page()

        # API 응답 가로채기
        async def handle_response(response):
            if "on-danjis" in response.url or "items" in response.url:
                try:
                    body = await response.json()
                    api_data.append({"url": response.url, "data": body})
                except:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # 동적 로딩 대기

            # 단지 목록에서 데이터 추출
            # 방법 1: 가로챈 API 데이터 파싱
            for api in api_data:
                data   = api["data"]
                danjis = (data.get("danjis") or data.get("items") or
                          data.get("data")   or [])
                if not danjis and isinstance(data, list):
                    danjis = data

                for danji in danjis:
                    item = _parse_danji(danji, district, trade_type)
                    if item and _passes_filter(item, trade_type):
                        results.append(item)

            # 방법 2: 페이지 DOM에서 직접 추출
            if not results:
                results = await _extract_from_dom(page, district, trade_type)

        except Exception as e:
            print(f"[Playwright] {district} {trade_type} 오류: {e}")
        finally:
            await browser.close()

    print(f"[Playwright] {district} {trade_type}: {len(results)}건")
    return results


async def _extract_from_dom(page, district: str, trade_type: str) -> list[dict]:
    """DOM에서 직접 매물 데이터 추출"""
    try:
        # Next.js __NEXT_DATA__ 추출
        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if not next_data:
            return []

        ssr    = (next_data.get("props", {})
                           .get("pageProps", {})
                           .get("SSRData", {}))
        danjis = ssr.get("danjis") or []

        results = []
        for danji in danjis:
            item = _parse_danji(danji, district, trade_type)
            if item and _passes_filter(item, trade_type):
                results.append(item)
        return results

    except Exception as e:
        print(f"[DOM 추출] {e}")
        return []


def _parse_danji(danji: dict, district: str, trade_type: str) -> dict | None:
    """단지 데이터 파싱"""
    try:
        name      = danji.get("name") or danji.get("danjiName") or ""
        local3    = danji.get("local3") or danji.get("dong") or ""
        built_str = str(danji.get("사용승인일") or danji.get("builtDate") or "")
        parking   = float(danji.get("가구당주차대수") or danji.get("parkingPerHousehold") or 0)
        lat       = float(danji.get("lat") or 0)
        lng       = float(danji.get("lng") or 0)
        danji_id  = danji.get("id") or danji.get("danjiId") or ""

        built_year = int(built_str[:4]) if len(built_str) >= 4 else 0
        age        = CURRENT_YEAR - built_year if built_year > 1990 else 99

        # 가격 (단지 대표 시세)
        if trade_type == "jeonse":
            price_raw = (danji.get("representativeRentPrice") or
                         danji.get("minRentPrice") or
                         danji.get("avgRentPrice") or 0)
        else:
            price_raw = (danji.get("representativeSalesPrice") or
                         danji.get("minSalesPrice") or
                         danji.get("avgSalesPrice") or 0)

        price = _parse_price(price_raw)
        area  = float(danji.get("representativeArea") or
                      danji.get("area") or 0)

        return {
            "source":      "zigbang",
            "trade_type":  trade_type,
            "name":        name,
            "district":    district,
            "dong":        local3,
            "price":       price if trade_type == "sale"   else 0,
            "deposit":     price if trade_type == "jeonse" else 0,
            "area":        area,
            "built_year":  built_year,
            "age":         age,
            "floor":       "",
            "parking":     parking,
            "lat":         lat,
            "lng":         lng,
            "listing_id":  f"ZP_{trade_type}_{danji_id}",
            "url":         f"https://www.zigbang.com/home/apt/danjis/{danji_id}",
            "is_priority": any(p in local3 or p in name
                               for p in CFG["priority_areas"]["sale"]),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        print(f"[파싱] {e}")
        return None


# ── 동기 래퍼 ────────────────────────────────────────────────────────

def fetch_zigbang_items(district: str, trade_type: str) -> list[dict]:
    """동기 인터페이스 (main.py에서 호출)"""
    return asyncio.run(_fetch_district(district, trade_type))


def collect_zigbang_all(trade_type: str = "both") -> dict:
    """전체 관심 지역 수집"""
    all_jeonse, all_sale = [], []

    districts = list(REGION_URLS.get("jeonse", {}).keys())

    for district in districts:
        if trade_type in ("jeonse", "both"):
            j = fetch_zigbang_items(district, "jeonse")
            all_jeonse.extend(j)
            time.sleep(2)

        if trade_type in ("sale", "both"):
            s = fetch_zigbang_items(district, "sale")
            all_sale.extend(s)
            time.sleep(2)

    print(f"\n[수집 완료] 전세 {len(all_jeonse)}건 / 매매 {len(all_sale)}건")
    return {"jeonse": all_jeonse, "sale": all_sale}


if __name__ == "__main__":
    print("[테스트] 유성구 전세")
    result = fetch_zigbang_items("유성구", "jeonse")
    print(f"결과: {len(result)}건")
    for r in result[:3]:
        price = r.get("deposit", 0) // 10000
        print(f"  {r['name']} {r['area']}m² {price}만원 {r['age']}년차")
