===============================================================================
XAUUSD DAY-TRADING INTELLIGENCE & AUTOMATION PLATFORM
Phase 1 — Foundation (ANALYSIS ONLY)
===============================================================================

*** LIVE TRADING IS NOT IMPLEMENTED IN PHASE 1. ***

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
and JWT), and configuration safety invariants.

(Full API/integration tests that need FastAPI/SQLAlchemy run once
backend/requirements.txt is installed in a networked environment.)


-------------------------------------------------------------------------------
8. MARKET-DATA SETUP
-------------------------------------------------------------------------------
Phase 1 uses NullMarketDataProvider — it reports "disconnected" and returns no
prices. A real provider is added in Phase 2 via the market_data abstraction,
so no application code outside market_data/ needs to change. The system will
never silently substitute stale data for live data.


-------------------------------------------------------------------------------
9. METATRADER SETUP
-------------------------------------------------------------------------------
Not applicable in Phase 1. MetaTrader 5 integration (account info, positions,
orders, synchronisation) is added in Phase 5, with credentials held in a
secret store and only a non-secret reference stored in the database.


-------------------------------------------------------------------------------
10. STRATEGY CONFIGURATION / CREATING STRATEGIES
-------------------------------------------------------------------------------
The plug-in interface exists now (strategy_engine/strategy.py). A strategy
implements evaluate(context) -> Signal and is added to the registry. Built-in
families and the user-facing Strategy Builder arrive in Phase 2.


-------------------------------------------------------------------------------
11. BACKTESTING / PAPER TRADING / LIVE TRADING
-------------------------------------------------------------------------------
  Backtesting  : reserved (Phase 3).
  Paper trading: reserved (Phase 4); mode is LOCKED in the UI.
  Live trading : reserved (Phase 6); mode is LOCKED and cannot be enabled.


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
17. CURRENT LIMITATIONS (PHASE 1)
-------------------------------------------------------------------------------
  * No real market data, indicators, signals or regime detection yet.
  * No backtesting, paper trading, MetaTrader, or live execution.
  * Only Dashboard and Settings pages are interactive; other pages are listed
    but marked as coming in later phases.


-------------------------------------------------------------------------------
18. FUTURE PHASES (see docs/ROADMAP.md)
-------------------------------------------------------------------------------
  Phase 2  Analysis (indicators, regime, strategies, signals)
  Phase 3  Backtesting (walk-forward, Monte Carlo, overfitting checks)
  Phase 4  Paper trading (virtual account, simulated execution, journal)
  Phase 5  MetaTrader integration
  Phase 6  Live execution (behind explicit confirmation + kill switch)

===============================================================================
