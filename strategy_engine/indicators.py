"""Technical indicator engine (pure Python, no third-party deps).

All functions take plain lists of floats and return lists aligned to the input
length, using ``None`` during the warm-up period so callers can index by bar.
Smoothing conventions follow the widely-used reference implementations:

    * RSI, ATR, ADX use Wilder's smoothing (RMA), matching most charting
      platforms (TradingView, MT4/MT5).
    * EMA is seeded with the SMA of the first ``period`` values.
    * MACD = EMA(fast) - EMA(slow); signal = EMA of the MACD line.

These are validated against known reference values in the test suite.
"""

from __future__ import annotations

from dataclasses import dataclass


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average."""
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average, seeded with the SMA of the first ``period``."""
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def _wilder_rma(values: list[float], period: int) -> list[float | None]:
    """Wilder's running moving average (used by RSI/ATR/ADX)."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index using Wilder's smoothing."""
    if period <= 0:
        raise ValueError("period must be > 0")
    n = len(values)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        change = values[i] - values[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)

    # First average gain/loss = simple mean over the first `period` changes.
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    def _rsi_from(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = _rsi_from(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


@dataclass(frozen=True)
class MACDResult:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> MACDResult:
    """MACD line, signal line and histogram."""
    if fast >= slow:
        raise ValueError("fast period must be < slow period")
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    n = len(values)
    macd_line: list[float | None] = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # Signal line = EMA of the (defined portion of the) MACD line.
    defined = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_line: list[float | None] = [None] * n
    hist: list[float | None] = [None] * n
    if len(defined) >= signal:
        seq = [v for _, v in defined]
        sig_seq = ema(seq, signal)
        for offset, (idx, _) in enumerate(defined):
            if sig_seq[offset] is not None:
                signal_line[idx] = sig_seq[offset]
                hist[idx] = macd_line[idx] - sig_seq[offset]
    return MACDResult(macd=macd_line, signal=signal_line, histogram=hist)


def true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """Per-bar True Range (first bar uses high-low)."""
    n = len(closes)
    tr = [0.0] * n
    if n == 0:
        return tr
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    return tr


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float | None]:
    """Average True Range using Wilder's smoothing."""
    tr = true_range(highs, lows, closes)
    return _wilder_rma(tr, period)


@dataclass(frozen=True)
class BollingerResult:
    middle: list[float | None]
    upper: list[float | None]
    lower: list[float | None]


def bollinger_bands(values: list[float], period: int = 20, num_std: float = 2.0) -> BollingerResult:
    """Bollinger Bands (population standard deviation, matching most platforms)."""
    n = len(values)
    mid = sma(values, period)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = mid[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = variance**0.5
        upper[i] = mean + num_std * sd
        lower[i] = mean - num_std * sd
    return BollingerResult(middle=mid, upper=upper, lower=lower)


@dataclass(frozen=True)
class ADXResult:
    adx: list[float | None]
    plus_di: list[float | None]
    minus_di: list[float | None]


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> ADXResult:
    """Average Directional Index with +DI/-DI (Wilder)."""
    n = len(closes)
    out_adx: list[float | None] = [None] * n
    out_pdi: list[float | None] = [None] * n
    out_mdi: list[float | None] = [None] * n
    if n <= period:
        return ADXResult(out_adx, out_pdi, out_mdi)

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = true_range(highs, lows, closes)
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0

    # Wilder-smoothed sums.
    def _smooth(series: list[float]) -> list[float | None]:
        sm: list[float | None] = [None] * n
        first = sum(series[1 : period + 1])
        sm[period] = first
        prev = first
        for i in range(period + 1, n):
            prev = prev - (prev / period) + series[i]
            sm[i] = prev
        return sm

    tr_s = _smooth(tr)
    pdm_s = _smooth(plus_dm)
    mdm_s = _smooth(minus_dm)

    dx: list[float | None] = [None] * n
    for i in range(period, n):
        if tr_s[i] and tr_s[i] != 0:
            pdi = 100.0 * (pdm_s[i] / tr_s[i])
            mdi = 100.0 * (mdm_s[i] / tr_s[i])
            out_pdi[i] = pdi
            out_mdi[i] = mdi
            denom = pdi + mdi
            dx[i] = 100.0 * abs(pdi - mdi) / denom if denom != 0 else 0.0

    # ADX = Wilder RMA of DX, starting after the first `period` DX values.
    first_dx_idx = period
    dx_defined = [dx[i] for i in range(first_dx_idx, n) if dx[i] is not None]
    if len(dx_defined) >= period:
        seed = sum(dx_defined[:period]) / period
        adx_start = first_dx_idx + period - 1
        out_adx[adx_start] = seed
        prev = seed
        for i in range(adx_start + 1, n):
            if dx[i] is not None:
                prev = (prev * (period - 1) + dx[i]) / period
                out_adx[i] = prev
    return ADXResult(out_adx, out_pdi, out_mdi)


def vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float | None],
) -> list[float | None]:
    """Volume-Weighted Average Price (cumulative).

    Requires volume. If any volume is missing/zero for the whole series the
    result is ``None`` (we never fabricate a VWAP without volume).
    """
    n = len(closes)
    out: list[float | None] = [None] * n
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(n):
        v = volumes[i] if i < len(volumes) else None
        if v is None:
            # Missing volume breaks the cumulative calc; skip this bar.
            out[i] = (cum_pv / cum_v) if cum_v > 0 else None
            continue
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        cum_pv += typical * v
        cum_v += v
        out[i] = (cum_pv / cum_v) if cum_v > 0 else None
    return out


def last_defined(series: list[float | None]) -> float | None:
    """Return the last non-None value in a series (convenience for strategies)."""
    for v in reversed(series):
        if v is not None:
            return v
    return None
