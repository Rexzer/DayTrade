===============================================================================
XAUUSD DAY-TRADING INTELLIGENCE & AUTOMATION PLATFORM
Phase 6 — MetaTrader 5 Integration (READ-ONLY)
===============================================================================

*** LIVE ORDER EXECUTION IS NOT IMPLEMENTED. NO REAL ORDERS CAN BE SENT. ***
*** MetaTrader 5 integration is READ-ONLY; paper trading stays simulated. ***

Phase 6 adds MetaTrader 5 connectivity behind a venue-agnostic
ExecutionProvider abstraction. It reads account info, the actual broker XAUUSD
symbol specifications, ticks, historical data, open positions, pending orders
and trade history; synchronizes positions; validates orders (dry-run); and
verifies the connected account. MT5 can also be used as a market-data source.

Order EXECUTION remains DISABLED: every write operation raises, the
LIVE_EXECUTION_ENABLED flag defaults to false, and the app refuses to start if
it is set true. Live execution is a later phase, behind explicit backend
authorization, account verification and a kill switch.

Phase 5 adds a complete paper-trading environment that uses LIVE market data
but simulates all execution:
  * Virtual account: starting balance, risk per trade, max daily loss, max
    open positions, max position size.
  * Realistic simulated execution: market/limit/stop orders, stop-loss/
    take-profit, partial exits, trailing stops, with adverse spread + slippage
    + latency and commission (never assumes perfect fills).
  * Risk limits enforced: per-trade sizing, max open positions, and a daily
    loss limit that HALTS new entries (auto-clears next day or on reset).
  * SIGNAL vs TRADE is explicit: every signal is journalled; a trade is only
    opened if risk checks pass, otherwise the rejection reason is recorded.
  * Paper positions, an auto trade journal, and per-strategy performance so
    strategies can be compared.
  * User controls: start / pause / resume / stop / reset / close position(s).

The trading-mode selector now offers ANALYSIS ONLY and PAPER TRADING. LIVE
TRADING remains locked and cannot be enabled.

Phase 4 adds a professional, leakage-free backtesting & validation engine:
  * Event-driven backtester: signals act on the NEXT bar's open (no look-
    ahead); positions managed conservatively (same-bar stop-before-target).
  * Modelled execution costs: spread, slippage (both adverse) and commission;
    risk-based position sizing to the stop distance.
  * Full metrics: net/gross P&L, win/loss rate, profit factor, expectancy,
    average/largest win-loss, max drawdown, consecutive streaks, Sharpe/
    Sortino, plus equity and drawdown curves.
  * Validation: train/validation/out-of-sample split, walk-forward analysis,
    parameter-sensitivity (fragility flag), Monte Carlo (drawdown ranges), and
    a PASS/WARNING/FAILED robustness report.
  * Strict anti-leakage: the strategy only ever sees candles fully closed by
    the decision time; date ranges gate ENTRIES without dropping lookback.

The purpose is to test whether a strategy's historical result survives OUTSIDE
its fitting period — NOT to find or promise a profitable strategy. Past
performance does not guarantee future results.

Phase 3 adds a modular strategy & signal engine on top of the Phase 2 market
data:
  * Indicator library (EMA/SMA/RSI/MACD/ATR/Bollinger/ADX/VWAP), reference-
    validated.
  * Market-regime detection (9 regimes) and market-structure analysis.
  * Five built-in strategies: Trend Following, EMA Pullback, Breakout+Retest,
    Support/Resistance Reversal, Multi-Timeframe Confluence.
  * Transparent, explainable signals (levels NO_SETUP / WATCH / POTENTIAL /
    CONFIRMED) with entry/SL/TP, risk-reward, met + missing conditions and an
    invalidation level. A configurable score rubric (NOT a probability).
  * Multi-timeframe analysis (4H/1H/15M/5M) and an alert system.
  * A user Strategy Builder (AND/OR rule conditions) for custom strategies.
  * Safety: signal generation HALTS on stale/disconnected data or missing
    timeframe history.

No strategy is guaranteed profitable. Every strategy is a hypothesis to be
backtested and validated (Phase 4+).

Data sources:
  * MARKET_DATA_PROVIDER=none       -> fully disconnected (default).
  * MARKET_DATA_PROVIDER=simulated  -> synthetic feed for OFFLINE DEV ONLY;
                                       always labelled source="simulated" and
                                       NOT real market data.
  * MARKET_DATA_PROVIDER=rest       -> generic HTTP JSON quote poller (real;
                                       requires network + endpoint/API key).

This build is a foundation only. It runs in ANALYSIS-ONLY mode. There is no
automated order execution, no paper trading, and no connection to a real-money
MetaTrader account. Those capabilities are added in later phases behind
explicit safeguards.

