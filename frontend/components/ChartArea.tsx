"use client";

import { useEffect, useRef, useState } from "react";
import {
  TIMEFRAMES,
  Timeframe,
  TIMEFRAME_SECONDS,
  toApiTimeframe,
} from "@/lib/config";
import { CandlesResponse, apiGet } from "@/lib/api";
import { LiveTick } from "@/lib/useMarketStream";

interface Bar {
  time: number; // seconds (UTC) — lightweight-charts uses seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

// Renders the XAUUSD candlestick chart from the live market-data feed.
// Candles are loaded from /market/candles for the selected timeframe and the
// forming candle is updated in real time from incoming ticks. When no feed is
// connected it shows a clear placeholder instead of fabricated candles.
export function ChartArea({
  connected,
  lastTick,
  onTimeframeChange,
}: {
  connected: boolean;
  lastTick: LiveTick | null;
  onTimeframeChange?: (tf: Timeframe) => void;
}) {
  const [active, setActive] = useState<Timeframe>("15M");
  const [barCount, setBarCount] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const lastBarRef = useRef<Bar | null>(null);

  // Initialise the chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    (async () => {
      try {
        const mod = await import("lightweight-charts");
        if (disposed || !containerRef.current || chartRef.current) return;
        const chart = mod.createChart(containerRef.current, {
          layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
          grid: {
            vertLines: { color: "#2a3142" },
            horzLines: { color: "#2a3142" },
          },
          timeScale: { timeVisible: true, secondsVisible: false },
          crosshair: { mode: 0 },
          autoSize: true,
        });
        chartRef.current = chart;
        seriesRef.current = chart.addCandlestickSeries({
          upColor: "#26a69a",
          downColor: "#ef5350",
          wickUpColor: "#26a69a",
          wickDownColor: "#ef5350",
          borderVisible: false,
        });
      } catch {
        // library missing (offline install) — placeholder stays visible
      }
    })();
    return () => {
      disposed = true;
    };
  }, []);

  // Load candles whenever the timeframe changes or the feed connects.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const res = await apiGet<CandlesResponse>(
        `/market/candles?timeframe=${toApiTimeframe(active)}&limit=300`
      );
      if (cancelled || !res.ok || !res.data) {
        setBarCount(0);
        return;
      }
      const bars: Bar[] = res.data.candles.map((c) => ({
        time: Math.floor(c.open_time_epoch),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      setBarCount(bars.length);
      lastBarRef.current = bars.length ? bars[bars.length - 1] : null;
      if (seriesRef.current) {
        seriesRef.current.setData(bars);
      }
    }
    load();
    const id = setInterval(load, 15000); // periodic resync
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [active, connected]);

  // Update the forming candle in real time from ticks.
  useEffect(() => {
    if (!lastTick || !seriesRef.current) return;
    const price = lastTick.price ?? lastTick.last ?? lastTick.bid;
    if (price == null) return;
    const dur = TIMEFRAME_SECONDS[active];
    const bucket = Math.floor(lastTick.timestamp_epoch / dur) * dur;
    const prev = lastBarRef.current;
    let bar: Bar;
    if (prev && prev.time === bucket) {
      bar = {
        time: bucket,
        open: prev.open,
        high: Math.max(prev.high, price),
        low: Math.min(prev.low, price),
        close: price,
      };
    } else {
      bar = { time: bucket, open: price, high: price, low: price, close: price };
    }
    lastBarRef.current = bar;
    try {
      seriesRef.current.update(bar);
    } catch {
      // out-of-order guard from the charting lib — ignore
    }
  }, [lastTick, active]);

  const showPlaceholder = !connected && barCount === 0;

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
        {showPlaceholder && (
          <div className="chart-placeholder">
            <div style={{ fontSize: 32 }}>📈</div>
            <div style={{ fontWeight: 600 }}>XAUUSD chart</div>
            <div className="muted">
              No market-data provider connected. Set MARKET_DATA_PROVIDER to
              connect a feed.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
