"use client";

import { useEffect, useState } from "react";
import { StrategiesListResponse, StrategyItem, apiGet } from "@/lib/api";

const LEVEL_BADGE: Record<string, string> = {
  NO_SETUP: "gray",
  WATCH: "gold",
  POTENTIAL_SETUP: "warn",
  CONFIRMED_SETUP: "green",
};

function StrategyRow({ s }: { s: StrategyItem }) {
  const [open, setOpen] = useState(false);
  const sig = s.current_signal;
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{ display: "flex", justifyContent: "space-between", cursor: "pointer" }}
        onClick={() => setOpen((o) => !o)}
      >
        <div>
          <strong>{s.name}</strong>{" "}
          {!s.is_builtin && <span className="badge gold">Custom</span>}
          <div className="muted" style={{ fontSize: 12 }}>
            {s.description}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <span className={`badge ${LEVEL_BADGE[sig?.level_name ?? "NO_SETUP"] ?? "gray"}`}>
            {(sig?.level_name ?? "NO_SETUP").replace(/_/g, " ")}
          </span>
          {sig?.confidence_score != null && (
            <div className="muted" style={{ fontSize: 12 }}>
              score {sig.confidence_score}/100
            </div>
          )}
        </div>
      </div>

      {open && (
        <div style={{ marginTop: 12 }}>
          <div className="row">
            <span className="label">Timeframes</span>
            <span>{s.suitable_timeframes.join(", ") || "—"}</span>
          </div>
          <div className="row">
            <span className="label">Suitable regimes</span>
            <span>{s.suitable_regimes.map((r) => r.replace(/_/g, " ")).join(", ") || "—"}</span>
          </div>
          <div className="row">
            <span className="label">Indicators</span>
            <span>{s.indicators.join(", ") || "—"}</span>
          </div>
          <div style={{ marginTop: 8 }}>
            <div className="section-title" style={{ margin: "8px 0 4px" }}>
              Entry conditions
            </div>
            {s.entry_conditions.map((c) => (
              <div key={c} className="muted" style={{ fontSize: 12 }}>
                • {c}
              </div>
            ))}
          </div>
          {s.confirmation_conditions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="section-title" style={{ margin: "8px 0 4px" }}>
                Confirmations
              </div>
              {s.confirmation_conditions.map((c) => (
                <div key={c} className="muted" style={{ fontSize: 12 }}>
                  • {c}
                </div>
              ))}
            </div>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <span className="label">Stop-loss</span>
            <span style={{ maxWidth: 380, textAlign: "right" }}>{s.stop_loss_logic}</span>
          </div>
          <div className="row">
            <span className="label">Take-profit</span>
            <span style={{ maxWidth: 380, textAlign: "right" }}>{s.take_profit_logic}</span>
          </div>
          <div className="row">
            <span className="label">Invalidation</span>
            <span style={{ maxWidth: 380, textAlign: "right" }}>{s.invalidation_logic}</span>
          </div>
          <div className="row">
            <span className="label">Historical performance</span>
            <span className="muted">Available after backtesting (Phase 4).</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function StrategiesPage() {
  const [data, setData] = useState<StrategiesListResponse | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const res = await apiGet<StrategiesListResponse>("/strategies");
      if (cancelled) return;
      setData(res.data);
      setOnline(res.ok);
    }
    load();
    const id = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Strategy Library</h2>
      {!online && <div className="notice warn">Backend not reachable.</div>}
      {data && !data.signals_allowed && (
        <div className="notice warn">
          Signal generation is halted (market data stale/disconnected). Statuses
          below may be inactive.
        </div>
      )}
      <div className="disclaimer" style={{ marginTop: 0, marginBottom: 16, borderTop: "none" }}>
        No strategy is guaranteed to be profitable. Each is a hypothesis to be
        backtested and validated. Scores are transparent rubrics, not
        probabilities of profit.
      </div>
      {(data?.strategies ?? []).map((s) => (
        <StrategyRow key={s.key} s={s} />
      ))}
      {data && data.strategies.length === 0 && (
        <div className="muted">No strategies loaded.</div>
      )}
    </div>
  );
}
