"use client";

import { useEffect, useRef, useState } from "react";
import { WS_BASE_URL } from "./config";
import { FeedHealth, MarketStatus } from "./api";

export interface LiveTick {
  symbol: string;
  timestamp_epoch: number;
  bid: number | null;
  ask: number | null;
  last: number | null;
  spread: number | null;
  price: number | null;
  source: string | null;
}

export interface ClosedCandleEvent {
  timeframe: string;
  candle: {
    open_time_epoch: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number | null;
  };
}

export interface MarketStream {
  status: MarketStatus | null;
  health: FeedHealth | null;
  lastTick: LiveTick | null;
  lastClosed: ClosedCandleEvent | null;
  connectionState: string;
  wsConnected: boolean;
}

// Connects to /ws/market and exposes the latest tick, health and status.
// Reconnects automatically with a short backoff. Never fabricates data — if
// the socket is down, fields stay null and the UI shows disconnected states.
export function useMarketStream(): MarketStream {
  const [stream, setStream] = useState<MarketStream>({
    status: null,
    health: null,
    lastTick: null,
    lastClosed: null,
    connectionState: "disconnected",
    wsConnected: false,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let closedByUs = false;

    function connect() {
      let ws: WebSocket;
      try {
        ws = new WebSocket(`${WS_BASE_URL}/ws/market`);
      } catch {
        scheduleRetry();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        setStream((s) => ({ ...s, wsConnected: true }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          setStream((s) => {
            const next = { ...s };
            switch (msg.type) {
              case "status":
                next.status = msg as MarketStatus;
                next.connectionState =
                  msg.connection_state ?? s.connectionState;
                if (msg.health) next.health = msg.health;
                break;
              case "tick":
                next.lastTick = msg.tick;
                next.health = msg.health ?? s.health;
                next.connectionState =
                  msg.connection_state ?? s.connectionState;
                break;
              case "candle_closed":
                next.lastClosed = msg as ClosedCandleEvent;
                break;
              case "health":
                next.health = msg.health ?? s.health;
                break;
            }
            return next;
          });
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setStream((s) => ({ ...s, wsConnected: false }));
        if (!closedByUs) scheduleRetry();
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function scheduleRetry() {
      if (retryRef.current) clearTimeout(retryRef.current);
      retryRef.current = setTimeout(connect, 3000);
    }

    connect();
    return () => {
      closedByUs = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  return stream;
}
