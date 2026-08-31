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

## Phase 3 — Strategy & Signal Engine ✅ (this deliverable)
Indicator library (EMA/SMA/RSI/MACD/ATR/Bollinger/ADX/VWAP, reference-
validated), nine-way market-regime detection, market-structure analysis, five
built-in strategies (Trend Following, EMA Pullback, Breakout+Retest, S/R
Reversal, Multi-Timeframe Confluence), a transparent configurable signal-score
rubric, multi-timeframe analysis, an alert system (WATCH/POTENTIAL/CONFIRMED/
INVALIDATED), and a user rule-builder for custom strategies. Signals are
explainable and gated by feed health (halted on stale/disconnected data).
**Strategies classify setups only — they never execute trades.**

## Phase 4 — Backtesting & Validation ✅ (this deliverable)
Leakage-free event-driven backtester (signal on closed bar, next-bar
execution, conservative same-bar stop-before-target) with modelled execution
costs (spread/slippage/commission) and risk-based position sizing. Full
performance metrics, equity + drawdown curves, train/validation/out-of-sample
splitting, walk-forward analysis (optimize in-sample, evaluate strictly-later
OOS), parameter-sensitivity (fragility flag), Monte Carlo (drawdown ranges),
and a PASS/WARNING/FAILED strategy report. Purpose is robustness assessment —
never a profitability guarantee. **No trade execution.**

## Phase 5 — Paper Trading ✅ (this deliverable)
Virtual account with simulated execution on LIVE data: market/limit/stop
orders, stop-loss/take-profit, partial exits and trailing stops with realistic
(adverse) fills; risk limits (per-trade sizing, max positions, daily-loss
halt); explicit SIGNAL-vs-TRADE distinction; full journal; and per-strategy
performance comparison. Paper-trading mode is unlocked (live stays locked).
**No real orders are possible — every fill is simulated.**

## Phase 6 — MetaTrader 5 Integration ✅ (this deliverable)
Read-only MT5 connectivity via a venue-agnostic ExecutionProvider abstraction
and an injectable, fully-mockable connector: account info, real broker XAUUSD
symbol specs (never assumed), ticks, historical data, positions, orders and
trade history; position synchronization; dry-run order validation; account
verification; and MT5 as a selectable market-data source. Order execution is
hard-disabled (writes raise; `LIVE_EXECUTION_ENABLED` defaults false and the
app refuses to start if true). **No orders can be placed.**

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
