"""
main.py — 부동산 AI 텔레그램 봇
주식 에이전트와 동일한 send() 패턴 사용
"""

import os
import json
import asyncio
import logging
from datetime import datetime, time as dtime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

from modules.db import (
    init_db, is_already_alerted, mark_alerted,
    add_watchlist, remove_watchlist, get_watchlist,
    get_today_ai_calls, save_price_history, save_jeonse_ratio
)
from modules.data_collector import collect_all, collect_watchlist_prices
from modules.scorer import run_scoring, fraud_risk
from modules.kakao_analyzer import analyze_location
from modules.official_price import get_official_price, check_hug_eligibility
from modules.ai_analyzer import (
    analyze_top_listings, analyze_single, weekly_report
)

load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CFG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'conditions.json')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

bot_app: Application = None


# ── 설정 로드/저장 ───────────────────────────────────────────────────

def load_cfg() -> dict:
    with open(CFG_PATH) as f:
        return json.load(f)


def save_cfg(cfg: dict):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── 텔레그램 전송 (분할 지원) ────────────────────────────────────────

async def send(text: str, chat_id: str = None):
    cid  = chat_id or CHAT_ID
    MAX  = 4000
    if len(text) <= MAX:
        await bot_app.bot.send_message(chat_id=cid, text=text)
    else:
        for chunk in [text[i:i+MAX] for i in range(0, len(text), MAX)]:
            await bot_app.bot.send_message(chat_id=cid, text=chunk)
            await asyncio.sleep(0.3)


# ── 알림 시간 체크 ───────────────────────────────────────────────────

def is_quiet_time() -> bool:
    cfg  = load_cfg()
    hour = datetime.now().hour
    qs   = cfg["alert"]["quiet_start"]   # 22
    qe   = cfg["alert"]["quiet_end"]     # 7
    return hour >= qs or hour < qe


def should_alert_now(score: float) -> bool:
    cfg = load_cfg()
    if score >= cfg["alert"]["important_score"]:
        return True          # 85점+ 는 방해금지 무시하고 즉시
    return not is_quiet_time()


# ── 매물 포맷 ────────────────────────────────────────────────────────

def fmt_jeonse(item: dict, show_score: bool = True) -> str:
    loc  = item.get("location") or {}
    sub  = loc.get("subway", {})
    hosp = loc.get("hospital", {})
    lines = [
        f"[전세] {item.get('district','')} {item.get('name','')}",
        f"  {item.get('area',0):.0f}m² / {item.get('age',0)}년차 / {item.get('floor','')}층",
        f"  보증금: {item.get('deposit',0)//10000}만원",
    ]
    if sub.get("station"):
        lines.append(f"  지하철: {sub['station']} 도보 {sub.get('walk_min','?')}분")
    if hosp.get("name"):
        lines.append(f"  병원: {hosp['name']} 차량 {hosp.get('car_min','?')}분")
    if show_score:
        lines.append(f"  종합점수: {item.get('score',0)}점")
    return "\n".join(lines)


def fmt_sale(item: dict, show_score: bool = True) -> str:
    lines = [
        f"[매매] {item.get('district','')} {item.get('name','')}",
        f"  {item.get('area',0):.0f}m² / {item.get('age',0)}년차 / {item.get('floor','')}층",
        f"  매매가: {item.get('price',0)//10000}만원",
        f"  {'1순위 지역' if item.get('is_priority') else '2순위 지역'}",
    ]
    if show_score:
        lines.append(f"  종합점수: {item.get('score',0)}점")
    return "\n".join(lines)


# ── 명령어: /start ───────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "부동산 AI 모니터링 봇\n\n"
        "내 조건\n"
        "전세: 2.5억 이하 / 56~62m2 / 10년 이내 / 지하철 10분\n"
        "매매: 6억 이하 / 81~87m2 / 10년 이내\n\n"
        "명령어\n"
        "/scan — 전체 스캔 + AI 분석\n"
        "/jeonse — 전세 매물 검색\n"
        "/sale — 매매 매물 검색\n"
        "/fraud — 전세사기 위험 체크\n"
        "/compare 지역1 지역2 — 지역 비교\n"
        "/watch 단지명 — 관심 단지 등록\n"
        "/unwatch 단지명 — 관심 단지 해제\n"
        "/watchlist — 관심 단지 목록\n"
        "/set 항목 값 — 조건 변경\n"
        "/report — 주간 AI 리포트\n"
        "/status — 시스템 상태"
    )
    await send(msg)


