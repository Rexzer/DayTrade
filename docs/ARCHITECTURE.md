# Architecture — XAUUSD Trading Platform

> Phase 7 (live execution + independent risk engine). Live execution is
> user-initiated only, gated by an explicit authorization and the authoritative
> risk engine. The platform never auto-executes trades.

## Phase 7 addendum — Live execution + independent risk engine

The mandatory pipeline (no shortcuts):

```
Strategy Engine → Signal → AUTHORIZATION → RISK ENGINE → ORDER VALIDATION →
duplicate check → EXECUTION (MetaTrader 5) → result verification → log
```

- `execution_engine/authorization.py::LiveAuthorization` — live orders require
  ALL of: `LIVE_EXECUTION_ENABLED` (backend), the six user confirmations, an
  explicit ARM action, and no active kill switch. It is in-memory, so a restart
  disables live trading. The frontend alone can never authorize execution.
- `risk_engine/live_risk.py::LiveRiskEngine` — the INDEPENDENT, authoritative
  gate. Broker-spec position sizing (tick size/value) + all hard limits
  (per-trade risk, daily/weekly loss, drawdown, max open / max XAUUSD positions,
  trades/day, consecutive losses) + spread / news / data / execution failsafes.
  Daily-loss and drawdown halts LATCH and require a manual reset. The strategy
  engine cannot bypass it — the coordinator needs an approving RiskDecision.
- `execution_engine/coordinator.py::ExecutionCoordinator` — the ONLY path to a
  live order. Records every stage in an execution log, prevents duplicate
  submissions, and NEVER assumes success (only an explicit broker DONE result
  counts). Provides the kill switch (stop new trades immediately; optionally
  close positions / cancel pending first).
- `MT5ExecutionProvider` now implements authorized `send_order` / `modify_order`
  / `close_position` (order_send mapping + result verification), gated by the
  authorization.

Backend: `backend/app/live/service.py` + `/api/live/*` routes (status, confirm,
enable/disable, kill + kill/clear, risk + risk/reset, execute, log). Execution
is USER-INITIATED (`/live/execute`); there is no autonomous loop
(`ENABLE_LIVE_TRADING` stays false and blocks startup if set). Frontend: a Live
Trading page with the confirmation checklist, ARM/disarm, a prominent emergency
stop, risk state, and the execution log.

---


## Phase 6 addendum — MetaTrader 5 integration (read-only)

The `execution_engine/` package gains a venue-agnostic execution abstraction
and a MetaTrader 5 connector — all reads, no writes:

```
ExecutionProvider (provider.py)  connect/disconnect/is_connected
        │  reads: account · symbol spec · tick · positions · orders
        │  validation: check_order (dry-run) — validate_order() is pure
        │  writes: send/modify/close -> _require_live() ALWAYS raises (Phase 7)
        ▼
MT5ExecutionProvider (mt5_connector.py)  wraps an INJECTABLE MetaTrader5 client
        ├── MT5MarketDataProvider (mt5_market_data.py)  MARKET_DATA_PROVIDER=mt5
        ├── PositionSynchronizer (sync.py)  opened/closed/modified diffs
        └── build_account_verification (verification.py)  broker/account/specs
```

Safety: writes are disabled in code (`_require_live` raises regardless of any
flag); `LIVE_EXECUTION_ENABLED` defaults false and the app refuses to start if
it is true. Broker contract specs (digits, point, tick value, min/max/step lot)
are read from the ACTUAL account — never assumed universal. Credentials come
from the environment/secret store and are never logged or returned by the API.

Backend: `backend/app/mt5/service.py` + read-only routes under `/api/mt5/*`
(status, connect/disconnect, account, symbol, tick, positions, orders, history,
candles, sync, verify, check-order). `/api/mt5/execution/status` exists only to
report that execution is disabled. MT5 can also be selected as the market-data
source. Frontend: a **Data Connections** page shows MT5 status + account
verification + XAUUSD contract specs.

---


## Phase 5 addendum — Paper trading engine

The `paper_trading/` package (pure Python) simulates a full trading account on
LIVE data — it can never place a real order:

