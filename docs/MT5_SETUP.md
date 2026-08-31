# MetaTrader 5 Setup

MT5 integration is **read-only** by default; live order execution requires the
explicit authorization flow (see RISK_MANAGEMENT.md and the Live Trading page).

## Requirements
- The MetaTrader 5 **terminal** installed on the backend host (Windows, or
  Linux via Wine).
- The `MetaTrader5` Python package (`pip install MetaTrader5`) on that host.
- A broker account (start with a **demo** account).

> The connector cannot run in a headless/Linux-only or offline environment —
> that is why the test suite uses an injectable mock client.

## Configuration (`.env`)
```
MT5_LOGIN=51234567
MT5_SERVER=YourBroker-Demo
MT5_PASSWORD=your-password        # env only; never logged or returned by the API
MT5_SYMBOL=XAUUSD                 # or your broker's gold symbol, e.g. XAUUSDm
MT5_PATH=                         # optional path to terminal64.exe
MARKET_DATA_PROVIDER=mt5          # optional: use MT5 as the data source too
LIVE_EXECUTION_ENABLED=false      # precondition for the live authorization flow
```

The password is read from the environment only and is **never** stored on the
settings object, logged, or returned by any endpoint.

## Endpoints (read-only)
`GET /api/mt5/status | account | symbol | tick | positions | orders | history |
candles | sync | verify` · `POST /api/mt5/connect | disconnect` ·
`POST /api/mt5/check-order` (dry-run validation only).

## Account verification
`GET /api/mt5/verify` returns broker, server, login, account type (demo/real),
currency, leverage and the **actual XAUUSD contract specifications** (digits,
point, tick size/value, contract size, min/max/step lot). Broker specs are
never assumed to be universal. Verify these before enabling live trading.

## Symbol names
Brokers name gold differently (XAUUSD, XAUUSDm, GOLD, XAUUSD.a, ...). Set
`MT5_SYMBOL` / `MARKET_DATA_SYMBOL` to your broker's exact symbol.
