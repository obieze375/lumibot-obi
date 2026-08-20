"""FastAPI backend for skope.io dashboard + 1-click Alpaca trades."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy import db
from strategy.alpaca_exec import place_bracket_long
from strategy.gemini_ranker import rank_with_gemini
from strategy.scanner import run_scanner
from strategy.settings import get_settings
from strategy.sniper import manage_once

app = FastAPI(title="skope.io", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def require_token(authorization: Optional[str] = Header(default=None), x_skope_token: Optional[str] = Header(default=None)):
    settings = get_settings()
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_skope_token:
        token = x_skope_token.strip()
    if not token or token != settings.skope_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


class ApproveTradeRequest(BaseModel):
    candidate_id: str
    limit_price: Optional[float] = Field(default=None)


@app.get("/health")
def health():
    return {"ok": True, "service": "skope.io", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/api/status")
def status(_: bool = Depends(require_token)):
    risk = db.get_daily_risk()
    return {
        "paper": get_settings().alpaca_is_paper,
        "risk": _serialize(risk),
        "candidates_today": len(db.list_candidates(limit=500)),
        "open_trades": len(db.list_open_trades()),
    }


@app.get("/api/candidates")
def candidates(status_filter: Optional[str] = None, _: bool = Depends(require_token)):
    rows = db.list_candidates(status=status_filter, limit=100)
    return {"candidates": _serialize(rows)}


@app.get("/api/trades")
def trades(_: bool = Depends(require_token)):
    return {"trades": _serialize(db.list_trades(limit=200))}


@app.get("/api/events")
def events(_: bool = Depends(require_token)):
    return {"events": _serialize(db.list_events(limit=100))}


@app.post("/api/screen")
def screen_now(_: bool = Depends(require_token)):
    settings = get_settings()
    found = run_scanner(settings)
    ranked = rank_with_gemini(found, settings)
    n = db.upsert_candidates(ranked) if ranked else 0
    db.log_event("screen_manual", f"Manual screen upserted {n}", {"symbols": [c["symbol"] for c in ranked]})
    return {"count": n, "candidates": _serialize(ranked)}


@app.post("/api/trades/approve")
def approve_trade(body: ApproveTradeRequest, _: bool = Depends(require_token)):
    settings = get_settings()
    risk = db.get_daily_risk()
    if risk and risk.get("kill_switch"):
        raise HTTPException(status_code=403, detail="Daily kill switch is active")

    candidate = db.get_candidate(body.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.get("status") == "traded":
        raise HTTPException(status_code=409, detail="Candidate already traded")

    try:
        result = place_bracket_long(
            symbol=candidate["symbol"],
            settings=settings,
            limit_price=body.limit_price or float(candidate["price"] or 0) or None,
        )
    except Exception as exc:  # noqa: BLE001
        db.log_event("trade_error", str(exc), {"candidate_id": body.candidate_id}, level="error")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trade = db.insert_trade(
        {
            "candidate_id": body.candidate_id,
            "symbol": candidate["symbol"],
            "side": "buy",
            "qty": result["qty"],
            "entry_price": result["entry_price"],
            "limit_price": result.get("limit_price"),
            "take_profit_price": result["take_profit_price"],
            "stop_loss_price": result["stop_loss_price"],
            "status": "submitted",
            "alpaca_order_id": result["alpaca_order_id"],
            "alpaca_client_order_id": result["alpaca_client_order_id"],
            "notes": "1-click dashboard approve",
            "raw": result.get("raw") or {},
        }
    )
    db.set_candidate_status(body.candidate_id, "traded")
    db.log_event(
        "trade_approved",
        f"Approved {candidate['symbol']}",
        {"trade_id": str(trade["id"]), "order_id": result["alpaca_order_id"]},
    )
    return {"trade": _serialize(trade), "alpaca": _serialize(result)}


@app.post("/api/manage")
def manage(_: bool = Depends(require_token)):
    return _serialize(manage_once(get_settings()))


@app.post("/api/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, _: bool = Depends(require_token)):
    db.set_candidate_status(candidate_id, "rejected")
    return {"ok": True, "id": candidate_id, "status": "rejected"}
