// Thin API client for the backend. All calls fail gracefully so the UI can
// render honest "disconnected" states instead of crashing when the backend
// is unavailable.
import { API_BASE_URL } from "./config";

export interface ApiResult<T> {
  ok: boolean;
  data: T | null;
  error: string | null;
}

export async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_BASE_URL}/api${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) {
      return { ok: false, data: null, error: `HTTP ${res.status}` };
    }
    const data = (await res.json()) as T;
    return { ok: true, data, error: null };
  } catch (err) {
    return {
      ok: false,
      data: null,
      error: err instanceof Error ? err.message : "network error",
    };
  }
}

// ---- Response shapes (Phase 1) ----
export interface MarketSnapshot {
  symbol: string;
  connected: boolean;
  bid: number | null;
  ask: number | null;
  last: number | null;
  spread: number | null;
  source: string | null;
  connection_status: string;
  data_status: string;
}

export interface AccountInfo {
  connected: boolean;
  status: string;
  balance: number | null;
  equity: number | null;
  margin: number | null;
  free_margin: number | null;
  open_positions: number;
  today_pnl: number | null;
  daily_drawdown: number | null;
}

export interface ModeInfo {
  mode: string;
  availability: string;
  active: boolean;
  reason: string | null;
}

export interface ModesResponse {
  current: string;
  live_trading_active: boolean;
  modes: ModeInfo[];
}

export interface StrategiesResponse {
  connected: boolean;
  active: Array<Record<string, unknown>>;
  planned: Array<{ key: string; name: string }>;
  note: string;
}

export interface NewsResponse {
  connected: boolean;
  next_high_impact_event: unknown | null;
  status: string;
}
