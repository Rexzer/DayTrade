"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

function fmtTime(epoch?: number): string {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toISOString().replace("T", " ").slice(0, 19);
}

export default function JournalPage() {
  const [trades, setTrades] = useState<any[]>([]);
  const [observations, setObservations] = useState<any[]>([]);

  useEffect(() => {
    apiGet<any>("/paper/trades?limit=200").then((r) => setTrades(r.data?.trades ?? []));
    apiGet<any>("/analytics/journal").then((r) => setObservations(r.data?.observations ?? []));
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Trade Journal</h2>
      <div className="notice">
        Every recorded (paper) trade with its strategy, regime, entry/exit and
        reason. Behavioural observations are shown neutrally below.
      </div>

      <div className="section-title">Observations</div>
      <div className="card" style={{ marginBottom: 16 }}>
        {observations.length === 0 && <div className="muted">No observations yet.</div>}
        {observations.map((ob) => (
          <div key={ob.code} style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600 }}>{ob.title}</div>
            <div className="muted" style={{ fontSize: 12 }}>{ob.detail}</div>
          </div>
        ))}
      </div>

      <div className="section-title">Trades ({trades.length})</div>
      <div className="card" style={{ maxHeight: 500, overflowY: "auto" }}>
        {trades.length === 0 && <div className="muted">No trades recorded yet.</div>}
        {trades.map((t) => (
          <div key={t.id} className="row" style={{ fontSize: 12 }}>
            <span>
              {fmtTime(t.opened_epoch)} · {String(t.direction).toUpperCase()} {t.strategy_name}
            </span>
            <span className="muted">
              {t.entry_price} → {t.exit_price} · {t.regime ?? "—"} · {t.exit_reason}
            </span>
            <span style={{ color: t.pnl >= 0 ? "var(--green)" : "var(--red)" }}>{t.pnl}</span>
          </div>
        ))}
      </div>

      <div className="disclaimer">
        Phase 8 — trade journal &amp; intelligence. Observations are neutral
        reflections, not advice. Past performance does not guarantee future
        results.
      </div>
    </div>
  );
}