Past performance does not guarantee future results. No strategy in this
platform is, or will be, guaranteed to make money. Every strategy is a
hypothesis that must be backtested, validated out-of-sample, and monitored.


-------------------------------------------------------------------------------
1. WHAT THIS APPLICATION DOES
-------------------------------------------------------------------------------
The long-term goal is a transparent XAUUSD (Gold/USD) trading workstation:
real-time monitoring, explainable strategies, backtesting, out-of-sample
validation, paper trading, optional MetaTrader 5 integration, optional
automated live trading, risk management, trade journaling, analytics, and an
AI analysis assistant.

Phase 1 delivers the safe foundation:
  * Modular architecture with clear engine boundaries.
  * Professional dashboard (XAUUSD header, market overview, chart container,
    multi-timeframe panel, strategy/account/news panels, mode selector).
  * Market-data ABSTRACTION with a null provider (no fabricated prices).
  * Trading-mode state machine: ANALYSIS ONLY enabled; PAPER and LIVE locked.
  * Database models, authentication architecture, structured logging.
  * WebSocket infrastructure for future real-time updates.
  * Settings pages (Trading clearly shows: LIVE TRADING DISABLED).
  * Tests, including guarantees that LIVE TRADING CANNOT BE ACTIVATED.


-------------------------------------------------------------------------------
2. ARCHITECTURE (see docs/ARCHITECTURE.md for detail)
-------------------------------------------------------------------------------
  frontend/          Next.js + TypeScript UI (dashboard, chart, settings)
  backend/           FastAPI app: config, security, DB, API routes, WebSocket
  database/          PostgreSQL init + notes (models live in backend/app/db)
  market_data/       Provider-agnostic interface + NullMarketDataProvider
  strategy_engine/   Strategy interface, signal levels, market regimes, registry
  risk_engine/       Risk settings + position sizing + pre-trade checks
  execution_engine/  HARD-DISABLED in Phase 1 (raises on any order attempt)
  backtesting/       Reserved (Phase 3)
  paper_trading/     Reserved (Phase 4)
  tests/             Pure-logic test suite (runs without web/db dependencies)
  docs/              Architecture + roadmap

The pure-Python engine packages and core domain (trading mode, connection/data
status, security, sizing) have NO third-party dependencies and are unit-tested
in isolation.


-------------------------------------------------------------------------------
3. REQUIREMENTS
-------------------------------------------------------------------------------
  * Python 3.10+  (3.11 recommended)
  * Node.js 18+   (20 recommended)
  * PostgreSQL 14+  (or use Docker)
  * Redis 6+        (or use Docker)
  * Docker + Docker Compose (optional, recommended)


-------------------------------------------------------------------------------
4. QUICK START WITH DOCKER (recommended)
-------------------------------------------------------------------------------
  1. cp .env.example .env
  2. Edit .env: set a strong SECRET_KEY and a POSTGRES_PASSWORD.
     Leave ENABLE_PAPER_TRADING=false and ENABLE_LIVE_TRADING=false.
  3. docker compose up --build
  4. Open the frontend:  http://localhost:3000
     Backend API docs:    http://localhost:8000/docs

The backend refuses to start if ENABLE_LIVE_TRADING=true (Phase 1 safety lock).


-------------------------------------------------------------------------------
5. MANUAL DEVELOPMENT SETUP
-------------------------------------------------------------------------------
Backend:
  python -m venv .venv
  source .venv/bin/activate            (Windows: .venv\Scripts\activate)
  pip install -r backend/requirements.txt
  cp .env.example .env                 (edit values)
  # Ensure PostgreSQL + Redis are running and .env points at them.
  uvicorn backend.app.main:app --reload --port 8000

  Create the tables (dev convenience) from a Python shell:
      python -c "from backend.app.db.session import init_db; init_db()"

