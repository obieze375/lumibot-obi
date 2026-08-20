# skope.io

Premarket high-volume momentum scalping (“sniping”) on top of Lumibot + Alpaca.

Name from Greek **skopeftís** (sniper / marksman).

## What it does

1. **Screen window (08:00–13:00 Europe/London)**  
   Finviz + Finnhub scan for premarket gappers: day volume ≥ 1M, avg volume ≥ 500k–1M, RVOL ≥ 3–5×, % change ≥ 20%.  
   Gemini ranks candidates. Results land in Neon and appear on the dashboard.

2. **Trade window (from ~14:30 Europe/London / NYSE open)**  
   You 1-click approve a candidate on the dashboard → Alpaca places the order via Lumibot.  
   Targets +10% take-profit, −10% stop, 10% portfolio sizing, and a daily kill-switch after a −10% day loss.

3. **Dashboard (Netlify)**  
   Kinetic typography UI showing live candidates, open positions, fills, and 1-click trade.

## Layout

```
skope.io/
  api/           FastAPI (candidates, approve trade, positions, history)
  strategy/      Finviz/Finnhub scanner, Gemini ranker, Lumibot sniper
  dashboard/     Vite + React + Tailwind (Netlify)
  sql/           Neon schema
  cloud-run/     Cloud Run Job + Scheduler manifests
  scripts/       Local runners
  Dockerfile     API + strategy image
```

## Required secrets (never commit real values)

| Variable | Purpose |
|---|---|
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | Alpaca trading |
| `ALPACA_IS_PAPER` | `true` (default) or `false` |
| `FINNHUB_API_KEY` | Volume / quote enrichment |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Candidate ranking |
| `DATABASE_URL` | Neon Postgres connection string |
| `SKOPE_API_TOKEN` | Protects approve-trade endpoint |
| `VITE_API_BASE_URL` | Dashboard → API URL |
| `VITE_API_TOKEN` | Same token for dashboard calls |

## Local quick start

```bash
cd skope.io
cp .env.example .env   # fill placeholders
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# screen once
python -m strategy.runner --mode screen

# API
uvicorn api.main:app --reload --port 8080

# dashboard
cd dashboard && npm install && npm run dev
```

## Cloud Run (free-tier oriented)

Use **Jobs + Scheduler**, not an always-on service with min instances:

- `skope-screen` every 10–15 min, 08:00–13:00 London
- `skope-manage` every 1–2 min during NYSE hours (manage stops/targets only)
- Keep the API as a scale-to-zero Cloud Run **service** for dashboard 1-click trades

See `cloud-run/` for YAML and cron expressions.

## Safety defaults

- Paper trading on by default
- No autonomous entries — dashboard **1-click** is required
- Daily kill-switch after −10% portfolio day loss
- Position size capped at 10% of equity
