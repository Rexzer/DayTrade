"use client";

import { useEffect, useRef, useState } from "react";
import { TIMEFRAMES, Timeframe } from "@/lib/config";

// The XAUUSD chart container. It uses TradingView Lightweight Charts when a
// data feed exists. In Phase 1 there is no feed, so it renders a clear
// placeholder rather than fake candles. The lightweight-charts library is
// imported dynamically so the placeholder still works if data is absent.
export function ChartArea({
  connected,
  onTimeframeChange,
}: {
  connected: boolean;
  onTimeframeChange?: (tf: Timeframe) => void;
}) {
  const [active, setActive] = useState<Timeframe>("15M");
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // When a real feed is connected (Phase 2+), initialise the chart here.
    // Kept intentionally inert in Phase 1 to avoid presenting empty/fake data.
    if (!connected || !containerRef.current) return;
    let disposed = false;
    (async () => {
      try {
        const mod = await import("lightweight-charts");
        if (disposed || !containerRef.current) return;
        const chart = mod.createChart(containerRef.current, {
          layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
          grid: {
            vertLines: { color: "#2a3142" },
            horzLines: { color: "#2a3142" },
          },
          autoSize: true,
        });
        // Candlestick series is populated by the market-data layer in Phase 2.
        chart.addCandlestickSeries();
      } catch {
        // Library not installed / feed absent — placeholder remains visible.
      }
    })();
    return () => {
      disposed = true;
    };
  }, [connected, active]);

  return (
    <div className="card">
      <div className="tf-tabs">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            className={`tf-tab ${active === tf ? "active" : ""}`}
            onClick={() => {
              setActive(tf);
              onTimeframeChange?.(tf);
            }}
          >
            {tf}
          </button>
        ))}
      </div>
      <div className="chart-wrap">
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
        {!connected && (
          <div className="chart-placeholder">
            <div style={{ fontSize: 32 }}>📈</div>
            <div style={{ fontWeight: 600 }}>XAUUSD chart</div>
            <div className="muted">
              Waiting for the market-data layer (Phase 2).
            </div>
            <div className="muted">
              Candlesticks, crosshair, zoom &amp; pan activate once a provider
              is connected.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
