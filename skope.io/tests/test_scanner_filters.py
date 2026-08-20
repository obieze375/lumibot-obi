"""Unit tests for skope.io hard filters (no network)."""

from strategy.scanner import apply_hard_filters
from strategy.settings import Settings


def test_apply_hard_filters_keeps_liquid_gapper():
    settings = Settings(
        SKOPE_MIN_AVG_VOLUME=500_000,
        SKOPE_MIN_DAY_VOLUME=1_000_000,
        SKOPE_MIN_RVOL=3.0,
        SKOPE_MIN_PCT_CHANGE=20.0,
    )
    rows = [
        {
            "symbol": "PLAG",
            "pct_change": 58.0,
            "day_volume": 2_500_000,
            "avg_volume": 600_000,
            "rvol": 4.1,
            "price": 1.37,
        },
        {
            "symbol": "THIN",
            "pct_change": 40.0,
            "day_volume": 100_000,
            "avg_volume": 50_000,
            "rvol": 8.0,
            "price": 2.0,
        },
    ]
    kept = apply_hard_filters(rows, settings)
    assert [r["symbol"] for r in kept] == ["PLAG"]


def test_rvol_derived_from_volumes():
    settings = Settings(
        SKOPE_MIN_AVG_VOLUME=500_000,
        SKOPE_MIN_DAY_VOLUME=1_000_000,
        SKOPE_MIN_RVOL=3.0,
        SKOPE_MIN_PCT_CHANGE=20.0,
    )
    rows = [
        {
            "symbol": "MOMO",
            "pct_change": 25.0,
            "day_volume": 3_000_000,
            "avg_volume": 750_000,
            "rvol": None,
            "price": 5.0,
        }
    ]
    kept = apply_hard_filters(rows, settings)
    assert len(kept) == 1
    assert kept[0]["rvol"] == 4.0
