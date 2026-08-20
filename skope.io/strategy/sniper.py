"""
Lumibot strategy wrapper for skope.io position management during NYSE hours.

Entries are human 1-click via the API. This strategy only:
- refreshes Alpaca positions into Neon
- enforces daily kill-switch logging
- optionally liquidates if kill-switch is on
"""

from __future__ import annotations

import logging
from typing import Optional

from strategy import db
from strategy.alpaca_exec import get_account_equity, sync_open_orders
from strategy.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def manage_once(settings: Optional[Settings] = None) -> dict:
    settings = settings or get_settings()
    risk = db.get_daily_risk()
    equity = get_account_equity(settings)
    if risk is None:
        risk = db.upsert_daily_risk(starting_equity=equity, realized_pnl=0, kill_switch=False)

    starting = float(risk.get("starting_equity") or equity)
    # Approximate day PnL from equity drift when broker realized fields are unavailable.
    day_pnl_pct = (equity - starting) / starting if starting else 0.0
    kill = bool(risk.get("kill_switch"))
    if day_pnl_pct <= -settings.daily_loss_kill_pct:
        kill = True
        db.upsert_daily_risk(kill_switch=True, realized_pnl=equity - starting)
        db.log_event(
            "kill_switch",
            f"Daily loss {day_pnl_pct:.2%} hit kill switch",
            {"equity": equity, "starting": starting},
            level="warning",
        )

    snapshot = sync_open_orders(settings)
    if kill and snapshot["positions"]:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import ClosePositionRequest

        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_api_secret,
            paper=bool(settings.alpaca_is_paper),
        )
        for pos in snapshot["positions"]:
            try:
                client.close_position(pos["symbol"])
                db.log_event("flatten", f"Closed {pos['symbol']} due to kill switch", pos)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to flatten %s: %s", pos["symbol"], exc)

    db.log_event("manage", "Manage cycle complete", {"kill": kill, **snapshot})
    return {"kill_switch": kill, "equity": equity, "day_pnl_pct": day_pnl_pct, **snapshot}


try:
    from lumibot.strategies import Strategy

    class SkopeSniperStrategy(Strategy):
        """Optional Lumibot lifecycle runner for the manage window."""

        parameters = {
            "sleep_time": 60,
        }

        def initialize(self):
            self.sleeptime = self.parameters.get("sleep_time", 60)
            self.settings = get_settings()

        def on_trading_iteration(self):
            result = manage_once(self.settings)
            if result.get("kill_switch"):
                self.log_message("SKOPE kill switch active — no new risk")

except Exception:  # noqa: BLE001 - allow API-only installs without lumibot import side effects
    SkopeSniperStrategy = None  # type: ignore
