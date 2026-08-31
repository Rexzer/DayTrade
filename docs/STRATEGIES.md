# Strategies

Strategies are plug-ins that classify the market into a signal level and
explain themselves. They **never** execute trades — that is the job of the risk
+ execution engines. No strategy is guaranteed to be profitable; each is a
hypothesis to be backtested and validated.

## Signal levels
`NO_SETUP (0)` · `WATCH (1)` · `POTENTIAL_SETUP (2)` · `CONFIRMED_SETUP (3)` ·
`TRADE_EXECUTED (4, execution only)`.

Every `Signal` carries: direction, entry zone, stop-loss, take-profit(s),
risk/reward, satisfied `confirmations`, `missing_confirmations`, an
`invalidation` level, market `regime`, and a transparent `confidence_score`
(0–100). **The score is a rubric, not a probability of profit.**

## Built-in strategies (`strategy_engine/strategies/`)
| Key | Name | Idea | Primary TF |
|-----|------|------|-----------|
| `trend_following` | Trend Following | EMA alignment + structure + ADX | 1h |
| `ema_pullback` | EMA Pullback | Pullback into EMA zone + rejection | 15m |
| `breakout_retest` | Breakout + Retest | Range break then retest + confirm | 15m |
| `sr_reversal` | S/R Reversal | Rejection at support/resistance | 15m |
| `mtf_confluence` | Multi-Timeframe Confluence | 4H/1H trend + 15M pullback + 5M trigger | 5m |

## Indicators (`strategy_engine/indicators.py`)
EMA, SMA, RSI, MACD, ATR, Bollinger Bands, ADX, VWAP — Wilder smoothing where
applicable, validated against reference values in the test suite.

## Market regime (`strategy_engine/regime.py`)
Nine regimes (strong/weak bull & bear, ranging, high/low volatility, breakout,
uncertain) from EMA alignment + ADX + ATR%/Bollinger width + market structure.

## Scoring (`strategy_engine/scoring.py`)
A configurable rubric summing to 100 across trend / structure / momentum /
support-resistance / entry-trigger / risk-reward / news. Bands: weak /
developing / moderate / strong / very_strong.

## Custom strategies (Strategy Builder)
Users compose AND/OR condition groups over indicators, price, constants and
time (`strategy_engine/rules.py`). Definitions are JSON-serialisable, validated,
saved to the `user_strategies` table, and appear in the Strategy Library.
Endpoint: `POST /api/strategies/custom`.

## Safety
The signal engine (`strategy_engine/engine.py`) halts ALL signal generation
when market data is stale/disconnected or required timeframe history is missing.
