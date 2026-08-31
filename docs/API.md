# API Reference

Base URL: `http://localhost:8000`. All application routes are under `/api`.
Interactive docs (OpenAPI/Swagger) are served at `/docs`.

## Health & auth
- `GET /api/health`, `GET /api/health/db`
- `GET /api/system/health` — per-component health (🟢/🟡/🔴)
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`

## Mode
- `GET /api/mode`, `POST /api/mode/{mode}` (paper/live via mode endpoint is
  gated; live execution is enabled only via the `/live` authorization flow)

## Market data
- `GET /api/market/status | snapshot | candles | timeframes | symbols`
- `POST /api/market/symbol`
- WebSocket `WS /ws/market` — tick / candle_closed / health / status frames
- WebSocket `WS /ws/status`

## Strategies & signals
- `GET /api/strategies` · `/strategies/signals` · `/strategies/{key}`
- `GET /api/strategies/analysis/mtf` · `/strategies/alerts`
- `GET/POST/DELETE /api/strategies/custom[/{key}]`

## Backtesting
- `GET /api/backtest/strategies` · `POST /api/backtest/run` · `POST /api/backtest/report`

## Paper trading
- `GET /api/paper/state | performance | trades | journal`
- `POST /api/paper/start | pause | resume | stop | reset | close/{id} | close-all`

## MetaTrader 5 (read-only)
- `GET /api/mt5/status | account | symbol | tick | positions | orders | history | candles | sync | verify`
- `POST /api/mt5/connect | disconnect | check-order`
- `GET /api/mt5/execution/status` (reports execution disabled)

## Live execution (user-initiated, authorized)
- `GET /api/live/status | log`
- `GET /api/live/history` — durably-persisted signals / orders / trades
- `POST /api/live/confirm | enable | disable`
- `POST /api/live/dry-run` `{ "enabled": true|false }` — ON validates the full
  chain (incl. broker order_check) but NEVER sends an order (defaults ON)
- `POST /api/live/kill | kill/clear`
- `POST /api/live/risk | risk/reset`
- `POST /api/live/execute` — execute the best current confirmed signal (manual)

**Operator authorization:** the dangerous endpoints (`confirm`, `enable`,
`risk`, `execute`) require an operator credential — either an `X-Operator-Token`
header matching the backend `LIVE_API_TOKEN`, or a valid bearer JWT from
`/api/auth/login`. They fail closed (HTTP 401) if neither is configured.

## AI assistant
- `POST /api/assistant/ask` `{ "question": "..." }` · `GET /api/assistant/examples`

## Analytics
- `GET /api/analytics/performance | journal | comparison | signals/history`

## Notifications
- `GET /api/notifications` · `POST /api/notifications` (channels/events) ·
  `GET /api/notifications/recent` · `POST /api/notifications/test`

## Settings & news
- `GET /api/settings` · `GET /api/account` · `GET /api/news/next`

> No endpoint returns secrets (passwords/API keys). Live order writes require
> explicit authorization; unauthorized writes raise and never reach a broker.
