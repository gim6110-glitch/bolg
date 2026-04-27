"""
modules/zigbang_playwright.py
Playwright로 직방 지도 탐색하면서 API 응답 가로채기
"""

import json, os, asyncio, time
from datetime import datetime

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

CURRENT_YEAR = datetime.now().year

REGION_MAP_URLS = {
    "유성구": "https://www.zigbang.com/home/apt?lat=36.3624&lng=127.3560&zoom=13",
    "서구":   "https://www.zigbang.com/home/apt?lat=36.3554&lng=127.3830&zoom=13",
    "중구":   "https://www.zigbang.com/home/apt?lat=36.3251&lng=127.4208&zoom=13",
    "동구":   "https://www.zigbang.com/home/apt?lat=36.3121&lng=127.4545&zoom=13",
    "대덕구": "https://www.zigbang.com/home/apt?lat=36.3464&lng=127.4154&zoom=13",
    "세종시": "https://www.zigbang.com/home/apt?lat=36.4801&lng=127.2890&zoom=13",
}

TRADE_PARAMS = {"jeonse": "tradeType=charter", "sale": "tradeType=sales"}
AREA_PARAMS  = {"jeonse": "minPynArea=15평대&maxPynArea=20평대",
                "sale":   "minPynArea=30평대&maxPynArea=35평대"}


def _parse_price(val) -> int:
    try:
        return int(str(val).replace(",", "")) * 10000
    except:
        return 0


def _passes_filter(item: dict, trade_type: str) -> bool:
    cfg   = CFG["jeonse"] if trade_type == "jeonse" else CFG["sale"]
    area  = item.get("area", 0)
    price = item.get("deposit", 0) or item.get("price", 0)
    age   = item.get("age", 99)
    if not (cfg["min_area"] <= area <= cfg["max_area"]): return False
    if price > cfg["max_price"] or price < 10_000_000:   return False
    if age < 99 and age > cfg["max_age_years"]:          return False
    return True


async def _crawl(district: str, trade_type: str) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Playwright] pip install playwright 필요")
        return []

    base = REGION_MAP_URLS.get(district)
    if not base:
        return []

    url           = f"{base}&{TRADE_PARAMS[trade_type]}&{AREA_PARAMS[trade_type]}"
    api_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-gpu", "--single-process"]
        )
        ctx  = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        page = await ctx.new_page()

        async def on_response(resp):
            try:
                if ("on-danjis" in resp.url or
                    "danji/marker" in resp.url or
                    "apartments" in resp.url) and resp.status == 200:
                    body = await resp.json()
                    api_responses.append(body)
                    print(f"  [가로채기] {resp.url[:70]}")
            except:
                pass

        page.on("response", on_response)

        try:
            print(f"[Playwright] {district} {trade_type} 로딩...")
            await page.goto(url, wait_until="load", timeout=60000)
            await asyncio.sleep(6)
            # 지도 약간 이동해서 추가 API 호출 유도
            await page.keyboard.press("ArrowRight")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[Playwright] {district} 오류: {e}")
        finally:
            await browser.close()

    # 응답 파싱
    results = []
    for data in api_responses:
        danjis = (data.get("danjis") or data.get("items") or
                  data.get("data") or [])
        if not danjis and isinstance(data, list):
            danjis = data
        for d in danjis:
            item = _parse(d, district, trade_type)
            if item and _passes_filter(item, trade_type):
                results.append(item)

    print(f"[Playwright] {district} {trade_type}: {len(results)}건")
    return results


def _parse(d: dict, district: str, trade_type: str) -> dict | None:
    try:
        name      = d.get("name") or d.get("danjiName") or d.get("aptName") or ""
        local3    = d.get("local3") or d.get("dong") or ""
        built_str = str(d.get("사용승인일") or d.get("builtDate") or "")
        built_year= int(built_str[:4]) if len(built_str) >= 4 else 0
        age       = CURRENT_YEAR - built_year if built_year > 1990 else 99
        danji_id  = d.get("id") or d.get("danjiId") or ""
        lat       = float(d.get("lat") or 0)
        lng_      = float(d.get("lng") or 0)

        if trade_type == "jeonse":
            price_raw = (d.get("minRentPrice") or d.get("representativeRentPrice") or
                         d.get("avgRentPrice") or d.get("depositMin") or 0)
        else:
            price_raw = (d.get("minSalesPrice") or d.get("representativeSalesPrice") or
                         d.get("avgSalesPrice") or d.get("priceMin") or 0)

        price = _parse_price(price_raw)
        area  = float(d.get("representativeArea") or d.get("area") or d.get("sizeM2") or 0)

        if not name or price <= 0:
            return None

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
            "parking":     float(d.get("가구당주차대수") or 0),
            "lat":         lat,
            "lng":         lng_,
            "listing_id":  f"ZP_{trade_type}_{danji_id}_{price}",
            "url":         f"https://www.zigbang.com/home/apt/danjis/{danji_id}",
            "is_priority": any(p in local3 or p in name
                               for p in CFG["priority_areas"]["sale"]),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except:
        return None


def fetch_zigbang_items(district: str, trade_type: str) -> list[dict]:
    return asyncio.run(_crawl(district, trade_type))


def collect_zigbang_all(trade_type: str = "both") -> dict:
    all_jeonse, all_sale = [], []
    for district in REGION_MAP_URLS:
        if trade_type in ("jeonse", "both"):
            all_jeonse.extend(fetch_zigbang_items(district, "jeonse"))
            time.sleep(3)
        if trade_type in ("sale", "both"):
            all_sale.extend(fetch_zigbang_items(district, "sale"))
            time.sleep(3)
    print(f"\n[수집 완료] 전세 {len(all_jeonse)}건 / 매매 {len(all_sale)}건")
    return {"jeonse": all_jeonse, "sale": all_sale}


if __name__ == "__main__":
    result = fetch_zigbang_items("유성구", "jeonse")
    print(f"결과: {len(result)}건")
    for r in result[:3]:
        p = r.get("deposit", 0) // 10000
        print(f"  {r['name']} {r['area']}m² {p}만원 {r['age']}년차")