```
market ticks ──► PaperTradingEngine.on_price(bid, ask, epoch)
                   │  process pending limit/stop orders
                   │  manage positions: SL / TP / partial exit / trailing stop
                   │  mark-to-market equity, drawdown, DAILY-LOSS halt
                   ▼
candle closes ─► (auto) evaluate strategies ─► on_signal(signal)
                   │  SIGNAL is always journalled; a TRADE is only opened if
                   │  risk checks pass (min level, max positions, sizing, geometry)
                   │  otherwise a REJECTED entry explains why (signal != trade)
                   ▼
PaperAccount (account.py): balance, positions, closed trades, daily/drawdown
CostModel (execution.py): adverse spread + slippage + latency, commission
PaperJournal (journal.py) · performance.py (per-strategy comparison)
```

The trading-mode state machine now enables **PAPER_TRADING**; **LIVE_TRADING
remains hard-locked**. Backend: `backend/app/paper_trading/service.py` registers
tick/candle listeners on the market service and auto-trades confirmed setups
only while ACTIVE. Endpoints under `/api/paper/*` (state, performance, trades,
journal, start/pause/resume/stop/reset/close). Nothing here can place a real
order.

---


## Phase 4 addendum — Backtesting & validation engine

The `backtesting/` package (pure Python) provides a leakage-free backtester and
a validation suite:

```
candles_by_tf ──► Backtester (engine.py)
                    │  no look-ahead: signal on CLOSED bar j → enter at OPEN j+1;
                    │  position managed from j+2; same-bar stop-before-target
                    │  CostModel (execution.py): spread+slippage adverse, commission
                    │  position_lots: risk-% sizing to the stop distance
                    ▼
                  BacktestResult ── metrics.py (net/gross, PF, expectancy,
                    │                win/loss, avg/largest, max drawdown, streaks,
                    │                Sharpe/Sortino, equity + drawdown curves)
                    ▼
Validation:  splitting.py (train/validation/OOS; date range gates ENTRIES only,
             full lookback retained) · walkforward.py (optimize in-sample →
             evaluate strictly-later OOS) · sensitivity.py (fragility flag) ·
             montecarlo.py (bootstrap drawdown/equity ranges) ·
             report.py (PASS/WARNING/FAILED + robustness + warnings)
```

Anti-leakage is enforced structurally: `Backtester._slice_context` only ever
exposes candles fully closed by the decision time (across all timeframes), and
entries execute on the next bar's open. Date ranges restrict which bars may
open a trade without dropping lookback history, so sub-period and walk-forward
tests never see the future.

Backend: `backend/app/backtesting/service.py` sources historical candles from
the active provider and runs backtests/reports. Endpoints:
`GET /api/backtest/strategies`, `POST /api/backtest/run`, `POST /api/backtest/report`.
Nothing here can place an order, and no result is presented as a guarantee.

---


## Phase 2 addendum — Real-time market-data engine

The `market_data/` package gains a full real-time pipeline (all pure Python,
provider-independent):

```
Provider (simulated | rest | broker...)   implements MarketDataProvider
        │  ticks
        ▼
CandleAggregator (per timeframe)   UTC bucketing; dedup; out-of-order;
        │  candles                 gap detection (missing_buckets)
        ├──────────────► FeedHealthMonitor  LIVE/DELAYED/STALE/DISCONNECTED
        │                                   + signal gating (signals_allowed)
        ▼
MarketDataService (backend/app/market_data)
        ├─ ReconnectionController  detect drop → backoff → BACKFILL → LIVE
        ├─ CandleRepository        PostgreSQL storage, duplicate-proof
        └─ ConnectionManager       broadcasts to /ws/market
                                   { tick | candle_closed | health | status }
```

Key modules:
- `market_data/tick.py` — `Tick` (bid/ask/last/volume; derived price/spread).
- `market_data/timeframes.py` — UTC-aligned bucket maths + gap enumeration.
- `market_data/candle_engine.py` — `CandleAggregator` (the core).
- `market_data/health.py` — `FeedHealthMonitor` (stale → signals halted).
- `market_data/reconnection.py` — `ReconnectionController` state machine.
- `market_data/symbols.py` — broker symbol mapping to canonical XAUUSD.
- `market_data/simulated_provider.py` — labelled synthetic feed (offline dev).
- `market_data/providers/rest_polling.py` — generic real HTTP quote provider.
- `backend/app/market_data/service.py` — async orchestrator + broadcaster.
- `backend/app/db/models.py::MarketCandle` + `candle_repository.py` — storage.

