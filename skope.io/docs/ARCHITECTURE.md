# skope.io engineering notes

**Last Updated:** 2026-08-20  
**Status:** Initial scaffold  
**Audience:** Contributors deploying the sniping desk

## Overview

`skope.io` is a self-contained add-on in the Lumibot monorepo. It does **not** replace Lumibot; it orchestrates:

1. Premarket screening (Finviz + Finnhub + Gemini)
2. Human 1-click Alpaca entries via FastAPI
3. Lumibot-compatible manage loop for stops / daily kill-switch
4. Neon trade history + Netlify kinetic dashboard

## Schedule (Europe/London)

| Window | Mode | Behavior |
|---|---|---|
| 08:00–13:00 | `screen` | Setup filters only — no auto entries |
| ~14:30–21:00 | `manage` | Watch Alpaca positions / enforce kill-switch |
| Anytime | API `POST /api/trades/approve` | 1-click entry from dashboard |

US premarket ~06:00 ET falls inside the London morning screen window for most of the year.

## Free-tier Cloud Run guidance

Prefer **Jobs + Scheduler** over min-instances. An always-on bot will burn free CPU allotment quickly. Keep the API at `min-instances=0`.

## Safety

- Default `ALPACA_IS_PAPER=true`
- Entries require dashboard approval
- Daily −10% equity kill-switch flattens and blocks new approvals
