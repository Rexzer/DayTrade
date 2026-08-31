# Development Roadmap

Built in phases. Each phase is verified before the next begins.

## Phase 1 — Foundation ✅ (this deliverable)
Project structure, modular engine boundaries, database models, authentication
architecture, dashboard, XAUUSD chart container, market-data abstraction,
WebSocket infrastructure, settings, trading-mode selector (analysis-only
active; paper/live locked), security baseline, tests, docs.
**No live trading. No fake data.**

## Phase 2 — Analysis
Technical indicators (EMA/SMA/RSI/MACD/ATR/Bollinger/VWAP/ADX), candle
construction, market-regime detection, the built-in strategy families, signal
generation with full reasoning, and multi-timeframe analysis feeding the
dashboard. Real market-data provider wired into the abstraction.

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