New endpoints: `GET /api/market/status|snapshot|candles|timeframes|symbols`,
`POST /api/market/symbol`, and `WS /ws/market`.

Failsafe: when the feed is STALE or DISCONNECTED, `FeedHealthMonitor.
signals_allowed()` returns False, and the reconnection machine refuses to
report LIVE until backfill completes — so the platform never acts on, or
silently resumes with, incomplete data. Simulated data is always tagged
`source="simulated"` and surfaced as such in the UI.

---

## Phase 3 addendum — Strategy & signal engine

The `strategy_engine/` package gains a full analysis engine (pure Python):

```
MarketContext (candles per timeframe)
        │
        ▼
Indicators (indicators.py)  EMA/SMA/RSI/MACD/ATR/Bollinger/ADX/VWAP
Structure  (structure.py)   swing points, HH/HL, support/resistance
        │
        ▼
RegimeDetector (regime.py)  9 regimes from EMA+ADX+ATR/BB+structure
        │
        ▼
Strategies (strategies/*)   5 built-ins + user RuleStrategy (rules.py)
        │  Signal (level, direction, entry/SL/TP, R:R,
        │          confirmations, missing, invalidation, score)
        ▼
SignalEngine (engine.py)    safety gating: HALTS on stale/disconnected
        ├── MultiTimeframeAnalyzer (mtf.py)  4H/1H/15M/5M trend/structure/…
        ├── ScoreCard (scoring.py)           transparent rubric (≠ probability)
        └── AlertManager (alerts.py)         WATCH/POTENTIAL/CONFIRMED/INVALIDATED
```

Backend: `backend/app/strategy/service.py` builds the MarketContext from the
MarketDataService candles, runs the engine with the feed's data status as the
safety gate, and manages alerts + custom strategies. New endpoints:
`GET /api/strategies`, `/strategies/signals`, `/strategies/{key}`,
`/strategies/analysis/mtf`, `/strategies/alerts`, and custom-strategy CRUD at
`/strategies/custom`. Custom strategies persist via the `user_strategies`
table (`UserStrategy` model).

Safety: strategies produce only NO_SETUP / WATCH / POTENTIAL_SETUP /
CONFIRMED_SETUP. They can never reach TRADE_EXECUTED and cannot place orders.
Signal generation stops entirely when data is stale/disconnected or required
timeframe history is missing.

---

## Phase 1 foundation (unchanged)

## 1. High-level component diagram

```
                        ┌──────────────────────────────┐
                        │        Frontend (Next.js)     │
                        │  Dashboard · Chart · Settings  │
                        └───────────────┬───────────────┘
                             HTTPS / REST │  WebSocket (status)
                        ┌───────────────▼───────────────┐
                        │        Backend (FastAPI)       │
                        │  API routers · WS manager      │
                        └───┬───────┬───────┬───────┬────┘
                            │       │       │       │
             ┌──────────────▼┐ ┌────▼─────┐ │  ┌────▼───────────┐
             │ market_data   │ │ strategy │ │  │ risk_engine    │
             │ (abstraction) │ │ _engine  │ │  │ (sizing/limits)│
             └───────────────┘ └──────────┘ │  └────────────────┘
                            ┌────────────────▼┐
                            │ execution_engine │  (HARD-DISABLED in Phase 1)
                            └──────────────────┘
                        ┌───────────────┬───────────────┐
                        │  PostgreSQL   │     Redis      │
                        └───────────────┴───────────────┘
```

Backtesting and paper-trading packages are reserved (Phases 3 and 4).

## 2. Module boundaries (role separation)

Per the security spec, engines are separated so responsibilities don't leak:

- **`market_data/`** — provider-agnostic interface + `NullMarketDataProvider`.
  Never fabricates prices. Concrete providers plug in later.
- **`strategy_engine/`** — `Strategy` interface, `Signal`/`SignalLevel`,
  `MarketRegime`, and an (empty) registry. Consumes market data; produces
  explainable signals. Cannot place orders.
