"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";
import {
  PaperJournalEntry,
  PaperState,
  StrategyPerfRow,
  apiGet,
} from "@/lib/api";

function money(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <div className="metric" style={{ color: tone }}>{value}</div>
    </div>
  );
}

export default function PaperTradingPage() {
  const [state, setState] = useState<PaperState | null>(null);
  const [perf, setPerf] = useState<{ overall: Record<string, number>; by_strategy: StrategyPerfRow[] } | null>(null);
  const [journal, setJournal] = useState<PaperJournalEntry[]>([]);
  const [online, setOnline] = useState(true);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [s, p, j] = await Promise.all([
      apiGet<PaperState>("/paper/state"),
      apiGet<{ overall: Record<string, number>; by_strategy: StrategyPerfRow[] }>("/paper/performance"),
      apiGet<{ journal: PaperJournalEntry[] }>("/paper/journal?limit=40"),
    ]);
    setOnline(s.ok);
    if (s.data) setState(s.data);
    if (p.data) setPerf(p.data);
    if (j.data) setJournal(j.data.journal);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  async function control(path: string) {
    setBusy(true);
    try {
      await fetch(`${API_BASE_URL}/api/paper${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: path === "/start" ? JSON.stringify(state?.config ?? {}) : undefined,
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const acc = state?.account;
  const dailyTone = (acc?.realized_daily_pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div>
      <h2 style={{ marginBottom: 12 }}>Paper Trading</h2>
      <div className="notice warn">
        SIMULATED trading on live data — no real orders are ever placed. This is
        a virtual account for practice and validation.
      </div>

      {!online && <div className="notice warn">Backend not reachable.</div>}

      {acc?.halted && (
        <div className="notice warn" style={{ fontWeight: 700 }}>
          ⛔ TRADING HALTED — {acc.halt_reason}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <button className={`mode-btn ${state?.active ? "active" : ""}`} disabled={busy} onClick={() => control("/start")}>
          {state?.active ? "● Active" : "Start"}
        </button>
        {acc?.paused ? (
          <button className="mode-btn" disabled={busy} onClick={() => control("/resume")}>Resume</button>
        ) : (
          <button className="mode-btn" disabled={busy} onClick={() => control("/pause")}>Pause</button>
        )}
        <button className="mode-btn" disabled={busy} onClick={() => control("/stop")}>Stop auto-trade</button>
        <button className="mode-btn" disabled={busy} onClick={() => control("/close-all")}>Close all</button>
        <button className="mode-btn" disabled={busy} onClick={() => control("/reset")}>Reset account</button>
      </div>

      <div className="grid grid-4">
        <Metric label="Balance" value={money(acc?.balance)} />
        <Metric label="Equity" value={money(acc?.equity)} />
        <Metric label="Today's P&L" value={money(acc?.realized_daily_pnl)} tone={dailyTone} />
        <Metric label="Max drawdown" value={acc ? `${(acc.max_drawdown_pct * 100).toFixed(2)}%` : "—"} />
      </div>

      <div className="section-title">Open Positions</div>
      <div className="card">
        {(state?.positions ?? []).length === 0 && <div className="muted">No open positions.</div>}
        {(state?.positions ?? []).map((p) => (
          <div key={p.id} className="row">
            <span>
              {p.direction.toUpperCase()} {p.lots.toFixed(2)} lots · {p.strategy_name}
            </span>
            <span className="muted">
              entry {p.entry_price} · now {p.current_price ?? "—"} · SL {p.stop_loss ?? "—"} · TP {p.take_profit ?? "—"}
            </span>
            <span style={{ color: (p.unrealized_pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
              {money(p.unrealized_pnl)}
              <button className="tf-tab" style={{ marginLeft: 8 }} onClick={() => control(`/close/${p.id}`)}>
                Close
              </button>
            </span>
          </div>
        ))}
      </div>

      <div className="section-title">Strategy Performance</div>
      <div className="card">
        {(perf?.by_strategy ?? []).length === 0 && <div className="muted">No closed trades yet.</div>}
        {(perf?.by_strategy ?? []).map((r) => (
          <div key={r.strategy_key} className="row">
            <span><strong>{r.strategy_name}</strong></span>
            <span className="muted">
              {r.num_trades} trades · win {(r.win_rate * 100).toFixed(0)}% · PF {r.profit_factor ?? "∞/—"} · exp {r.expectancy}
            </span>
            <span style={{ color: r.net_pnl >= 0 ? "var(--green)" : "var(--red)" }}>{money(r.net_pnl)}</span>
          </div>
        ))}
      </div>

      <div className="section-title">Journal (signal → trade)</div>
      <div className="card" style={{ maxHeight: 320, overflowY: "auto" }}>
        {journal.length === 0 && <div className="muted">No activity yet.</div>}
        {journal.map((e, i) => {
          const color =
            e.kind === "trade_opened" ? "var(--green)"
            : e.kind === "rejected" ? "var(--warn)"
            : e.kind === "trade_closed" ? "var(--text)"
            : "var(--text-dim)";
          return (
            <div key={i} className="row" style={{ fontSize: 12 }}>
              <span className="badge gray">{e.kind}</span>
              <span style={{ color, flex: 1, textAlign: "left", paddingLeft: 10 }}>{e.message}</span>
            </div>
          );
        })}
      </div>

      <div className="disclaimer">
        Phase 5 — paper trading. All fills are simulated with modelled spread,
        slippage, latency and commission. No real orders are possible. Past
        performance does not guarantee future results.
      </div>
    </div>
  );
}
