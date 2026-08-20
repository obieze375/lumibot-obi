import { useEffect, useMemo, useState } from "react";
import Marquee from "react-fast-marquee";
import { motion, useReducedMotion } from "framer-motion";
import { api } from "./api";

function Noise() {
  return (
    <svg className="noise" aria-hidden="true">
      <title>Noise texture</title>
      <filter id="noiseFilter">
        <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch" />
      </filter>
      <rect width="100%" height="100%" filter="url(#noiseFilter)" />
    </svg>
  );
}

function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return `${Number(v).toFixed(2)}%`;
}

function fmtNum(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toLocaleString();
}

function fmtMoney(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return `$${Number(v).toFixed(2)}`;
}

export default function App() {
  const reduceMotion = useReducedMotion();
  const [status, setStatus] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [trades, setTrades] = useState([]);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setError("");
      const [s, c, t, e] = await Promise.all([
        api.status(),
        api.candidates(),
        api.trades(),
        api.events(),
      ]);
      setStatus(s);
      setCandidates(c.candidates || []);
      setTrades(t.trades || []);
      setEvents(e.events || []);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  const pending = useMemo(
    () => candidates.filter((c) => c.status === "pending"),
    [candidates]
  );
  const openTrades = useMemo(
    () => trades.filter((t) => ["submitted", "filled"].includes(t.status)),
    [trades]
  );

  async function onTrade(id) {
    setBusyId(id);
    try {
      await api.approve(id);
      await refresh();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(id) {
    setBusyId(id);
    try {
      await api.reject(id);
      await refresh();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function onScreen() {
    setBusyId("screen");
    try {
      await api.screen();
      await refresh();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusyId(null);
    }
  }

  const kill = Boolean(status?.risk?.kill_switch);

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <Noise />

      <header className="border-b-2 border-border px-4 md:px-8 py-6 flex flex-col md:flex-row md:items-end md:justify-between gap-6 max-w-[95vw] mx-auto">
        <div>
          <p className="text-xs md:text-sm tracking-widest uppercase text-muted-foreground mb-2">
            skopeftís · premarket sniper desk
          </p>
          <h1 className="uppercase font-bold tracking-tighter leading-[0.8] text-[clamp(3rem,12vw,10rem)]">
            SKOPE<span className="text-accent">.IO</span>
          </h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onScreen}
            disabled={busyId === "screen" || kill}
            className="h-14 px-8 uppercase font-bold tracking-tighter bg-accent text-accent-foreground hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
          >
            {busyId === "screen" ? "Scanning…" : "Run Screen"}
          </button>
          <button
            type="button"
            onClick={refresh}
            className="h-14 px-8 uppercase font-bold tracking-tighter border-2 border-border hover:bg-foreground hover:text-background transition-colors"
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="bg-accent text-accent-foreground border-b-2 border-border">
        {reduceMotion ? (
          <div className="px-4 py-4 uppercase font-bold tracking-tight text-xl md:text-3xl">
            RVOL ≥ 3× · GAP ≥ 20% · VOL ≥ 1M · SIZE 10% · TP +10% · SL −10%
          </div>
        ) : (
          <Marquee speed={80} gradient={false} className="marquee-strip py-4">
            {[
              "PREMARKET GAPS",
              "RVOL 3×–5×",
              "DAY VOLUME 1M+",
              "10% PORTFOLIO SNIPES",
              "TAKE PROFIT +10%",
              "STOP −10%",
              "1-CLICK ALPACA",
              "GEMINI RANKED",
            ].map((label) => (
              <span key={label} className="mx-10 uppercase font-bold tracking-tighter text-2xl md:text-4xl">
                {label} <span aria-hidden="true">✦</span>
              </span>
            ))}
          </Marquee>
        )}
      </div>

      <main className="max-w-[95vw] mx-auto px-4 md:px-8 py-12 md:py-20 space-y-20">
        <section className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border border-2 border-border">
          <Stat label="Pending" value={pending.length} />
          <Stat label="Open Trades" value={openTrades.length} />
          <Stat
            label={kill ? "Kill Switch" : status?.paper ? "Paper" : "Live"}
            value={kill ? "ON" : status?.paper === false ? "LIVE" : "PAPER"}
            danger={kill}
          />
        </section>

        {error ? (
          <div className="border-2 border-accent bg-muted p-6 uppercase font-bold tracking-tight text-accent">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="text-muted-foreground text-xl uppercase tracking-widest">Loading desk…</p>
        ) : null}

        <section>
          <div className="flex items-end justify-between gap-4 mb-8">
            <h2 className="uppercase font-bold tracking-tighter leading-none text-[clamp(2.5rem,8vw,6rem)]">
              Radar
            </h2>
            <span className="text-muted-foreground uppercase tracking-widest text-sm md:text-lg">
              1-click to fire
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border border-2 border-border">
            {pending.length === 0 ? (
              <div className="bg-background p-10 col-span-full text-muted-foreground text-xl md:text-2xl">
                No pending gappers yet. Run screen during the London 08:00–13:00 window.
              </div>
            ) : (
              pending.map((c, idx) => (
                <CandidateCard
                  key={c.id}
                  candidate={c}
                  index={idx}
                  busy={busyId === c.id}
                  disabled={kill}
                  onTrade={() => onTrade(c.id)}
                  onReject={() => onReject(c.id)}
                />
              ))
            )}
          </div>
        </section>

        <section>
          <h2 className="uppercase font-bold tracking-tighter leading-none text-[clamp(2.5rem,8vw,6rem)] mb-8">
            Fills
          </h2>
          <div className="border-2 border-border overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead className="bg-muted uppercase tracking-widest text-xs md:text-sm text-muted-foreground">
                <tr>
                  <th className="p-4">Symbol</th>
                  <th className="p-4">Qty</th>
                  <th className="p-4">Entry</th>
                  <th className="p-4">TP</th>
                  <th className="p-4">SL</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr>
                    <td className="p-6 text-muted-foreground" colSpan={6}>
                      No trades yet.
                    </td>
                  </tr>
                ) : (
                  trades.map((t) => (
                    <tr key={t.id} className="border-t border-border hover:bg-accent hover:text-black transition-colors duration-300">
                      <td className="p-4 font-bold uppercase tracking-tight text-2xl">{t.symbol}</td>
                      <td className="p-4">{fmtNum(t.qty)}</td>
                      <td className="p-4">{fmtMoney(t.entry_price)}</td>
                      <td className="p-4">{fmtMoney(t.take_profit_price)}</td>
                      <td className="p-4">{fmtMoney(t.stop_loss_price)}</td>
                      <td className="p-4 uppercase tracking-widest text-sm">{t.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="uppercase font-bold tracking-tighter leading-none text-[clamp(2.5rem,8vw,6rem)] mb-8">
            Tape
          </h2>
          {reduceMotion ? (
            <div className="space-y-2">
              {events.slice(0, 8).map((e) => (
                <EventPill key={e.id} event={e} />
              ))}
            </div>
          ) : (
            <Marquee speed={40} gradient={false} className="marquee-strip border-2 border-border py-6 bg-muted">
              {(events.length ? events : [{ id: 0, message: "Waiting for bot events", event_type: "idle" }]).map(
                (e) => (
                  <span key={e.id} className="mx-8">
                    <EventPill event={e} />
                  </span>
                )
              )}
            </Marquee>
          )}
        </section>
      </main>

      <footer className="bg-accent text-accent-foreground px-4 md:px-8 py-16">
        <p className="uppercase font-bold tracking-tighter text-[clamp(2rem,6vw,5rem)] leading-none max-w-[95vw]">
          Get in. Take the 10%. Get out. No revenge trading.
        </p>
      </footer>
    </div>
  );
}

function Stat({ label, value, danger }) {
  return (
    <div className={`bg-background p-8 md:p-12 relative overflow-hidden ${danger ? "text-accent" : ""}`}>
      <p className="uppercase tracking-widest text-muted-foreground text-sm md:text-lg mb-4">{label}</p>
      <p className="font-bold tracking-tighter leading-none text-[clamp(3rem,8vw,6rem)]">{value}</p>
      <span
        aria-hidden="true"
        className="absolute -right-2 -bottom-6 text-muted text-[6rem] md:text-[8rem] font-bold leading-none select-none"
      >
        {typeof value === "number" ? value : "!"}
      </span>
    </div>
  );
}

function CandidateCard({ candidate, index, onTrade, onReject, busy, disabled }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.4) }}
      className="group bg-background p-8 md:p-12 hover:bg-accent hover:text-black transition-colors duration-300 relative"
    >
      <span
        aria-hidden="true"
        className="absolute right-4 top-2 text-muted group-hover:text-black/20 font-bold text-[6rem] md:text-[8rem] leading-none"
      >
        {String(index + 1).padStart(2, "0")}
      </span>
      <div className="relative z-10 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="uppercase font-bold tracking-tighter text-4xl md:text-6xl leading-none">
              {candidate.symbol}
            </h3>
            <p className="mt-2 text-muted-foreground group-hover:text-black/70 text-lg md:text-xl">
              {candidate.company || "—"}
            </p>
          </div>
          <div className="text-right">
            <p className="uppercase tracking-widest text-xs md:text-sm text-muted-foreground group-hover:text-black/60">
              Gemini
            </p>
            <p className="font-bold text-4xl md:text-5xl tracking-tighter">
              {candidate.gemini_score != null ? Number(candidate.gemini_score).toFixed(0) : "—"}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm md:text-base">
          <Metric label="Price" value={fmtMoney(candidate.price)} />
          <Metric label="Change" value={fmtPct(candidate.pct_change)} />
          <Metric label="RVOL" value={candidate.rvol != null ? `${Number(candidate.rvol).toFixed(1)}×` : "—"} />
          <Metric label="Day Vol" value={fmtNum(candidate.day_volume)} />
        </div>

        <p className="text-muted-foreground group-hover:text-black/80 text-base md:text-lg leading-tight max-w-2xl">
          {candidate.gemini_rationale || "Awaiting rationale"}
        </p>

        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            disabled={busy || disabled}
            onClick={onTrade}
            className="h-14 px-8 uppercase font-bold tracking-tighter bg-foreground text-background group-hover:bg-black group-hover:text-accent disabled:opacity-50 hover:scale-105 active:scale-95 transition-all"
          >
            {busy ? "Sending…" : "Trade"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onReject}
            className="h-14 px-8 uppercase font-bold tracking-tighter border-2 border-border group-hover:border-black disabled:opacity-50"
          >
            Skip
          </button>
        </div>
      </div>
    </motion.article>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="uppercase tracking-widest text-xs text-muted-foreground group-hover:text-black/60">{label}</p>
      <p className="font-bold tracking-tight text-xl md:text-2xl">{value}</p>
    </div>
  );
}

function EventPill({ event }) {
  return (
    <span className="inline-flex items-center gap-3 uppercase tracking-tight font-bold text-lg md:text-2xl">
      <span className="text-accent">{event.event_type || "event"}</span>
      <span>{event.message}</span>
    </span>
  );
}
