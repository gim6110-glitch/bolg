"""
modules/db.py
SQLite DB 초기화 및 공통 쿼리
- 매물 중복 알림 방지
- 관심 단지 watchlist
- 가격 추이 히스토리
- AI 호출 횟수 추적
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'realestate.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DB 테이블 초기화"""
    conn = get_conn()
    c = conn.cursor()

    # 알림 발송 이력 (중복 방지)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id  TEXT NOT NULL,
            trade_type  TEXT NOT NULL,
            price       INTEGER,
            score       REAL,
            alerted_at  TEXT NOT NULL,
            UNIQUE(listing_id, trade_type)
        )
    """)

    # 매물 가격 추이 히스토리
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            complex_name TEXT NOT NULL,
            district    TEXT,
            trade_type  TEXT,
            price       INTEGER,
            area        REAL,
            floor       TEXT,
            recorded_at TEXT NOT NULL
        )
    """)

    # 관심 단지 watchlist
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            complex_name TEXT NOT NULL UNIQUE,
            district     TEXT,
            added_at     TEXT NOT NULL,
            memo         TEXT
        )
    """)

    # AI 호출 횟수 추적
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_call_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            call_date  TEXT NOT NULL,
            purpose    TEXT,
            called_at  TEXT NOT NULL
        )
    """)

    # 전세가율 추이 (역전세 위험 모니터링)
    c.execute("""
        CREATE TABLE IF NOT EXISTS jeonse_ratio_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            complex_name TEXT NOT NULL,
            district     TEXT,
            jeonse_price INTEGER,
            sale_price   INTEGER,
            ratio        REAL,
            recorded_at  TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] 초기화 완료")


# ── 중복 알림 방지 ───────────────────────────────────────────────────

def is_already_alerted(listing_id: str, trade_type: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM alert_history WHERE listing_id=? AND trade_type=?",
        (listing_id, trade_type)
    ).fetchone()
    conn.close()
    return row is not None


def mark_alerted(listing_id: str, trade_type: str, price: int, score: float):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            """INSERT OR REPLACE INTO alert_history
               (listing_id, trade_type, price, score, alerted_at)
               VALUES (?,?,?,?,?)""",
            (listing_id, trade_type, price, score, now)
        )
        conn.commit()
    except Exception as e:
        print(f"[DB] mark_alerted 오류: {e}")
    finally:
        conn.close()


def update_alert_price(listing_id: str, trade_type: str, new_price: int):
    """가격 변동 시 재알림 허용을 위해 기존 기록 삭제"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM alert_history WHERE listing_id=? AND trade_type=?",
        (listing_id, trade_type)
    )
    conn.commit()
    conn.close()


# ── 가격 히스토리 ────────────────────────────────────────────────────

def save_price_history(complex_name: str, district: str, trade_type: str,
                       price: int, area: float, floor: str):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO price_history
           (complex_name, district, trade_type, price, area, floor, recorded_at)
           VALUES (?,?,?,?,?,?,?)""",
        (complex_name, district, trade_type, price, area, floor, now)
    )
    conn.commit()
    conn.close()


def get_price_trend(complex_name: str, trade_type: str, days: int = 90) -> list:
    """최근 N일간 가격 추이"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT price, area, recorded_at FROM price_history
           WHERE complex_name LIKE ? AND trade_type=?
           ORDER BY recorded_at DESC LIMIT 20""",
        (f"%{complex_name}%", trade_type)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Watchlist ────────────────────────────────────────────────────────

def add_watchlist(complex_name: str, district: str = "", memo: str = "") -> bool:
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            """INSERT INTO watchlist (complex_name, district, added_at, memo)
               VALUES (?,?,?,?)""",
            (complex_name, district, now, memo)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_watchlist(complex_name: str) -> bool:
    conn = get_conn()
    result = conn.execute(
        "DELETE FROM watchlist WHERE complex_name LIKE ?",
        (f"%{complex_name}%",)
    )
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


def get_watchlist() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT complex_name, district, added_at, memo FROM watchlist ORDER BY added_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── AI 호출 관리 ─────────────────────────────────────────────────────

def get_today_ai_calls() -> int:
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM ai_call_log WHERE call_date=?",
        (today,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def log_ai_call(purpose: str = ""):
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO ai_call_log (call_date, purpose, called_at) VALUES (?,?,?)",
        (today, purpose, now)
    )
    conn.commit()
    conn.close()


def can_call_ai(max_daily: int = 5) -> bool:
    return get_today_ai_calls() < max_daily


# ── 전세가율 히스토리 ────────────────────────────────────────────────

def save_jeonse_ratio(complex_name: str, district: str,
                      jeonse_price: int, sale_price: int, ratio: float):
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO jeonse_ratio_history
           (complex_name, district, jeonse_price, sale_price, ratio, recorded_at)
           VALUES (?,?,?,?,?,?)""",
        (complex_name, district, jeonse_price, sale_price, ratio, now)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("[DB] 테이블 생성 완료")
    print(f"[DB] 경로: {os.path.abspath(DB_PATH)}")
