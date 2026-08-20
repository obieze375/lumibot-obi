"""Finviz + Finnhub premarket momentum scanner."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from strategy.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, str):
            cleaned = value.replace("%", "").replace(",", "").strip()
            if cleaned.endswith("M"):
                return float(cleaned[:-1]) * 1_000_000
            if cleaned.endswith("K"):
                return float(cleaned[:-1]) * 1_000
            if cleaned.endswith("B"):
                return float(cleaned[:-1]) * 1_000_000_000
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    number = _to_float(value)
    return int(number) if number is not None else None


def screen_finviz(settings: Optional[Settings] = None):
    """Pull Finviz overview rows matching avg volume / RVOL / % change."""
    import pandas as pd

    settings = settings or get_settings()
    try:
        from finvizfinance.screener.overview import Overview
    except ImportError as exc:  # pragma: no cover - env without optional deps
        raise RuntimeError("Install finvizfinance to run the premarket scanner") from exc

    # Prefer stricter avg volume; fall back to 500k+ if empty.
    filter_attempts = [
        {
            "Average Volume": "Over 1M",
            "Relative Volume": "Over 3",
            "Change": "Up 20%",
        },
        {
            "Average Volume": "Over 500K",
            "Relative Volume": "Over 3",
            "Change": "Up 20%",
        },
    ]

    frames: List[Any] = []
    for filters_dict in filter_attempts:
        try:
            overview = Overview()
            overview.set_filter(filters_dict=filters_dict)
            df = overview.screener_view(verbose=0)
            if df is not None and not df.empty:
                df = df.copy()
                df["_filter_set"] = str(filters_dict)
                frames.append(df)
                logger.info("Finviz returned %s rows for %s", len(df), filters_dict)
                break
        except Exception as exc:  # noqa: BLE001 - scanner must degrade gracefully
            logger.warning("Finviz screen failed for %s: %s", filters_dict, exc)

    if not frames:
        return pd.DataFrame()

    df = frames[0]
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key == "ticker":
            rename[col] = "symbol"
        elif key in {"company", "name"}:
            rename[col] = "company"
        elif key == "price":
            rename[col] = "price"
        elif key in {"change", "change %", "change%"}:
            rename[col] = "pct_change"
        elif key in {"volume", "current volume"}:
            rename[col] = "day_volume"
        elif key in {"average volume", "avg volume", "avg. volume"}:
            rename[col] = "avg_volume"
        elif key in {"relative volume", "rel volume"}:
            rename[col] = "rvol"
        elif key in {"float", "shares float"}:
            rename[col] = "float_shares"
    return df.rename(columns=rename)


def enrich_finnhub(rows: List[Dict[str, Any]], settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    """Confirm day volume / % change with Finnhub quotes when a key is present."""
    settings = settings or get_settings()
    if not settings.finnhub_api_key:
        logger.warning("FINNHUB_API_KEY missing — skipping Finnhub enrichment")
        return rows

    try:
        import finnhub
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install finnhub-python to enrich quotes") from exc

    client = finnhub.Client(api_key=settings.finnhub_api_key)
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        symbol = row["symbol"]
        try:
            quote = client.quote(symbol) or {}
            current = _to_float(quote.get("c"))
            pct = _to_float(quote.get("dp"))
            if current:
                row["price"] = current
            if pct is not None:
                row["pct_change"] = pct
            row.setdefault("raw", {})
            row["raw"]["finnhub_quote"] = quote

            metrics = client.company_basic_financials(symbol, "all") or {}
            metric = metrics.get("metric") or {}
            avg10 = _to_float(metric.get("10DayAverageTradingVolume"))
            if avg10 is not None:
                avg_shares = int(avg10 * 1_000_000) if avg10 < 10_000 else int(avg10)
                row["avg_volume"] = row.get("avg_volume") or avg_shares
            row["raw"]["finnhub_metrics"] = metric
        except Exception as exc:  # noqa: BLE001
            logger.warning("Finnhub enrich failed for %s: %s", symbol, exc)
        enriched.append(row)
    return enriched


def apply_hard_filters(rows: List[Dict[str, Any]], settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    settings = settings or get_settings()
    kept: List[Dict[str, Any]] = []
    for row in rows:
        pct = _to_float(row.get("pct_change"))
        day_vol = _to_int(row.get("day_volume"))
        avg_vol = _to_int(row.get("avg_volume"))
        rvol = _to_float(row.get("rvol"))

        if rvol is None and day_vol and avg_vol and avg_vol > 0:
            rvol = day_vol / avg_vol
            row["rvol"] = rvol

        row["pct_change"] = pct
        row["day_volume"] = day_vol
        row["avg_volume"] = avg_vol
        row["price"] = _to_float(row.get("price"))
        row["float_shares"] = _to_int(row.get("float_shares"))

        if not row.get("symbol"):
            continue
        if pct is None or pct < settings.min_pct_change:
            continue
        if day_vol is None or day_vol < settings.min_day_volume:
            continue
        if avg_vol is None or avg_vol < settings.min_avg_volume:
            continue
        if rvol is None or rvol < settings.min_rvol:
            continue
        kept.append(row)
    return kept


def run_scanner(settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    settings = settings or get_settings()
    df = screen_finviz(settings)
    if df.empty:
        logger.info("No Finviz candidates")
        return []

    rows: List[Dict[str, Any]] = []
    for _, series in df.iterrows():
        item = series.to_dict()
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "company": item.get("company"),
                "price": item.get("price"),
                "pct_change": item.get("pct_change"),
                "day_volume": item.get("day_volume"),
                "avg_volume": item.get("avg_volume"),
                "rvol": item.get("rvol"),
                "float_shares": item.get("float_shares"),
                "source": "finviz+finnhub",
                "raw": {"finviz": item},
            }
        )

    rows = enrich_finnhub(rows, settings)
    rows = apply_hard_filters(rows, settings)
    logger.info("Hard filters kept %s candidates", len(rows))
    return rows
