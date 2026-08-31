"use client";

import { XauHeader } from "@/components/XauHeader";
import { MarketOverview } from "@/components/MarketOverview";
import { ChartArea } from "@/components/ChartArea";
import { MultiTimeframePanel } from "@/components/MultiTimeframePanel";
import { StrategyPanel } from "@/components/StrategyPanel";
import { AccountPanel } from "@/components/AccountPanel";
import { NewsPanel } from "@/components/NewsPanel";
import { ModeSelector } from "@/components/ModeSelector";
import { useDashboardData } from "@/lib/useDashboardData";
import { useState } from "react";

export default function DashboardPage() {
  const data = useDashboardData();
  const [timeframe, setTimeframe] = useState("15M");
  const connected = data.snapshot?.connected ?? false;

  return (
    <div>
      {!data.backendOnline && !data.loading && (
        <div className="notice warn">
          Backend API is not reachable. Start it with{" "}
          <code>uvicorn backend.app.main:app</code> (see README.txt). The
          dashboard is showing honest disconnected states.
        </div>
      )}

      <XauHeader snapshot={data.snapshot} />

      <div style={{ marginBottom: 16 }}>
        <ModeSelector modes={data.modes} />
      </div>

      <MarketOverview snapshot={data.snapshot} timeframe={timeframe} />

      <div className="section-title">XAUUSD Chart</div>
      <ChartArea connected={connected} onTimeframeChange={(tf) => setTimeframe(tf)} />

      <div className="section-title">Analysis</div>
      <MultiTimeframePanel />

      <div className="section-title">Overview</div>
      <div className="grid grid-2">
        <StrategyPanel data={data.strategies} />
        <AccountPanel account={data.account} />
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <NewsPanel data={data.news} />
        <div className="card">
          <h3>Active Signal</h3>
          <div className="muted">
            No active signal. The strategy &amp; signal engine is added in
            Phase 2 — every signal will show its full reasoning, entry zone,
            stop-loss, take-profit, risk/reward and invalidation level.
          </div>
        </div>
      </div>

      <div className="disclaimer">
        Phase 1 — analysis only. Live trading is NOT implemented. This platform
        does not guarantee profits; every strategy is a hypothesis requiring
        historical testing and validation. Past performance does not guarantee
        future results.
      </div>
    </div>
  );
}
