"use client";

import { XauHeader } from "@/components/XauHeader";
import { MarketOverview } from "@/components/MarketOverview";
import { ChartArea } from "@/components/ChartArea";
import { MultiTimeframePanel } from "@/components/MultiTimeframePanel";
import { AccountPanel } from "@/components/AccountPanel";
import { NewsPanel } from "@/components/NewsPanel";
import { ModeSelector } from "@/components/ModeSelector";
import { DataSourcePanel } from "@/components/DataSourcePanel";
import { ActiveSignalPanel } from "@/components/ActiveSignalPanel";
import { useDashboardData } from "@/lib/useDashboardData";
import { useMarketStream } from "@/lib/useMarketStream";
import { MarketSnapshot } from "@/lib/api";
import { useState } from "react";

export default function DashboardPage() {
  const data = useDashboardData();
  const market = useMarketStream();
  const [timeframe, setTimeframe] = useState("15M");

  const connected = market.status?.connected ?? false;
  const dataStatus = market.health?.status ?? "disconnected";
  const isStale = dataStatus === "stale";

  // Build a snapshot for the header/overview from the live stream (falling
  // back to the periodic REST snapshot before the socket delivers a tick).
  const snapshot: MarketSnapshot = {
    symbol: "XAUUSD",
    connected,
    bid: market.lastTick?.bid ?? null,
    ask: market.lastTick?.ask ?? null,
    last: market.lastTick?.last ?? market.lastTick?.price ?? null,
    spread: market.lastTick?.spread ?? null,
    source: market.status?.source ?? null,
    connection_status: connected ? "connected" : "disconnected",
    data_status: dataStatus,
  };

  return (
    <div>
      {!data.backendOnline && !data.loading && (
        <div className="notice warn">
          Backend API is not reachable. Start it with{" "}
          <code>uvicorn backend.app.main:app</code> (see README.txt). The
          dashboard is showing honest disconnected states.
        </div>
      )}

      {isStale && (
        <div className="notice warn" style={{ fontWeight: 700 }}>
          ⚠ MARKET DATA STALE — live signal generation is halted until fresh
          data resumes. Displayed prices may be out of date.
        </div>
      )}

      <XauHeader snapshot={snapshot} />

      <div style={{ marginBottom: 16 }}>
        <ModeSelector modes={data.modes} />
      </div>

      <MarketOverview snapshot={snapshot} timeframe={timeframe} />

      <div className="section-title">XAUUSD Chart</div>
      <ChartArea
        connected={connected}
        lastTick={market.lastTick}
        onTimeframeChange={(tf) => setTimeframe(tf)}
      />

      <div className="section-title">Analysis</div>
      <MultiTimeframePanel />

      <div className="section-title">Overview</div>
      <div className="grid grid-2">
        <DataSourcePanel status={market.status} health={market.health} />
        <AccountPanel account={data.account} />
      </div>

      <div className="section-title">Signals</div>
      <div className="grid grid-2">
        <ActiveSignalPanel />
        <NewsPanel data={data.news} />
      </div>

      <div className="disclaimer">
        Phase 3 — real-time data + strategy/signal engine; analysis only. Live
        trading is NOT implemented and no orders can be sent. Signals are
        explainable classifications (never executed trades); scores are
        transparent rubrics, not probabilities of profit. Past performance does
        not guarantee future results.
      </div>
    </div>
  );
}
