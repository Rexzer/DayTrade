"use client";

import { ModesResponse } from "@/lib/api";

const LABELS: Record<string, string> = {
  analysis_only: "Analysis Only",
  paper_trading: "Paper Trading",
  live_trading: "Live Trading",
};

export function ModeSelector({ modes }: { modes: ModesResponse | null }) {
  const list = modes?.modes ?? [
    { mode: "analysis_only", availability: "enabled", active: true, reason: null },
    { mode: "paper_trading", availability: "locked", active: false, reason: null },
    { mode: "live_trading", availability: "locked", active: false, reason: null },
  ];

  return (
    <div>
      <div className="mode-selector">
        {list.map((m) => {
          const locked = m.availability === "locked";
          return (
            <button
              key={m.mode}
              className={`mode-btn ${m.active ? "active" : ""} ${
                locked ? "locked" : ""
              }`}
              disabled={locked}
              title={m.reason ?? undefined}
            >
              {m.active && <span className="status-dot" />}
              {LABELS[m.mode] ?? m.mode}
              {locked && " 🔒"}
            </button>
          );
        })}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        Analysis Only is active. Paper Trading unlocks in Phase 4 and Live
        Trading in Phase 6 (behind explicit confirmations).
      </div>
    </div>
  );
}
