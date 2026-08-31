// Runtime configuration derived from environment variables.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

export const SYMBOL = "XAUUSD";

export const TIMEFRAMES = ["1M", "5M", "15M", "30M", "1H", "4H", "1D"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];

// UI label -> backend timeframe code (e.g. "15M" -> "15m").
export function toApiTimeframe(tf: Timeframe): string {
  return tf.toLowerCase();
}

// Seconds per timeframe (mirrors the backend), used to bucket live ticks.
export const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  "1M": 60,
  "5M": 300,
  "15M": 900,
  "30M": 1800,
  "1H": 3600,
  "4H": 14400,
  "1D": 86400,
};
