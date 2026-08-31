"""Train / validation / out-of-sample splitting (pure Python).

Splits the timeline chronologically. Crucially, the full candle history is
always available for indicator warm-up; only the ENTRY window differs per
segment (enforced by the backtester's date range). This prevents the optimizer
from ever using future data while still giving each segment proper lookback.
"""

from __future__ import annotations

from dataclasses import replace

from backtesting.config import BacktestConfig
from backtesting.engine import Backtester, BacktestResult


def compute_windows(
    candles_by_tf: dict[str, list],
    primary_tf: str,
    *,
    train: float = 0.5,
    validation: float = 0.25,
) -> dict[str, tuple[float, float]]:
    """Return {'train'|'validation'|'oos': (start_epoch, end_epoch)} by time."""
    prim = candles_by_tf.get(primary_tf, [])
    n = len(prim)
    if n < 4:
        raise ValueError("Not enough primary candles to split.")
    i_train = max(1, int(n * train))
    i_val = max(i_train + 1, int(n * (train + validation)))
    i_val = min(i_val, n - 1)

    def window(a: int, b: int) -> tuple[float, float]:
        return (prim[a].open_time_epoch, prim[b - 1].open_time_epoch)

    return {
        "train": window(0, i_train),
        "validation": window(i_train, i_val),
        "oos": window(i_val, n),
    }


def run_window(
    strategy,
    base_config: BacktestConfig,
    candles_by_tf: dict[str, list],
    window: tuple[float, float],
) -> BacktestResult:
    """Run a backtest whose ENTRIES are restricted to ``window`` (full lookback)."""
    cfg = replace(base_config, start_epoch=window[0], end_epoch=window[1])
    return Backtester(strategy, cfg).run(candles_by_tf)


def run_all_segments(
    strategy,
    base_config: BacktestConfig,
    candles_by_tf: dict[str, list],
    *,
    train: float = 0.5,
    validation: float = 0.25,
) -> dict[str, BacktestResult]:
    windows = compute_windows(
        candles_by_tf, base_config.primary_timeframe, train=train, validation=validation
    )
    return {
        name: run_window(strategy, base_config, candles_by_tf, w) for name, w in windows.items()
    }
