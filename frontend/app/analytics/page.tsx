"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

function BreakdownTable({ title, data }: { title: string; data: any }) {
  const rows = data?.rows ?? [];
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <h3>{title}</h3>
      {rows.length === 0 && <div className="muted">No data.</div>}
      {rows.map((r: any) => (
        <div key={r.group} className="row" style={{ fontSize: 12 }}>
          <span>{r.group}</span>
          <span className="muted">
            {r.num_trades} trades · win {Math.round((r.win_rate || 0) * 100)}% · PF{" "}
            {r.profit_factor ?? (r.profit_factor_infinite ? "∞" : "—")}
          </span>
          <span style={{ color: r.net_pnl >= 0 ? "var(--green)" : "var(--red)" }}>{r.net_pnl}</span>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const [perf, setPerf] = useState<any>(null);
  const [journal, setJournal] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);

  useEffect(() => {
    apiGet<any>("/analytics/performance").then((r) => setPerf(r.data));
    apiGet<any>("/analytics/journal").then((r) => setJournal(r.data));
    apiGet<any>("/analytics/comparison").then((r) => setComparison(r.data));
    apiGet<any>("/analytics/signals/history").then((r) => setHistory(r.data));
  }, []);

  const o = perf?.overall ?? {};
  const M = (label: string, value: any) => (
    <div className="card">
      <h3>{label}</h3>
      <div className="metric na" style={{ fontSize: 18 }}>{value ?? "—"}</div>
    </div>
  );

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Performance Analytics</h2>
      <div className="disclaimer" style={{ marginTop: 0, borderTop: "none" }}>
        Historical / simulated measurements only. No result guarantees future
        performance.
      </div>

      <div className="grid grid-4">
        {M("Trades", o.num_trades)}
        {M("Win rate", o.win_rate != null ? `${Math.round(o.win_rate * 100)}%` : "—")}
        {M("Profit factor", o.profit_factor ?? (o.profit_factor_infinite ? "∞" : "—"))}
        {M("Expectancy", o.expectancy)}
        {M("Net P&L", o.net_pnl)}
        {M("Avg win", o.average_win)}
        {M("Avg loss", o.average_loss)}
        {M(
          "Avg hold",
          o.average_holding_seconds != null ? `${Math.round(o.average_holding_seconds / 60)}m` : "—"
        )}
      </div>

      <div className="section-title">Breakdowns</div>
      <div className="grid grid-2">
        <BreakdownTable title="By strategy" data={perf?.by_strategy} />
        <BreakdownTable title="By direction" data={perf?.by_direction} />
        <BreakdownTable title="By market regime" data={perf?.by_regime} />
        <BreakdownTable title="By session" data={perf?.by_session} />
        <BreakdownTable title="By exit reason" data={perf?.by_exit_reason} />
        <BreakdownTable title="By month" data={perf?.by_month} />
      </div>

      <div className="section-title">Strategy Comparison</div>
      <div className="card">
        <div className="row" style={{ fontWeight: 600, fontSize: 12 }}>
          <span>Strategy</span>
          <span>Backtest OOS</span>
          <span>Paper</span>
          <span>Live</span>
        </div>
        {(comparison?.rows ?? []).map((r: any) => (
          <div key={r.strategy_key} className="row" style={{ fontSize: 12 }}>
            <span>{r.strategy_name}</span>
            <span>{r.backtest_oos?.net_pnl ?? "—"}</span>
            <span>{r.paper?.net_pnl ?? "—"}</span>
            <span>{r.live?.net_pnl ?? "—"}</span>
          </div>
        ))}
        <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>{comparison?.note}</div>
      </div>

      <div className="section-title">Journal Intelligence</div>
      <div className="card">
        {(journal?.observations ?? []).length === 0 && (
          <div className="muted">No behavioural observations yet.</div>
        )}
        {(journal?.observations ?? []).map((ob: any) => (
          <div key={ob.code} style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600 }}>{ob.title}</div>
            <div className="muted" style={{ fontSize: 12 }}>{ob.detail}</div>
          </div>
        ))}
        <div className="muted" style={{ fontSize: 11 }}>
          Observations are presented neutrally, for reflection — not as advice.
        </div>
      </div>

      <div className="section-title">Signal History</div>
      <div className="card" style={{ maxHeight: 300, overflowY: "auto" }}>
        {(history?.events ?? []).length === 0 && <div className="muted">No signal transitions recorded yet.</div>}
        {(history?.events ?? []).map((e: any, i: number) => (
          <div key={i} className="row" style={{ fontSize: 12 }}>
            <span className="badge gray">{e.transition}</span>
            <span style={{ flex: 1, textAlign: "left", paddingLeft: 8 }}>
              {e.strategy_name}: {e.from_level_name} → {e.to_level_name}
            </span>
            <span className="muted">{e.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
