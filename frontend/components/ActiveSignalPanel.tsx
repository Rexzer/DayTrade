"use client";

import { useEffect, useState } from "react";
import { SignalDTO, SignalsResponse, apiGet } from "@/lib/api";

const LEVEL_BADGE: Record<string, string> = {
  NO_SETUP: "gray",
  WATCH: "gold",
  POTENTIAL_SETUP: "warn",
  CONFIRMED_SETUP: "green",
};

function SignalCard({ s }: { s: SignalDTO }) {
  const dir = (s.direction ?? "").toUpperCase();
  return (
    <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>
          {s.strategy_name ?? s.strategy_key} {dir && `— ${dir}`}
        </strong>
        <span className={`badge ${LEVEL_BADGE[s.level_name] ?? "gray"}`}>
          {s.level_name.replace(/_/g, " ")}
        </span>
      </div>

      {s.entry_zone && (
        <div className="row">
          <span className="label">Entry</span>
          <span>
            {s.entry_zone[0]}–{s.entry_zone[1]}
          </span>
        </div>
      )}
      {s.stop_loss != null && (
        <div className="row">
          <span className="label">Stop</span>
          <span>{s.stop_loss}</span>
        </div>
      )}
      {s.take_profits?.length > 0 && (
        <div className="row">
          <span className="label">Targets</span>
          <span>{s.take_profits.join(" / ")}</span>
        </div>
      )}
      {s.risk_reward != null && (
        <div className="row">
          <span className="label">Risk/Reward</span>
          <span>1:{s.risk_reward}</span>
        </div>
      )}
      {s.confidence_score != null && (
        <div className="row">
          <span className="label">Score (rubric, not probability)</span>
          <span>{s.confidence_score}/100</span>
        </div>
      )}

      {s.confirmations?.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {s.confirmations.map((c) => (
            <div key={c} className="muted" style={{ fontSize: 12 }}>
              ✓ {c}
            </div>
          ))}
        </div>
      )}
      {s.missing_confirmations?.length > 0 && (
        <div style={{ marginTop: 4 }}>
          {s.missing_confirmations.map((c) => (
            <div key={c} style={{ fontSize: 12, color: "var(--warn)" }}>
              ⚠ waiting: {c}
            </div>
          ))}
        </div>
      )}
      {s.invalidation && (
        <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Invalidation: {s.invalidation}
        </div>
      )}
      {s.notes && (
        <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          {s.notes}
        </div>
      )}
    </div>
  );
}

// Shows the current best signals with FULL transparent reasoning. Respects the
// safety gate: if signals are halted (stale data) it says so and shows nothing.
export function ActiveSignalPanel() {
  const [data, setData] = useState<SignalsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const res = await apiGet<SignalsResponse>("/strategies/signals");
      if (!cancelled) setData(res.data);
    }
    load();
    const id = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const allowed = data?.signals_allowed ?? false;
  const top = (data?.signals ?? []).filter((s) => s.level >= 1).slice(0, 3);

  return (
    <div className="card">
      <h3>Active Signals</h3>
      {!allowed && (
        <div className="muted">
          {data?.reason ??
            "No signals. The strategy engine halts when market data is stale/disconnected."}
        </div>
      )}
      {allowed && top.length === 0 && (
        <div className="muted">No active setups right now. Strategies are watching.</div>
      )}
      {allowed && top.map((s) => <SignalCard key={s.strategy_key} s={s} />)}
    </div>
  );
}