- **`risk_engine/`** — position sizing + pre-trade checks. Cannot place orders.
- **`execution_engine/`** — the ONLY module that could talk to a broker. In
  Phase 1 every method raises `ExecutionDisabledError`.
- **`backtesting/` · `paper_trading/`** — reserved interfaces.
- **`backend/`** — FastAPI web layer, config, security, DB, WebSocket. Composes
  the engines but does not embed their logic.

The pure-domain rules (trading mode, connection/data status, security,
sizing) live in dependency-free modules so they are unit-testable anywhere.

## 3. Data flow (Phase 1)

1. Frontend polls REST endpoints (`/api/market/snapshot`, `/api/mode`, ...).
2. Backend returns **honest disconnected states** (null prices, "not
   connected"), because the null provider is active.
3. A status WebSocket (`/ws/status`) pushes a "disconnected" frame; real
   price frames arrive in Phase 2.

## 4. API surface (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Service banner |
| GET | `/api/health` | Liveness + phase/mode |
| GET | `/api/health/db` | DB reachability |
| POST | `/api/auth/register` | Create user (hashed password) |
| POST | `/api/auth/login` | Issue JWT |
| GET | `/api/auth/me` | Current user (bearer token) |
| GET | `/api/mode` | Modes + availability |
| POST | `/api/mode/{mode}` | Switch mode (paper/live → 409 locked) |
| GET | `/api/market/snapshot` | Quote (null in Phase 1) |
| GET | `/api/market/timeframes` | Supported timeframes |
| GET | `/api/market/candles` | Candles (empty in Phase 1) |
| GET | `/api/account` | Account (not connected) |
| GET | `/api/strategies` | Active (none) + planned families |
| GET | `/api/news/next` | Next event (unavailable) |
| GET | `/api/settings` | Settings sections |
| WS | `/ws/status` | Connection status frames |

## 5. WebSocket architecture

A single `ConnectionManager` tracks clients and broadcasts JSON frames. Phase 1
broadcasts status only. Phase 2 adds a market-data publisher that fans out tick
/ candle updates; Redis pub/sub becomes the cross-process transport when the
market-data worker is split out.

## 6. Strategy-engine architecture

Each strategy implements `Strategy.evaluate(context) -> Signal`. The lifecycle
mirrors the platform philosophy: **regime → setup → confirmation → entry/stop/
target**. Signals are explicit and explainable (`confirmations`,
`missing_confirmations`, `invalidation`, transparent `confidence_score`). The
registry is the plug-in point for built-in and user-created strategies.

## 7. Risk-engine architecture

`RiskSettings` holds validated limits. `RiskEngine.position_size()` computes
lots from account balance, risk %, stop distance and the broker's own point
value (never assumed), and always returns a human-readable explanation.
Enforcement against real orders is added with the execution engine in Phase 6.

## 8. MetaTrader integration (future — Phase 5)

```
Application → Trading API/Connector → MetaTrader 5 → Broker
```

Only the `execution_engine` and a dedicated MT5 connector may talk to the
broker. Credentials go to a secret store; `broker_connections` holds only a
reference.

## 9. Security architecture

- Secrets via environment variables; none in source or frontend.
- Passwords hashed (PBKDF2-HMAC-SHA256); never stored/logged in plaintext.
- JWT (HS256) access tokens.
- Structured JSON logging that never includes secrets.
- Execution requires explicit authorization (absent by design in Phase 1).
- Config validation fails closed: the app refuses to start if
  `ENABLE_LIVE_TRADING` is true.

## 10. Failsafe posture (Phase 1)

- No provider ⇒ status `DISCONNECTED`, prices `null` (never stale/fake).
- `classify_data_freshness()` will drive LIVE/DELAYED/STALE indicators once a
  feed exists; stale data must stop live-signal generation (Phase 2+).
- Execution is hard-disabled; the kill switch is a safe no-op.

## 11. Technology stack

Frontend: React + TypeScript + Next.js, TradingView Lightweight Charts.
Backend: Python + FastAPI. DB: PostgreSQL. Cache/realtime: Redis.
Containerization: Docker / docker-compose.
