"""Strategy plug-in interface and shared trading vocabulary (pure Python)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class SignalLevel(int, Enum):
    """Signal levels — deliberately separate 'observation' from 'execution'.

    A LEVEL_2/LEVEL_3 signal is NOT an executed trade. Only LEVEL_4 means an
    order was actually placed (which cannot happen in Phase 1).
    """

    NO_SETUP = 0
    WATCH = 1
    POTENTIAL_SETUP = 2
    CONFIRMED_SETUP = 3
    TRADE_EXECUTED = 4


class MarketRegime(str, Enum):
    """Market regime classification (populated by Phase 2 detectors)."""

    STRONG_BULLISH = "strong_bullish"
    WEAK_BULLISH = "weak_bullish"
    STRONG_BEARISH = "strong_bearish"
    WEAK_BEARISH = "weak_bearish"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StrategyMetadata:
    """Static description of a strategy (shown in the Strategies UI)."""

    key: str
    name: str
    description: str
    suitable_timeframes: tuple[str, ...] = ()
    suitable_regimes: tuple[MarketRegime, ...] = ()
    indicators: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "suitable_timeframes": list(self.suitable_timeframes),
            "suitable_regimes": [r.value for r in self.suitable_regimes],
            "indicators": list(self.indicators),
        }


@dataclass(frozen=True)
class Signal:
    """A transparent, explainable signal.

    Every field that justifies the signal is explicit. Reasoning is never
    hidden: ``confirmations``/``missing_confirmations``/``invalidation`` are
    first-class. Prices are ``None`` until a real setup exists.
    """

    strategy_key: str
    level: SignalLevel
    regime: MarketRegime = MarketRegime.UNKNOWN
    timeframe: str | None = None
    direction: str | None = None  # "long" | "short" | None
    entry_zone: tuple[float, float] | None = None
    stop_loss: float | None = None
    take_profits: tuple[float, ...] = ()
    risk_reward: float | None = None
    confirmations: tuple[str, ...] = ()
    missing_confirmations: tuple[str, ...] = ()
    invalidation: str | None = None
    confidence_score: int | None = None  # 0-100, transparent rubric (Phase 2)
    notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "level": self.level.value,
            "level_name": self.level.name,
            "regime": self.regime.value,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "entry_zone": list(self.entry_zone) if self.entry_zone else None,
            "stop_loss": self.stop_loss,
            "take_profits": list(self.take_profits),
            "risk_reward": self.risk_reward,
            "confirmations": list(self.confirmations),
            "missing_confirmations": list(self.missing_confirmations),
            "invalidation": self.invalidation,
            "confidence_score": self.confidence_score,
            "notes": self.notes,
        }


class Strategy(ABC):
    """Common interface every strategy (built-in or user-created) implements.

    The lifecycle mirrors the platform's philosophy: detect regime → detect
    setup → confirm → derive entry/stop/target. Phase 1 defines the contract;
    Phase 2 provides concrete implementations.
    """

    metadata: StrategyMetadata

    @abstractmethod
    def evaluate(self, context: MarketContext) -> Signal:
        """Evaluate the current market and return an explainable Signal."""

    @property
    def key(self) -> str:
        return self.metadata.key


@dataclass
class MarketContext:
    """Inputs handed to a strategy at evaluation time.

    Phase 1 keeps this minimal; Phase 2 enriches it with indicator series,
    multi-timeframe candles, news windows, etc. It is defined now so the
    interface is stable.
    """

    symbol: str = "XAUUSD"
    candles: dict[str, list] = field(default_factory=dict)  # timeframe -> candles
    now_epoch: float | None = None
