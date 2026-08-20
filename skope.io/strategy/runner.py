"""CLI entrypoints for Cloud Run Jobs / local cron."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python -m strategy.runner` from skope.io/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy import db
from strategy.gemini_ranker import rank_with_gemini
from strategy.scanner import run_scanner
from strategy.settings import get_settings
from strategy.sniper import manage_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("skope.runner")


def run_screen() -> int:
    settings = get_settings()
    candidates = run_scanner(settings)
    ranked = rank_with_gemini(candidates, settings)
    if not ranked:
        db.log_event("screen", "No candidates passed filters")
        logger.info("No candidates")
        return 0
    n = db.upsert_candidates(ranked)
    db.log_event(
        "screen",
        f"Upserted {n} candidates",
        {"symbols": [c["symbol"] for c in ranked]},
    )
    logger.info("Upserted %s candidates: %s", n, [c["symbol"] for c in ranked])
    return n


def run_manage() -> dict:
    return manage_once(get_settings())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="skope.io screen / manage runner")
    parser.add_argument(
        "--mode",
        choices=("screen", "manage"),
        required=True,
        help="screen = Finviz/Finnhub/Gemini setup; manage = Alpaca risk/exits",
    )
    args = parser.parse_args(argv)
    if args.mode == "screen":
        run_screen()
    else:
        run_manage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