# ── 명령어: /scan ────────────────────────────────────────────────────

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send("전체 매물 스캔 중... (2~3분 소요)")
    try:
        raw      = collect_all(months=2)
        jeonse_s = run_scoring(raw["jeonse"], fetch_location=True)
        sale_s   = run_scoring(raw["sale"],   fetch_location=True)

        cfg      = load_cfg()
        j_min    = cfg["jeonse"]["alert_min_score"]
        s_min_p  = cfg["sale"]["alert_min_score_priority"]
        s_min_o  = cfg["sale"]["alert_min_score_others"]

        now = datetime.now().strftime("%m/%d %H:%M")
        lines = [f"매물 스캔 결과 [{now}]\n"]
        lines.append(f"전세 통과: {len(jeonse_s)}건 / 매매 통과: {len(sale_s)}건\n")

        # 전세 상위
        j_top = [i for i in jeonse_s if i["score"] >= j_min][:5]
        lines.append(f"전세 점수 {j_min}점+: {len(j_top)}건")
        for item in j_top:
            lines.append(fmt_jeonse(item))
            lines.append("")

        # 매매 상위
        s_top = [i for i in sale_s
                 if (i["is_priority"] and i["score"] >= s_min_p) or
                    (not i["is_priority"] and i["score"] >= s_min_o)][:5]
        lines.append(f"매매 점수 기준 통과: {len(s_top)}건")
        for item in s_top:
            lines.append(fmt_sale(item))
            lines.append("")

        await send("\n".join(lines))

        # 히스토리 저장
        for item in jeonse_s[:20]:
            save_price_history(item.get("name",""), item.get("district",""),
                               "jeonse", item.get("deposit",0),
                               item.get("area",0), item.get("floor",""))
        for item in sale_s[:20]:
            save_price_history(item.get("name",""), item.get("district",""),
                               "sale", item.get("price",0),
                               item.get("area",0), item.get("floor",""))

        # AI 분석 (상위 있을 때만)
        if j_top or s_top:
            await send("AI 종합 분석 중...")
            ai_result = analyze_top_listings(j_top, s_top)
            await send(ai_result)

    except Exception as e:
        log.error(f"스캔 오류: {e}")
        await send(f"스캔 오류: {e}")


# ── 명령어: /jeonse ──────────────────────────────────────────────────

async def cmd_jeonse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send("전세 매물 검색 중...")
    try:
        raw    = collect_all(months=2)
        scored = run_scoring(raw["jeonse"], fetch_location=True)
        cfg    = load_cfg()
        j_min  = cfg["jeonse"]["alert_min_score"]
        top    = [i for i in scored if i["score"] >= j_min]

        if not top:
            await send(
                f"조건 맞는 전세 매물 없음\n"
                f"(2.5억 이하 / 56~62m2 / 10년 이내 / 지하철 10분 / {j_min}점+)"
            )
            return

        lines = [f"전세 매물 [{len(top)}건]\n"]
        for i, item in enumerate(top[:8], 1):
            lines.append(f"{i}. {fmt_jeonse(item)}\n")
        await send("\n".join(lines))

    except Exception as e:
        await send(f"오류: {e}")


# ── 명령어: /sale ────────────────────────────────────────────────────

