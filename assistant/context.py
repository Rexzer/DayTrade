"""Snapshot of all data the assistant is allowed to use (pure Python).

Every field is optional and holds already-serialized, JSON-ready data taken
from the running platform. The assistant reads ONLY these fields — if a field
is ``None`` (or empty) the corresponding answer must report insufficient data
rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AssistantContext:
    # Market data (from the market service snapshot).
    market: dict | None = None  # {connected, bid, ask, last, spread, source, data_status}
    regime: dict | None = None  # {regime, trend, strength, volatility, details}
    mtf: list[dict] | None = None  # [{timeframe, trend, structure, momentum, signal_state}]

    # Strategy / signal engine.
    signals: list[dict] | None = None  # current signals with full reasoning
    signals_allowed: bool = False
    signals_reason: str | None = None
    alerts: list[dict] | None = None

    # Trading history / performance (paper or live).
    trades: list[dict] | None = None
    performance: dict | None = None  # {overall, by_strategy}

    # Risk engine.
    risk_state: dict | None = None
    risk_settings: dict | None = None

    # Execution log (for "why was this trade rejected/executed").
    execution_log: list[dict] | None = None

    # News + system health.
    news: dict | None = None
    health: dict | None = None

    now_epoch: float | None = None
    extra: dict = field(default_factory=dict)
