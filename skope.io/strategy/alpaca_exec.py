"""Alpaca execution helpers for 1-click snipes and position management."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any, Dict, Optional

from strategy.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _trading_client(settings: Settings):
    from alpaca.trading.client import TradingClient

    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET are required")
    return TradingClient(
        settings.alpaca_api_key,
        settings.alpaca_api_secret,
        paper=bool(settings.alpaca_is_paper),
    )


def get_account_equity(settings: Optional[Settings] = None) -> float:
    settings = settings or get_settings()
    client = _trading_client(settings)
    account = client.get_account()
    return float(account.equity)


def place_bracket_long(
    symbol: str,
    settings: Optional[Settings] = None,
    limit_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Size at 10% equity and submit a bracket: +10% TP / -10% SL."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
    )

    settings = settings or get_settings()
    client = _trading_client(settings)
    equity = float(client.get_account().equity)
    if equity <= 0:
        raise RuntimeError("Account equity is zero")

    # Latest trade / quote for sizing
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest

    data = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_api_secret)
    latest = data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
    trade = latest[symbol]
    px = float(limit_price or trade.price)
    if px <= 0:
        raise RuntimeError(f"Invalid price for {symbol}")

    notional = equity * settings.position_pct
    qty = math.floor(notional / px)
    if qty < 1:
        raise RuntimeError(
            f"Position size too small: equity={equity:.2f} price={px:.4f} "
            f"alloc={settings.position_pct:.0%}"
        )

    tp = round(px * (1 + settings.take_profit_pct), 4)
    sl = round(px * (1 - settings.stop_loss_pct), 4)
    client_order_id = f"skope-{symbol.lower()}-{uuid.uuid4().hex[:10]}"

    # Extended hours premarket: prefer limit DAY. Regular hours: market bracket.
    try:
        clock = client.get_clock()
        is_open = bool(clock.is_open)
    except Exception:  # noqa: BLE001
        is_open = True

    if is_open:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=tp),
            stop_loss=StopLossRequest(stop_price=sl),
            client_order_id=client_order_id,
        )
    else:
        # Premarket: single limit; manager will attach exits after fill if needed.
        req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            limit_price=round(px * 1.01, 4),
            extended_hours=True,
            client_order_id=client_order_id,
        )

    order = client.submit_order(req)
    return {
        "symbol": symbol,
        "qty": qty,
        "entry_price": px,
        "limit_price": getattr(req, "limit_price", None),
        "take_profit_price": tp,
        "stop_loss_price": sl,
        "status": str(order.status),
        "alpaca_order_id": str(order.id),
        "alpaca_client_order_id": client_order_id,
        "raw": order.model_dump() if hasattr(order, "model_dump") else {"id": str(order.id)},
        "equity": equity,
        "paper": settings.alpaca_is_paper,
    }


def sync_open_orders(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Lightweight manage pass: cancel day leftovers after kill-switch, report positions."""
    settings = settings or get_settings()
    client = _trading_client(settings)
    positions = client.get_all_positions()
    orders = client.get_orders()
    return {
        "positions": [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_plpc": float(p.unrealized_plpc),
                "current_price": float(p.current_price),
            }
            for p in positions
        ],
        "open_orders": len(list(orders)),
    }
