"""Market-structure analysis (pure Python).

Detects swing points, higher-high/higher-low (and lower-high/lower-low)
sequences, and clusters swing points into support/resistance zones. These are
the building blocks strategies use to reason about structure transparently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str  # "high" | "low"


def swing_points(
    highs: list[float], lows: list[float], left: int = 2, right: int = 2
) -> list[SwingPoint]:
    """Return fractal swing highs/lows.

    A swing high at ``i`` is a bar whose high is >= the ``left`` bars before and
    > the ``right`` bars after (strict on the right to avoid duplicates). Swing
    lows are the mirror.
    """
    n = len(highs)
    points: list[SwingPoint] = []
    for i in range(left, n - right):
        window_h = highs[i - left : i + right + 1]
        window_l = lows[i - left : i + right + 1]
        if highs[i] == max(window_h) and highs[i] > max(
            highs[i + 1 : i + right + 1] or [float("-inf")]
        ):
            points.append(SwingPoint(i, highs[i], "high"))
        elif lows[i] == min(window_l) and lows[i] < min(
            lows[i + 1 : i + right + 1] or [float("inf")]
        ):
            points.append(SwingPoint(i, lows[i], "low"))
    return points


@dataclass(frozen=True)
class StructureResult:
    trend: str  # "bullish" | "bearish" | "neutral"
    higher_highs: bool
    higher_lows: bool
    lower_highs: bool
    lower_lows: bool
    last_swing_high: float | None
    last_swing_low: float | None


def analyze_structure(
    highs: list[float], lows: list[float], left: int = 2, right: int = 2
) -> StructureResult:
    """Classify structure from the two most recent swing highs and lows."""
    points = swing_points(highs, lows, left, right)
    sh = [p for p in points if p.kind == "high"]
    sl = [p for p in points if p.kind == "low"]

    hh = len(sh) >= 2 and sh[-1].price > sh[-2].price
    lh = len(sh) >= 2 and sh[-1].price < sh[-2].price
    hl = len(sl) >= 2 and sl[-1].price > sl[-2].price
    ll = len(sl) >= 2 and sl[-1].price < sl[-2].price

    if hh and hl:
        trend = "bullish"
    elif lh and ll:
        trend = "bearish"
    else:
        trend = "neutral"

    return StructureResult(
        trend=trend,
        higher_highs=hh,
        higher_lows=hl,
        lower_highs=lh,
        lower_lows=ll,
        last_swing_high=sh[-1].price if sh else None,
        last_swing_low=sl[-1].price if sl else None,
    )


@dataclass(frozen=True)
class Level:
    price: float
    touches: int
    kind: str  # "support" | "resistance"


def support_resistance(
    highs: list[float],
    lows: list[float],
    *,
    left: int = 2,
    right: int = 2,
    tolerance_pct: float = 0.0015,
    max_levels: int = 6,
) -> list[Level]:
    """Cluster swing points into support/resistance zones.

    Swing highs cluster into resistance, swing lows into support. Zones within
    ``tolerance_pct`` of each other are merged; ``touches`` counts members.
    """
    points = swing_points(highs, lows, left, right)
    highs_p = sorted(p.price for p in points if p.kind == "high")
    lows_p = sorted(p.price for p in points if p.kind == "low")

    def _cluster(prices: list[float], kind: str) -> list[Level]:
        clusters: list[list[float]] = []
        for price in prices:
            if clusters and abs(price - clusters[-1][-1]) / max(price, 1e-9) <= tolerance_pct:
                clusters[-1].append(price)
            else:
                clusters.append([price])
        levels = [Level(price=sum(c) / len(c), touches=len(c), kind=kind) for c in clusters]
        # Strongest (most touches) first.
        return sorted(levels, key=lambda level: level.touches, reverse=True)

    res = _cluster(highs_p, "resistance") + _cluster(lows_p, "support")
    res.sort(key=lambda level: level.touches, reverse=True)
    return res[:max_levels]


def nearest_level(levels: list[Level], price: float, kind: str) -> Level | None:
    """Return the nearest support (below) or resistance (above) to ``price``."""
    if kind == "support":
        candidates = [level for level in levels if level.kind == "support" and level.price <= price]
        return max(candidates, key=lambda level: level.price) if candidates else None
    candidates = [level for level in levels if level.kind == "resistance" and level.price >= price]
    return min(candidates, key=lambda level: level.price) if candidates else None
