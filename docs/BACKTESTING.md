# Backtesting & Validation

The backtester (`backtesting/`) measures whether a strategy's historical result
survives **outside** its fitting period. It never proves future profitability.

## No look-ahead (enforced structurally)
- A signal computed on a **closed** bar is acted on at the **next** bar's open.
- A position opened on bar j+1 is only managed from bar j+2.
- The strategy only ever sees candles fully closed by the decision time
  (`Backtester._slice_context`), across all timeframes.
- When a bar spans both stop and target, the **stop** is assumed to fill first
  (pessimistic).

## Execution model
Adverse spread + slippage on every fill, commission per lot, and risk-based
position sizing to the stop distance (`CostModel`, `position_lots`). Prices are
in absolute units; `value_per_unit` is the P&L per 1.0 price move per lot.

## Metrics (`backtesting/metrics.py`)
Net/gross P&L, win/loss rate, profit factor, expectancy, average/largest win &
loss, max drawdown (abs + %), consecutive streaks, Sharpe & Sortino (per-trade,
labelled), plus equity and drawdown curves.

## Validation
- **Split** (`splitting.py`): train / validation / out-of-sample by time; date
  ranges gate *entries* only, so full lookback is retained.
- **Walk-forward** (`walkforward.py`): optimize on an in-sample window, evaluate
  on the strictly-later out-of-sample window.
- **Parameter sensitivity** (`sensitivity.py`): vary one parameter; flag
  FRAGILE strategies (sign flips / high variance).
- **Monte Carlo** (`montecarlo.py`): bootstrap the trade sequence to estimate
  ending-equity / drawdown ranges (distributions, not predictions).
- **Report** (`report.py`): PASS / WARNING / FAILED with robustness + warnings;
  fails on severe OOS deterioration or insufficient evidence.

## API
`GET /api/backtest/strategies` · `POST /api/backtest/run` ·
`POST /api/backtest/report`. Run it from the Backtesting page.

> Past performance does not guarantee future results.
