"use client";

import { useEffect, useState } from "react";
import { MtfRow, apiGet } from "@/lib/api";

// Multi-timeframe analysis panel. Populated from /strategies/analysis/mtf.
// Shows UNKNOWN/no-data honestly when a timeframe lacks history.
const TFS = ["4H", "1H", "15M", "5M"] as const;

function label(v: string): string {
  return (v ?? "unknown").replace(/_/g, " ").toUpperCase();
}

function trendClass(v: string): string {
  if (v === "bullish") return "green";
  if (v === "bearish") return "red";
  return "gray";
}

export function MultiTimeframePanel() {
  const [rows, setRows] = useState<Record<string, MtfRow>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const res = await apiGet<{ timeframes: MtfRow[] }>("/strategies/analysis/mtf");
      if (cancelled || !res.ok || !res.data) return;
      const map: Record<string, MtfRow> = {};
      for (const r of res.data.timeframes) map[r.timeframe] = r;
      setRows(map);
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="card">
      <h3>Multi-Timeframe Analysis</h3>
      <div className="mtf-grid">
        {TFS.map((tf) => {
          const r = rows[tf];
          return (
            <div className="mtf-cell" key={tf}>
              <div className="mtf-tf">{tf}</div>
              <div className="row">
                <span className="label">Trend</span>
                <span className={`badge ${trendClass(r?.trend ?? "unknown")}`}>
                  {label(r?.trend ?? "unknown")}
                </span>
              </div>
              <div className="row">
                <span className="label">Momentum</span>
                <span>{label(r?.momentum ?? "unknown")}</span>
              </div>
              <div className="row">
                <span className="label">Structure</span>
                <span>{label(r?.structure ?? "unknown")}</span>
              </div>
              <div className="row">
                <span className="label">State</span>
                <span>{label(r?.signal_state ?? "no_data")}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
