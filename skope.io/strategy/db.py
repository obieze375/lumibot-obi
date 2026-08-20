"""Neon / Postgres helpers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from strategy.settings import get_settings


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)!r} is not JSON serializable")


@contextmanager
def connect():
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for Neon persistence")
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def upsert_candidates(rows: Iterable[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO candidates (
        symbol, company, price, pct_change, day_volume, avg_volume, rvol,
        float_shares, gemini_score, gemini_rationale, status, source, raw, session_date
    ) VALUES (
        %(symbol)s, %(company)s, %(price)s, %(pct_change)s, %(day_volume)s, %(avg_volume)s,
        %(rvol)s, %(float_shares)s, %(gemini_score)s, %(gemini_rationale)s, 'pending',
        %(source)s, %(raw)s::jsonb, CURRENT_DATE
    )
    ON CONFLICT (symbol, session_date) DO UPDATE SET
        company = EXCLUDED.company,
        price = EXCLUDED.price,
        pct_change = EXCLUDED.pct_change,
        day_volume = EXCLUDED.day_volume,
        avg_volume = EXCLUDED.avg_volume,
        rvol = EXCLUDED.rvol,
        float_shares = EXCLUDED.float_shares,
        gemini_score = EXCLUDED.gemini_score,
        gemini_rationale = EXCLUDED.gemini_rationale,
        raw = EXCLUDED.raw,
        screened_at = NOW(),
        status = CASE
            WHEN candidates.status IN ('approved', 'traded') THEN candidates.status
            ELSE 'pending'
        END
    """
    count = 0
    with connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                payload = dict(row)
                payload["raw"] = json.dumps(payload.get("raw") or payload, default=_json_default)
                payload.setdefault("source", "finviz+finnhub")
                cur.execute(sql, payload)
                count += 1
        conn.commit()
    return count


def list_candidates(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    clauses = ["session_date = CURRENT_DATE"]
    params: Dict[str, Any] = {"limit": limit}
    if status:
        clauses.append("status = %(status)s")
        params["status"] = status
    where = " AND ".join(clauses)
    sql = f"""
        SELECT * FROM candidates
        WHERE {where}
        ORDER BY gemini_score DESC NULLS LAST, pct_change DESC NULLS LAST, screened_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def get_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
            return cur.fetchone()


def set_candidate_status(candidate_id: str, status: str) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET status = %s WHERE id = %s",
                (status, candidate_id),
            )
        conn.commit()


def insert_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    sql = """
    INSERT INTO trades (
        candidate_id, symbol, side, qty, entry_price, limit_price,
        take_profit_price, stop_loss_price, status, alpaca_order_id,
        alpaca_client_order_id, notes, raw
    ) VALUES (
        %(candidate_id)s, %(symbol)s, %(side)s, %(qty)s, %(entry_price)s, %(limit_price)s,
        %(take_profit_price)s, %(stop_loss_price)s, %(status)s, %(alpaca_order_id)s,
        %(alpaca_client_order_id)s, %(notes)s, %(raw)s::jsonb
    )
    RETURNING *
    """
    payload = dict(trade)
    payload["raw"] = json.dumps(payload.get("raw") or {}, default=_json_default)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, payload)
            row = cur.fetchone()
        conn.commit()
    return row


def list_trades(limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM trades
                ORDER BY opened_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def list_open_trades() -> List[Dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM trades
                WHERE status IN ('submitted', 'filled')
                ORDER BY opened_at DESC
                """
            )
            return list(cur.fetchall())


def update_trade(trade_id: str, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    cols = []
    params: Dict[str, Any] = {"id": trade_id}
    for key, value in fields.items():
        if key == "raw":
            cols.append("raw = %(raw)s::jsonb")
            params["raw"] = json.dumps(value, default=_json_default)
        else:
            cols.append(f"{key} = %({key})s")
            params[key] = value
    sql = f"UPDATE trades SET {', '.join(cols)} WHERE id = %(id)s"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def log_event(event_type: str, message: str, payload: Optional[Dict[str, Any]] = None, level: str = "info") -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_events (level, event_type, message, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (level, event_type, message, json.dumps(payload or {}, default=_json_default)),
            )
        conn.commit()


def get_daily_risk() -> Optional[Dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM daily_risk WHERE session_date = CURRENT_DATE")
            return cur.fetchone()


def upsert_daily_risk(
    starting_equity: Optional[float] = None,
    realized_pnl: Optional[float] = None,
    kill_switch: Optional[bool] = None,
) -> Dict[str, Any]:
    existing = get_daily_risk()
    if existing is None:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_risk (session_date, starting_equity, realized_pnl, kill_switch)
                    VALUES (CURRENT_DATE, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        starting_equity,
                        realized_pnl if realized_pnl is not None else 0,
                        bool(kill_switch) if kill_switch is not None else False,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row

    fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if starting_equity is not None:
        fields["starting_equity"] = starting_equity
    if realized_pnl is not None:
        fields["realized_pnl"] = realized_pnl
    if kill_switch is not None:
        fields["kill_switch"] = kill_switch
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    fields["session_date"] = existing["session_date"]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE daily_risk SET {sets} WHERE session_date = %(session_date)s RETURNING *",
                fields,
            )
            row = cur.fetchone()
        conn.commit()
    return row


def list_events(limit: int = 50) -> List[Dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM bot_events ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return list(cur.fetchall())
