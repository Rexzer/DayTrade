"""Auto-trade scheduling helpers (pure Python).

Defines the selectable scan intervals, the per-strategy interval
recommendations, and the pure scheduling primitive (``should_scan``) plus the
``AutoTradeConfig`` state object. Kept dependency-free so it is fully unit
testable offline; the async loop that USES these lives in the backend service.

Auto-trade never bypasses the risk engine, authorization or the kill switch —
it merely decides *when* to run the same user-initiated execution pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

# Selectable scan intervals offered to the operator (label -> seconds). The
# "best" interval for a strategy is the timeframe on which its entry trigger
# is confirmed: scanning faster mostly re-reads the same forming candle, while
# scanning slower risks missing the entry window.
SCAN_INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
}

DEFAULT_INTERVAL_SECONDS = SCAN_INTERVAL_SECONDS["15m"]

# Per-built-in-strategy recommended scan interval. The recommended interval is
# the strategy's entry/trigger timeframe; a faster alternative catches the
# trigger a little earlier at the cost of more evaluations and intrabar noise.
STRATEGY_RECOMMENDATIONS: dict[str, dict] = {
    "trend_following": {
        "recommended": "1h",
        "faster": "15m",
        "rationale": (
            "Signals are confirmed on 1H closes (EMA alignment + ADX + "
            "structure). Trend setups develop slowly, so a 1H scan is ideal; "
            "15m only lets you enter a forming trend slightly earlier."
        ),
    },
    "ema_pullback": {
        "recommended": "15m",
        "faster": "5m",
        "rationale": (
            "The pullback rejection candle is confirmed on the 15M close, so "
            "15m is the natural cadence. 5m can catch the rejection sooner but "
            "adds noise."
        ),
    },
    "breakout_retest": {
        "recommended": "15m",
        "faster": "5m",
        "rationale": (
            "Breakout + retest entries are time-sensitive; 15m matches the "
            "setup's confirmation, and 5m helps catch the retest tap earlier."
        ),
    },
    "sr_reversal": {
        "recommended": "15m",
        "faster": "5m",
        "rationale": (
            "Reversal rejection at a support/resistance level is confirmed on "
            "the 15M close. 5m gives an earlier trigger near the level."
        ),
    },
    "mtf_confluence": {
        "recommended": "5m",
        "faster": "1m",
        "rationale": (
            "4H and 1H set the bias slowly while the 5M candle is the actual "
            "entry trigger, so scan at 5m. 1m only shaves the trigger latency."
        ),
    },
}

# Order timeframes fastest -> slowest for the "smallest suitable timeframe"
# fallback used for custom strategies with no curated recommendation.
_TF_ORDER = ["1m", "5m", "15m", "30m", "1h", "4h"]


def interval_seconds(label: str) -> int | None:
    """Seconds for an interval label (e.g. ``"15m"`` -> 900), or None."""
    return SCAN_INTERVAL_SECONDS.get(label)


def is_valid_interval_seconds(seconds: int) -> bool:
    return seconds in SCAN_INTERVAL_SECONDS.values()


def label_for_seconds(seconds: int) -> str | None:
    for label, secs in SCAN_INTERVAL_SECONDS.items():
        if secs == seconds:
            return label
    return None


def recommend_for_strategy(key: str, suitable_timeframes: tuple | list | None = None) -> dict:
    """Recommended scan interval for a strategy.

    Uses the curated table for built-ins; for anything else, falls back to the
    smallest offered timeframe among the strategy's suitable timeframes (its
    execution cadence), defaulting to 15m when unknown.
    """
    if key in STRATEGY_RECOMMENDATIONS:
        rec = dict(STRATEGY_RECOMMENDATIONS[key])
        rec["recommended_seconds"] = interval_seconds(rec["recommended"])
        return rec
    chosen = "15m"
    if suitable_timeframes:
        offered = [tf for tf in _TF_ORDER if tf in set(suitable_timeframes)]
        if offered:
            chosen = offered[0]  # smallest = execution cadence
    return {
        "recommended": chosen,
        "faster": None,
        "rationale": (
            "Defaulted to the smallest suitable timeframe (the strategy's " "execution cadence)."
        ),
        "recommended_seconds": interval_seconds(chosen),
    }


def interval_options() -> list[dict]:
    """The selectable intervals as ``[{label, seconds}, ...]`` for the UI."""
    return [{"label": label, "seconds": secs} for label, secs in SCAN_INTERVAL_SECONDS.items()]


def should_scan(now: float, last_scan_epoch: float | None, interval_seconds: int) -> bool:
    """True if at least ``interval_seconds`` have elapsed since the last scan.

    The very first scan (no prior scan recorded) is always allowed.
    """
    if last_scan_epoch is None:
        return True
    return (now - last_scan_epoch) >= interval_seconds


@dataclass
class AutoTradeConfig:
    """In-memory auto-trade state (resets on restart -> auto disabled)."""

    enabled: bool = False
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    # None => trade the best confirmed setup across ALL strategies.
    strategy_key: str | None = None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "interval_label": label_for_seconds(self.interval_seconds),
            "strategy_key": self.strategy_key,
        }
