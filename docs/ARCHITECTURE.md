# Architecture — XAUUSD Trading Platform

> Phase 1 (foundation). Analysis-only. No live trading, no automated
> execution, no real broker connection.

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
