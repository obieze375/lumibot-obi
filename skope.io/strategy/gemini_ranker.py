"""Gemini ranking for screened momentum candidates."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from strategy.settings import Settings, get_settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a premarket momentum risk analyst for a sniping/scalping desk.
Score each ticker 0-100 for a same-day long scalp with +10% target and -10% stop.
Favor: strong % change, high RVOL, liquid day volume, clean continuation setup.
Penalize: extreme halt risk, illiquidity, absurd extension without volume confirmation.
Return ONLY valid JSON array: [{"symbol":"ABC","score":81,"rationale":"..."}]
"""


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def rank_with_gemini(candidates: List[Dict[str, Any]], settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    settings = settings or get_settings()
    if not candidates:
        return []

    api_key = settings.effective_gemini_key
    if not api_key:
        logger.warning("No Gemini API key — using heuristic scores")
        return _heuristic_rank(candidates)

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=settings.skope_gemini_model,
            system_instruction=SYSTEM_PROMPT,
        )
        compact = [
            {
                "symbol": c["symbol"],
                "company": c.get("company"),
                "price": c.get("price"),
                "pct_change": c.get("pct_change"),
                "day_volume": c.get("day_volume"),
                "avg_volume": c.get("avg_volume"),
                "rvol": c.get("rvol"),
            }
            for c in candidates
        ]
        prompt = (
            "Rank these premarket gappers for a 10% scalp with 10% stop.\n"
            + json.dumps(compact, default=str)
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
        ranked = _extract_json_array(text)
        by_symbol = {str(item.get("symbol", "")).upper(): item for item in ranked}
        out: List[Dict[str, Any]] = []
        for c in candidates:
            hit = by_symbol.get(c["symbol"], {})
            c = dict(c)
            c["gemini_score"] = float(hit.get("score") or _heuristic_one(c))
            c["gemini_rationale"] = str(hit.get("rationale") or "Heuristic fallback")
            out.append(c)
        out.sort(key=lambda x: x.get("gemini_score") or 0, reverse=True)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini ranking failed (%s) — heuristic fallback", exc)
        return _heuristic_rank(candidates)


def _heuristic_one(c: Dict[str, Any]) -> float:
    pct = float(c.get("pct_change") or 0)
    rvol = float(c.get("rvol") or 0)
    day_vol = float(c.get("day_volume") or 0)
    score = min(40.0, pct) + min(40.0, rvol * 8.0) + min(20.0, day_vol / 1_000_000 * 4.0)
    return round(min(100.0, score), 2)


def _heuristic_rank(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in candidates:
        item = dict(c)
        item["gemini_score"] = _heuristic_one(item)
        item["gemini_rationale"] = "Heuristic score (Gemini unavailable)"
        out.append(item)
    out.sort(key=lambda x: x.get("gemini_score") or 0, reverse=True)
    return out
