// Runtime configuration derived from environment variables.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

export const SYMBOL = "XAUUSD";

export const TIMEFRAMES = ["1M", "5M", "15M", "30M", "1H", "4H", "1D"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];
