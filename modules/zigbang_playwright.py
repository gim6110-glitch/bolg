"""
modules/zigbang_playwright.py
Playwright로 직방 API 응답 가로채기
filtered/unfiltered 구조 파싱
"""

import json, os, asyncio, time
from datetime import datetime

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'conditions.json')) as f:
    CFG = json.load(f)

CURRENT_YEAR = datetime.now().year

# 대전/세종만 (서울 제외)
REGION_COORDS = {
    "유성구": (36.3624, 127.3560),
    "서구":   (36.3554, 127.3830),
    "중구":   (36.3251, 127.4208),
    "동구":   (36.3121, 127.4545),
    "대덕구": (36.3464, 127.4154),
    "세종시": (36.4801, 127.2890),
}

TRADE_PARAMS = {"jeonse": "tradeType=charter", "sale": "tradeType=sales"}


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
    if price > cfg["max_price"] or price < 10_000_000: return False
    if age < 99 and age > cfg["max_age_years"]:        return False
    return True


def _in_region(danji: dict, district: str) -> bool:
    """단지가 해당 지역에 속하는지 확인"""
    gugun = danji.get("gugun", "")
    sido  = danji.get("sido", "")
    dong  = danji.get("dong", "")

    if district == "세종시":
        return "세종" in sido or "세종" in gugun
    return district in gugun


def _parse(d: dict, district: str, trade_type: str) -> dict | None:
    try:
        name      = d.get("name") or ""
        local3    = d.get("dong") or ""
        built_str = str(d.get("사용승인일") or "")
        built_year= int(built_str[:4]) if len(built_str) >= 4 else 0
        age       = CURRENT_YEAR - built_year if built_year > 1990 else 99
        danji_id  = d.get("id") or ""
        lat       = float(d.get("lat") or 0)
        lng_      = float(d.get("lng") or 0)

        # 가격 구조: price.charter.min / price.sales.min
        price_data = d.get("price", {})
        if trade_type == "jeonse":
            charter = price_data.get("charter") or price_data.get("rent") or {}
            price_raw = charter.get("min") or charter.get("avg") or 0
        else:
            sales = price_data.get("sales") or {}
            price_raw = sales.get("min") or sales.get("avg") or 0

        price = _parse_price(price_raw)

        # 면적 (대표 평형 — 30평대 기준)
        area = float(d.get("representativeArea") or d.get("area") or 0)

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
            "lat":         lat,
            "lng":         lng_,
            "listing_id":  f"ZP_{trade_type}_{danji_id}_{price}",
            "url":         f"https://www.zigbang.com/home/apt/danjis/{danji_id}",
            "is_priority": any(p in local3 or p in name
                               for p in CFG["priority_areas"]["sale"]),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        print(f"[파싱 오류] {e}")
        return None


async def _crawl(district: str, trade_type: str) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Playwright] pip install playwright 필요")
        return []

    lat, lng = REGION_COORDS[district]
    url = (f"https://www.zigbang.com/home/apt"
           f"?lat={lat}&lng={lng}&zoom=13"
           f"&{TRADE_PARAMS[trade_type]}")

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

        async def on_resp(resp):
            try:
                if "on-danjis" in resp.url and resp.status == 200:
                    body = await resp.json()
                    api_responses.append(body)
                    print(f"  [가로채기] 단지 {len(body.get('filtered',[]))}건")
            except:
                pass

        page.on("response", on_resp)

        try:
            print(f"[Playwright] {district} {trade_type} 로딩...")
            await page.goto(url, wait_until="load", timeout=60000)
            await asyncio.sleep(6)
            # 지도 이동으로 추가 API 호출 유도
            await page.keyboard.press("ArrowRight")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[오류] {e}")
        finally:
            await browser.close()

    # 파싱
    results = []
    for data in api_responses:
        # filtered 우선 (조건에 맞는 단지)
        danjis = data.get("filtered") or data.get("unfiltered") or []
        for d in danjis:
            # 해당 지역 단지만 필터
            if not _in_region(d, district):
                continue
            item = _parse(d, district, trade_type)
            if item and _passes_filter(item, trade_type):
                results.append(item)

    print(f"[Playwright] {district} {trade_type}: {len(results)}건")
    return results


def fetch_zigbang_items(district: str, trade_type: str) -> list[dict]:
    return asyncio.run(_crawl(district, trade_type))


def collect_zigbang_all(trade_type: str = "both") -> dict:
    all_jeonse, all_sale = [], []
    for district in REGION_COORDS:
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
