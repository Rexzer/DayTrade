# Development Roadmap

Built in phases. Each phase is verified before the next begins.

## Phase 1 — Foundation ✅ (this deliverable)
Project structure, modular engine boundaries, database models, authentication
architecture, dashboard, XAUUSD chart container, market-data abstraction,
WebSocket infrastructure, settings, trading-mode selector (analysis-only
active; paper/live locked), security baseline, tests, docs.
**No live trading. No fake data.**

## Phase 2 — Real-time Market Data ✅ (this deliverable)
Provider-independent market-data layer: tick model, UTC-aligned candle
aggregation (duplicate/out-of-order/missing handling + gap detection), feed
health with LIVE/DELAYED/STALE/DISCONNECTED classification and signal gating,
a reconnection state machine with exponential backoff and backfill, broker
symbol mapping (XAUUSD/XAUUSDm/GOLD/XAUUSD.a/…), PostgreSQL candle storage with
duplicate prevention, a `/ws/market` real-time WebSocket, and a chart wired to
the live feed. Ships a clearly-labelled simulated provider for offline
development and a generic REST provider scaffold for real feeds.
**Market data only — no trading.**

## Phase 2b / later — Analysis
Technical indicators (EMA/SMA/RSI/MACD/ATR/Bollinger/VWAP/ADX), market-regime
detection, the built-in strategy families, and signal generation with full
reasoning feeding the dashboard. (Signal generation consumes the Phase 2 feed
health so it halts automatically on stale data.)

## Phase 3 — Backtesting
Historical data ingestion, backtesting engine, performance metrics, walk-forward
analysis, Monte Carlo, parameter-sensitivity and overfitting warnings.

## Phase 4 — Paper Trading
Virtual account, simulated execution against live data, trade journal, and
performance tracking. Paper-trading mode unlocks.

## Phase 5 — MetaTrader
MT5 account connection, account info, positions, orders and trade
synchronisation. Secret-store integration for credentials.

## Phase 6 — Live Execution
Live order execution, position management, hard risk enforcement, kill switch
and execution monitoring — behind explicit multi-step user confirmation.
Live-trading mode unlocks only here.

---

### Cross-cutting (progressively hardened)
News/macro filter, notifications (browser/desktop/sound/email/Telegram/
Discord), performance analytics, AI analysis assistant, expanded settings,
data-connection health page, and comprehensive automated tests.

> Past performance does not guarantee future results. No strategy is
> guaranteed to be profitable.
