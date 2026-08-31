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

// ---- Market data (Phase 2) ----
export interface FeedHealth {
  status: string; // live | delayed | stale | disconnected
  last_update_epoch: number | null;
  age_seconds: number | null;
  signals_allowed: boolean;
  source: string | null;
}

export interface MarketStatus {
  symbol: string;
  broker_symbol: string;
  source: string;
  provider_kind: string;
  connected: boolean;
  connection_state: string;
  health: FeedHealth;
  last_update_epoch: number | null;
  simulated: boolean;
}

export interface CandleDTO {
  timeframe: string;
  open_time_epoch: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface CandlesResponse {
  symbol: string;
  timeframe: string;
  connected: boolean;
  source: string;
  simulated: boolean;
  candles: CandleDTO[];
}

export interface SymbolsResponse {
  canonical: string;
  active_broker_symbol: string;
  known_aliases: string[];
}

// ---- Strategy & signal engine (Phase 3) ----
export interface SignalDTO {
  strategy_key: string;
  strategy_name?: string;
  level: number;
  level_name: string;
  regime: string;
  timeframe: string | null;
  direction: string | null;
  entry_zone: number[] | null;
  stop_loss: number | null;
  take_profits: number[];
  risk_reward: number | null;
  confirmations: string[];
  missing_confirmations: string[];
  invalidation: string | null;
  confidence_score: number | null;
  notes: string | null;
}

export interface SignalsResponse {
  signals_allowed: boolean;
  reason: string;
  regime: Record<string, unknown> | null;
  signals: SignalDTO[];
}

export interface StrategyItem {
  key: string;
  name: string;
  description: string;
  suitable_timeframes: string[];
  suitable_regimes: string[];
  indicators: string[];
  entry_conditions: string[];
  confirmation_conditions: string[];
  exit_conditions: string[];
  stop_loss_logic: string;
  take_profit_logic: string;
  invalidation_logic: string;
  is_builtin: boolean;
  current_signal: {
    level: number;
    level_name: string;
    direction: string | null;
    confidence_score: number | null;
  } | null;
}

export interface StrategiesListResponse {
  connected: boolean;
  signals_allowed: boolean;
  strategies: StrategyItem[];
}

export interface MtfRow {
  timeframe: string;
  trend: string;
  structure: string;
  momentum: string;
  signal_state: string;
}

export interface AlertDTO {
  strategy_name: string;
  kind: string;
  direction: string | null;
  message: string;
  timeframe: string | null;
  entry_zone: number[] | null;
  stop_loss: number | null;
  take_profits: number[] | null;
  risk_reward: number | null;
  timestamp_epoch: number;
}
