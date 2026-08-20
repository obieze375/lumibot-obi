-- skope.io Neon / Postgres schema
-- Run once against your Neon DATABASE_URL

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    company TEXT,
    price NUMERIC(18, 6),
    pct_change NUMERIC(12, 4),
    day_volume BIGINT,
    avg_volume BIGINT,
    rvol NUMERIC(12, 4),
    float_shares BIGINT,
    gemini_score NUMERIC(6, 2),
    gemini_rationale TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected | expired | traded
    source TEXT NOT NULL DEFAULT 'finviz+finnhub',
    screened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (symbol, session_date)
);

CREATE INDEX IF NOT EXISTS idx_candidates_session_status
    ON candidates (session_date, status, gemini_score DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'buy',
    qty NUMERIC(18, 6) NOT NULL,
    entry_price NUMERIC(18, 6),
    limit_price NUMERIC(18, 6),
    take_profit_price NUMERIC(18, 6),
    stop_loss_price NUMERIC(18, 6),
    exit_price NUMERIC(18, 6),
    status TEXT NOT NULL DEFAULT 'submitted', -- submitted | filled | closed | canceled | rejected
    alpaca_order_id TEXT,
    alpaca_client_order_id TEXT,
    pnl_pct NUMERIC(12, 4),
    notes TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trades_status_opened
    ON trades (status, opened_at DESC);

CREATE TABLE IF NOT EXISTS bot_events (
    id BIGSERIAL PRIMARY KEY,
    level TEXT NOT NULL DEFAULT 'info',
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_risk (
    session_date DATE PRIMARY KEY,
    starting_equity NUMERIC(18, 6),
    realized_pnl NUMERIC(18, 6) NOT NULL DEFAULT 0,
    kill_switch BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
