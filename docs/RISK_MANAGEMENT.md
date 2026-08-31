# Risk Management

The risk engine (`risk_engine/live_risk.py`) is **independent and
authoritative**: the execution coordinator must obtain an approving
`RiskDecision` before any order is sent, and the strategy engine cannot bypass
it.

## Position sizing
Lots are derived from the broker's **actual** contract spec — never assumed:

```
risk_amount   = equity * risk_per_trade_pct / 100
ticks_at_risk = |entry - stop| / tick_size
money_per_lot = ticks_at_risk * tick_value
lots          = risk_amount / money_per_lot   (then floored to volume_step,
                                               capped by max_lot_size & volume_max)
```

The calculation is always shown. If the result is below the broker minimum, the
trade is rejected.

## Hard limits (`RiskSettings`)
- Risk per trade (presets 0.25% / 0.5% / 1% / 2%, or custom)
- Max daily loss %, max weekly loss %, **max drawdown %**
- Max open positions, max XAUUSD positions
- Max trades/day, max consecutive losses
- Max lot size, max spread (points)
- News blackout window (minutes before/after a high-impact event)

## Automatic shutdown (latched — manual reset required)
- **Daily loss** limit reached → new trades blocked.
- **Max drawdown** reached → trading halted.
- Reset via `POST /api/live/risk/reset` (or the Risk panel).

## Pre-trade failsafes (each rejects the trade)
- **Spread** exceeds the threshold.
- **News** blackout window active.
- **Data** feed STALE / DISCONNECTED / INVALID.
- **Execution** — MetaTrader 5 not connected.
- Stop-loss geometry invalid; position size zero/below broker minimum.

## Kill switch
`POST /api/live/kill` (Emergency Stop) engages the kill switch, immediately
blocking new trades. It optionally closes open positions and cancels pending
orders first. Clearing it (`/api/live/kill/clear`) does not re-arm live
trading — that always requires the explicit authorization flow again.