async def cmd_sale(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send("매매 매물 검색 중...")
    try:
        raw    = collect_all(months=2)
        scored = run_scoring(raw["sale"], fetch_location=True)
        cfg    = load_cfg()
        top    = sorted(scored, key=lambda x: x["score"], reverse=True)[:8]

        if not top:
            await send("조건 맞는 매매 매물 없음 (6억 이하 / 81~87m2 / 10년 이내)")
            return

        lines = [f"매매 매물 [{len(top)}건]\n"]
        for i, item in enumerate(top, 1):
            lines.append(f"{i}. {fmt_sale(item)}\n")
        await send("\n".join(lines))

    except Exception as e:
        await send(f"오류: {e}")


# ── 명령어: /fraud ───────────────────────────────────────────────────

async def cmd_fraud(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send("전세사기 위험 분석 중...")
    try:
        raw        = collect_all(months=2)
        jeonse_map = {i.get("name",""): i for i in raw["jeonse"]}
        sale_map   = {i.get("name",""): i for i in raw["sale"]}

        danger_lines = ["전세사기 위험 분석\n"]
        danger_count = 0

        for name, j_item in list(jeonse_map.items())[:30]:
            s_item     = sale_map.get(name)
            sale_price = s_item.get("price", 0) if s_item else 0
            j_price    = j_item.get("deposit", 0)

            # 공시가격 조회
            official = get_official_price(
                name, j_item.get("dong",""), j_item.get("district","")
            )
            hug  = check_hug_eligibility(j_price, official)
            risk = fraud_risk(j_price, sale_price, official)

            # 위험/주의 이상만 출력
            if risk["overall_risk"] in ("위험", "주의") or hug["eligible"] is False:
                danger_count += 1
                danger_lines.append(
                    f"{risk['overall_risk']} | {j_item.get('district','')} {name}\n"
                    f"  전세 {j_price//10000}만원 / 매매 {sale_price//10000}만원\n"
                    f"  전세가율: {risk.get('jeonse_ratio',0)}%\n"
                    f"  HUG: {'가입가능' if hug['eligible'] else '가입불가 — 주의'}\n"
                )
                save_jeonse_ratio(name, j_item.get("district",""),
                                  j_price, sale_price,
                                  risk.get("jeonse_ratio", 0))

        if danger_count == 0:
            danger_lines.append("조회 범위에서 고위험 매물 없음")
        danger_lines.append("\n전세가율 80% 초과 or HUG 불가 시 계약 전 반드시 확인")
        await send("\n".join(danger_lines))

    except Exception as e:
        await send(f"오류: {e}")


# ── 명령어: /watch /unwatch /watchlist ──────────────────────────────

async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await send("사용법: /watch 단지명\n예) /watch 반석힐스테이트")
        return
    name = " ".join(ctx.args)
    ok = add_watchlist(name)
    if ok:
        await send(f"관심 단지 등록: {name}\n가격 변동 시 알림 드립니다.")
    else:
        await send(f"이미 등록된 단지입니다: {name}")


async def cmd_unwatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await send("사용법: /unwatch 단지명")
        return
    name = " ".join(ctx.args)
    ok = remove_watchlist(name)
    await send(f"{'해제 완료: ' + name if ok else '등록된 단지 없음: ' + name}")


async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wl = get_watchlist()
    if not wl:
        await send("등록된 관심 단지 없음\n/watch 단지명 으로 등록")
        return
    lines = ["관심 단지 목록\n"]
    for i, w in enumerate(wl, 1):
        lines.append(f"{i}. {w['complex_name']} ({w['district']}) — {w['added_at'][:10]}")
    await send("\n".join(lines))


# ── 명령어: /set ─────────────────────────────────────────────────────

async def cmd_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /set 항목 값
    예) /set jeonse_max 2억
        /set sale_max 7억
        /set jeonse_area 59
        /set subway_max 15
    """
    if len(ctx.args) < 2:
        await send(
            "사용법: /set 항목 값\n\n"
            "항목 목록\n"
            "jeonse_max — 전세 상한가 (예: 2억5천)\n"
            "sale_max — 매매 상한가 (예: 6억)\n"
            "jeonse_area — 전세 최소면적 m2\n"
            "sale_area — 매매 최소면적 m2\n"
            "jeonse_age — 전세 최대연식 년\n"
            "sale_age — 매매 최대연식 년\n"
            "subway_max — 지하철 최대 도보 분\n"
            "min_score — 알림 최소 점수"
        )
        return

    key = ctx.args[0]
    val_str = ctx.args[1].replace("억", "00000000").replace("천", "0000").replace(",", "")

    cfg = load_cfg()
    old_val = None

    try:
        val = int(val_str)

        mapping = {
            "jeonse_max":  ("jeonse", "max_price",       val * (1 if val > 100000 else 10000)),
            "sale_max":    ("sale",   "max_price",        val * (1 if val > 100000 else 10000)),
            "jeonse_area": ("jeonse", "min_area",         val),
            "sale_area":   ("sale",   "min_area",         val),
            "jeonse_age":  ("jeonse", "max_age_years",    val),
            "sale_age":    ("sale",   "max_age_years",    val),
            "subway_max":  ("jeonse", "subway_walk_max_min", val),
            "min_score":   ("jeonse", "alert_min_score",  val),
        }

        if key not in mapping:
            await send(f"알 수 없는 항목: {key}")
            return

        section, field, new_val = mapping[key]
        old_val = cfg[section][field]
        cfg[section][field] = new_val
        save_cfg(cfg)

        # 만원 단위 표시
        def fmt_val(v, f):
            if "price" in f and v >= 10000:
                return f"{v//10000}만원"
            return str(v)

        await send(
            f"설정 변경 완료\n"
            f"{key}: {fmt_val(old_val, field)} → {fmt_val(new_val, field)}\n"
            f"다음 스캔부터 적용됩니다"
        )
    except ValueError:
        await send(f"값 형식 오류: {ctx.args[1]}\n숫자로 입력해주세요 (예: /set jeonse_max 25000)")


# ── 명령어: /compare ─────────────────────────────────────────────────

async def cmd_compare(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await send("사용법: /compare 유성구 세종시")
        return
    r1, r2 = ctx.args[0], ctx.args[1]
    await send(f"{r1} vs {r2} 비교 분석 중...")
    try:
        raw    = collect_all(months=2)
        all_s  = run_scoring(raw["jeonse"] + raw["sale"], fetch_location=False)

        def stats(items, region):
            m = [i for i in items if i.get("district","") == region]
            if not m:
                return {"count": 0, "avg_price": 0, "avg_score": 0}
            prices = [i.get("deposit", i.get("price", 0)) for i in m]
            return {
                "count":     len(m),
                "avg_price": int(sum(prices)/len(prices)//10000),
                "avg_score": round(sum(i.get("score",0) for i in m)/len(m), 1),
            }

        s1j = stats([i for i in all_s if i["trade_type"]=="jeonse"], r1)
        s2j = stats([i for i in all_s if i["trade_type"]=="jeonse"], r2)
        s1s = stats([i for i in all_s if i["trade_type"]=="sale"],   r1)
        s2s = stats([i for i in all_s if i["trade_type"]=="sale"],   r2)

        msg = (
            f"{r1} vs {r2} 비교\n\n"
            f"전세\n"
            f"{r1}: {s1j['count']}건 / 평균 {s1j['avg_price']}만원 / 점수 {s1j['avg_score']}점\n"
            f"{r2}: {s2j['count']}건 / 평균 {s2j['avg_price']}만원 / 점수 {s2j['avg_score']}점\n\n"
            f"매매\n"
            f"{r1}: {s1s['count']}건 / 평균 {s1s['avg_price']}만원 / 점수 {s1s['avg_score']}점\n"
            f"{r2}: {s2s['count']}건 / 평균 {s2s['avg_price']}만원 / 점수 {s2s['avg_score']}점"
        )
        await send(msg)
    except Exception as e:
        await send(f"오류: {e}")


# ── 명령어: /report ──────────────────────────────────────────────────

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send("주간 리포트 생성 중... (AI 분석)")
    try:
        raw   = collect_all(months=1)
        stats = {}
        for item in raw["jeonse"] + raw["sale"]:
            d = item.get("district", "기타")
            t = item.get("trade_type", "")
            if d not in stats:
                stats[d] = {"jeonse": [], "sale": []}
            p = item.get("deposit" if t=="jeonse" else "price", 0)
            if p > 0:
                stats[d][t].append(p)

        region_summary = {
            r: {
                "jeonse_avg":   int(sum(v["jeonse"])/len(v["jeonse"])//10000) if v["jeonse"] else 0,
                "jeonse_count": len(v["jeonse"]),
                "sale_avg":     int(sum(v["sale"])/len(v["sale"])//10000)     if v["sale"]   else 0,
                "sale_count":   len(v["sale"]),
            }
            for r, v in stats.items()
        }
        report = weekly_report(region_summary)
        await send(report)
    except Exception as e:
        await send(f"오류: {e}")


# ── 명령어: /status ──────────────────────────────────────────────────

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg    = load_cfg()
    ai_cnt = get_today_ai_calls()
    wl_cnt = len(get_watchlist())
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (
        f"시스템 상태 [{now}]\n\n"
        f"AI 호출: {ai_cnt}/5회 (오늘)\n"
        f"관심 단지: {wl_cnt}개\n\n"
        f"현재 조건\n"
        f"전세: {cfg['jeonse']['max_price']//10000}만원 이하 / "
        f"{cfg['jeonse']['min_area']}~{cfg['jeonse']['max_area']}m2 / "
        f"{cfg['jeonse']['max_age_years']}년 이내 / "
        f"지하철 {cfg['jeonse']['subway_walk_max_min']}분\n"
        f"매매: {cfg['sale']['max_price']//10000}만원 이하 / "
        f"{cfg['sale']['min_area']}~{cfg['sale']['max_area']}m2 / "
        f"{cfg['sale']['max_age_years']}년 이내\n\n"
        f"스캔 지역\n"
        f"대전: 유성/서/중/동/대덕구\n"
        f"세종: 전지역\n"
        f"서울: 모니터링 전용\n\n"
        f"스케줄\n"
        f"매일 08:00 — 신규 매물 스캔\n"
        f"매주 목요일 — 한국부동산원 시세\n"
        f"매주 월요일 — AI 주간 리포트"
    )
    await send(msg)


# ── 스케줄: 매일 08:00 자동 스캔 ────────────────────────────────────

async def daily_scan(ctx: ContextTypes.DEFAULT_TYPE):
    log.info("일일 스캔 시작")
    try:
        raw     = collect_all(months=1)
        jeonse  = run_scoring(raw["jeonse"], fetch_location=True)
        sale    = run_scoring(raw["sale"],   fetch_location=True)
        cfg     = load_cfg()
        j_min   = cfg["jeonse"]["alert_min_score"]
        s_min_p = cfg["sale"]["alert_min_score_priority"]
        s_min_o = cfg["sale"]["alert_min_score_others"]

        now   = datetime.now().strftime("%m/%d")
        lines = [f"아침 스캔 [{now}]\n"]

        j_new = []
        for item in jeonse:
            if item["score"] < j_min:
                continue
            lid = item.get("listing_id", "")
            if not is_already_alerted(lid, "jeonse"):
                j_new.append(item)
                mark_alerted(lid, "jeonse", item.get("deposit",0), item["score"])

        s_new = []
        for item in sale:
            min_s = s_min_p if item.get("is_priority") else s_min_o
            if item["score"] < min_s:
                continue
            lid = item.get("listing_id", "")
            if not is_already_alerted(lid, "sale"):
                s_new.append(item)
                mark_alerted(lid, "sale", item.get("price",0), item["score"])

        if not j_new and not s_new:
            lines.append("신규 조건 통과 매물 없음")
            await bot_app.bot.send_message(chat_id=CHAT_ID, text="\n".join(lines))
            return

        lines.append(f"신규 전세: {len(j_new)}건 / 신규 매매: {len(s_new)}건\n")
        for item in j_new[:3]:
            lines.append(fmt_jeonse(item))
            lines.append("")
        for item in s_new[:3]:
            lines.append(fmt_sale(item))
            lines.append("")

        await bot_app.bot.send_message(chat_id=CHAT_ID, text="\n".join(lines))

        # AI 분석
        if j_new or s_new:
            ai = analyze_top_listings(j_new[:3], s_new[:3])
            await bot_app.bot.send_message(chat_id=CHAT_ID, text=ai)

    except Exception as e:
        log.error(f"일일 스캔 오류: {e}")


# ── 스케줄: 매주 월요일 08:30 주간 리포트 ────────────────────────────

async def weekly_report_task(ctx: ContextTypes.DEFAULT_TYPE):
    if datetime.now().weekday() != 0:
        return
    log.info("주간 리포트 시작")
    try:
        raw   = collect_all(months=1)
        stats = {}
        for item in raw["jeonse"] + raw["sale"]:
            d = item.get("district","기타")
            t = item.get("trade_type","")
            if d not in stats:
                stats[d] = {"jeonse":[], "sale":[]}
            p = item.get("deposit" if t=="jeonse" else "price", 0)
            if p > 0:
                stats[d][t].append(p)
        region_summary = {
            r: {
                "jeonse_avg": int(sum(v["jeonse"])/len(v["jeonse"])//10000) if v["jeonse"] else 0,
                "sale_avg":   int(sum(v["sale"])/len(v["sale"])//10000)     if v["sale"]   else 0,
            }
            for r, v in stats.items()
        }
        report = weekly_report(region_summary)
        await bot_app.bot.send_message(chat_id=CHAT_ID, text=report)
    except Exception as e:
        log.error(f"주간 리포트 오류: {e}")


# ── 메인 ─────────────────────────────────────────────────────────────

def main():
    global bot_app
    init_db()

    bot_app = Application.builder().token(TOKEN).build()

    # 명령어 등록
    handlers = [
        ("start",     cmd_start),
        ("scan",      cmd_scan),
        ("jeonse",    cmd_jeonse),
        ("sale",      cmd_sale),
        ("fraud",     cmd_fraud),
        ("watch",     cmd_watch),
        ("unwatch",   cmd_unwatch),
        ("watchlist", cmd_watchlist),
        ("set",       cmd_set),
        ("compare",   cmd_compare),
        ("report",    cmd_report),
        ("status",    cmd_status),
    ]
    for cmd, handler in handlers:
        bot_app.add_handler(CommandHandler(cmd, handler))

    # 스케줄 등록
    jq = bot_app.job_queue
    jq.run_daily(daily_scan,          dtime(8, 0),  name="daily_scan")
    jq.run_daily(weekly_report_task,  dtime(8, 30), name="weekly_report")

    log.info("부동산 AI 봇 시작")
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