Frontend:
  cd frontend
  cp .env.example .env.local
  npm install
  npm run dev                          (serves on http://localhost:3000)


-------------------------------------------------------------------------------
6. ENVIRONMENT VARIABLES (see .env.example for the full list)
-------------------------------------------------------------------------------
  APP_ENV, APP_DEBUG, BACKEND_HOST, BACKEND_PORT, CORS_ORIGINS
  SECRET_KEY                 (REQUIRED in production; no usable default)
  ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM
  POSTGRES_* / DATABASE_URL
  REDIS_URL
  ENABLE_PAPER_TRADING=false (must stay false in Phase 1)
  ENABLE_LIVE_TRADING=false  (must stay false; app refuses to start otherwise)
  NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_WS_BASE_URL  (frontend)

Secrets are read from the environment only. Never commit .env. Never place
credentials in source code or the frontend.


-------------------------------------------------------------------------------
7. RUNNING TESTS
-------------------------------------------------------------------------------
The core-logic test suite is dependency-free and runs offline:

  python -m pytest -q

It covers: trading-mode locks (LIVE TRADING CANNOT BE ACTIVATED),
connection/data status classification, the disabled execution engine, the
null market-data provider, risk sizing/validation, security (password hashing
and JWT), configuration safety invariants, and the Phase 2 market-data engine
(tick processing, candle construction, duplicate/out-of-order/missing/gap
handling, UTC timeframe bucketing, stale detection + signal gating, the
reconnection state machine, broker symbol mapping, and the simulated provider);
the Phase 3 strategy engine (indicators validated vs reference values, regime
detection, market structure, the five built-in strategies, transparent scoring,
multi-timeframe analysis, alerts, the signal engine's safety gating, and the
user rule-builder); and the Phase 4 backtesting engine (execution costs, risk
sizing, backtester mechanics for long/short entries/exits, metrics, drawdown,
train/validation/OOS separation, walk-forward OOS-after-IS ordering, parameter
sensitivity, Monte Carlo determinism, and a direct no-look-ahead slicing test);
the Phase 5 paper-trading engine (simulated fills, SL/TP, trailing stops,
partial exits, risk-based sizing, max-positions and daily-loss halts,
signal-vs-trade rejection, controls, and per-strategy performance); and the
Phase 6 MetaTrader 5 integration via a mocked client (connection failure,
reconnection, account/symbol/tick/historical/positions/orders mapping, invalid
symbol, order validation for invalid volume/SL/TP, broker rejection, position
synchronization, the read-only market-data adapter, account verification, and
proof that all write operations remain disabled).

(Full API/integration tests that need FastAPI/SQLAlchemy run once
backend/requirements.txt is installed in a networked environment.)


-------------------------------------------------------------------------------
8. MARKET-DATA SETUP (PHASE 2)
-------------------------------------------------------------------------------
Select a provider via MARKET_DATA_PROVIDER in .env:

  none       Default. NullMarketDataProvider: disconnected, no prices.

  simulated  A deterministic synthetic feed for offline development. Every
             tick/snapshot is tagged source="simulated" and the UI shows a
             clear "SIMULATED FEED" warning. This is NOT real market data and
             must never be used for real decisions. Useful to exercise the
             chart, candles, WebSocket, stale-detection and reconnection.

  rest       A generic HTTP JSON quote poller (market_data/providers/
             rest_polling.py). Point RestProviderConfig.url at a real quote
             endpoint and map the bid/ask/last JSON paths. Requires network
             access and (usually) an API key supplied via environment.

Other market-data env vars:
  MARKET_DATA_SYMBOL            broker symbol (XAUUSD, XAUUSDm, GOLD, XAUUSD.a)
  MARKET_TICK_INTERVAL_SECONDS  poll/generate interval
  DATA_DELAYED_AFTER_SECONDS    LIVE -> DELAYED threshold
  DATA_STALE_AFTER_SECONDS      DELAYED -> STALE threshold (halts signals)
  MARKET_HISTORY_CANDLES        candles seeded per timeframe on connect

Behaviour guarantees:
  * Timestamps are stored/aggregated in UTC.
  * Candles are unique per (symbol, timeframe, open_time) — no duplicates.
  * On disconnect: detect -> notify frontend -> reconnect w/ backoff ->
    backfill missed candles -> resume LIVE. Never resumes silently with gaps.
  * When data is STALE/DISCONNECTED, downstream signal generation is halted
    and the UI shows "MARKET DATA STALE". Stale data is never shown as live.

NOTE ON OFFLINE ENVIRONMENTS: connecting a real feed requires network access.
Use MARKET_DATA_PROVIDER=simulated to see the full pipeline without a network.


-------------------------------------------------------------------------------
9. METATRADER SETUP (PHASE 6, READ-ONLY)
-------------------------------------------------------------------------------
Requirements: the MetaTrader 5 terminal and the 'MetaTrader5' Python package
on the BACKEND host (Windows, or Wine). Then set in .env:
  MT5_LOGIN=<account number>
  MT5_SERVER=<YourBroker-Demo>
  MT5_PASSWORD=<password>     (env only; never logged or returned by the API)
  MT5_SYMBOL=XAUUSD           (or your broker's gold symbol, e.g. XAUUSDm)
  MT5_PATH=<optional path to terminal64.exe>

Use it from the Data Connections page (Connect) or the API:
  GET  /api/mt5/status     GET /api/mt5/account    GET /api/mt5/symbol
  GET  /api/mt5/tick       GET /api/mt5/positions  GET /api/mt5/orders
  GET  /api/mt5/history    GET /api/mt5/candles    GET /api/mt5/sync
  GET  /api/mt5/verify     POST /api/mt5/check-order   (dry-run validation only)
  POST /api/mt5/connect    POST /api/mt5/disconnect

Order execution is disabled: there is NO endpoint that can place, modify or
close an order. Broker contract specs are read from the actual account and are
never assumed to be universal. Set MARKET_DATA_PROVIDER=mt5 to also use MT5 as
the live data source.


-------------------------------------------------------------------------------
10. STRATEGY CONFIGURATION / CREATING STRATEGIES
-------------------------------------------------------------------------------
Built-in strategies live in strategy_engine/strategies/ and implement
evaluate(context) -> Signal. Five ship in Phase 3. Users can also create
custom strategies via the Strategy Builder page (AND/OR rule conditions over
indicators/price/constants); these are validated, saved to the user_strategies
table, and appear in the Strategy Library. API: POST /api/strategies/custom.
All strategies are analysis-only and can never place an order.


-------------------------------------------------------------------------------
11. BACKTESTING / PAPER TRADING / LIVE TRADING
-------------------------------------------------------------------------------
  Backtesting  : IMPLEMENTED (Phase 4). Run from the Backtesting page or via
                 POST /api/backtest/run and /api/backtest/report. Leakage-free;
                 results are historical measurements, never guarantees.
  Paper trading: IMPLEMENTED (Phase 5). Simulated execution on live data via
                 the Paper Trading page or /api/paper/*. No real orders.
  Live trading : reserved (later phase); mode is LOCKED and cannot be enabled.


-------------------------------------------------------------------------------
12. RISK MANAGEMENT
-------------------------------------------------------------------------------
RiskSettings defines conservative, validated limits (risk per trade, daily/
weekly loss, max positions/trades, consecutive losses, max lot, max spread).
Position sizing always shows its calculation. Hard enforcement against real
orders is wired in with the execution engine in Phase 6.


-------------------------------------------------------------------------------
13. SECURITY
-------------------------------------------------------------------------------
  * Secrets via environment variables only.
  * Passwords hashed with PBKDF2-HMAC-SHA256 (never plaintext, never logged).
  * JWT (HS256) access tokens.
  * Structured JSON logs that never contain secrets.
  * Role/module separation: only execution_engine may reach a broker, and it
    is disabled in Phase 1.
  * Config validation fails closed on any Phase 1 safety violation.


-------------------------------------------------------------------------------
14. EMERGENCY SHUTDOWN PROCEDURE
-------------------------------------------------------------------------------
Phase 1 has no live execution, so there is nothing to halt at the broker.
Still:
  * Stop the stack:      docker compose down    (or Ctrl-C the dev servers)
  * The kill switch (execution_engine) is present as a safe no-op and will
    perform real order cancellation/closure only from Phase 6 onward.
  * On restart, live trading NEVER auto-resumes; it must be explicitly enabled.


-------------------------------------------------------------------------------
15. HOW TO DISABLE LIVE TRADING
-------------------------------------------------------------------------------
It is already disabled and cannot be enabled in Phase 1. The safeguards:
  * ENABLE_LIVE_TRADING must be false; the backend refuses to start otherwise.
  * TradingModeManager rejects any switch to LIVE_TRADING (HTTP 409).
  * ExecutionEngine raises ExecutionDisabledError on every order operation.


-------------------------------------------------------------------------------
16. TROUBLESHOOTING
-------------------------------------------------------------------------------
  * Dashboard shows "Backend API is not reachable":
      Start the backend (uvicorn ...) and confirm NEXT_PUBLIC_API_BASE_URL.
  * "database: disconnected" on /api/health/db:
      Check POSTGRES_* / DATABASE_URL and that PostgreSQL is running.
  * Backend won't start, complains about live trading:
      Set ENABLE_LIVE_TRADING=false in .env (required in Phase 1).
  * Chart shows a placeholder:
      Expected — no market-data provider is connected until Phase 2.


-------------------------------------------------------------------------------
17. CURRENT LIMITATIONS (PHASE 6)
-------------------------------------------------------------------------------
  * MetaTrader 5 integration is READ-ONLY. There is NO order execution, and it
    requires the MT5 terminal + MetaTrader5 package on the backend host (so it
    cannot connect in a headless/Linux-only or offline environment).
  * Paper trading remains fully simulated; no real-money execution exists.
  * Interactive pages: Dashboard, Settings, Strategies, Strategy Builder,
    Backtesting, Paper Trading and Data Connections. Live Trading arrives in a
    later phase.


-------------------------------------------------------------------------------
18. FUTURE PHASES (see docs/ROADMAP.md)
-------------------------------------------------------------------------------
  Phase 2  Analysis (indicators, regime, strategies, signals)
  Phase 3  Backtesting (walk-forward, Monte Carlo, overfitting checks)
  Phase 4  Paper trading (virtual account, simulated execution, journal)
  Phase 5  MetaTrader integration
  Phase 6  Live execution (behind explicit confirmation + kill switch)

===============================================================================
