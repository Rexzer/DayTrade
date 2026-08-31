"""Alert generation from signal transitions (pure Python).

Emits alerts when a strategy's signal level changes in a meaningful way:
    * rises to WATCH / POTENTIAL_SETUP / CONFIRMED_SETUP
    * an active setup (>= POTENTIAL) becomes INVALIDATED (drops back down)

The AlertManager is stateful (remembers the previous level per strategy) but
pure — no I/O. Delivery channels (browser/desktop/email/…) are wired later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from strategy_engine.strategy import SignalLevel

_LEVEL_LABELS = {
    SignalLevel.WATCH: "WATCH",
    SignalLevel.POTENTIAL_SETUP: "POTENTIAL SETUP",
    SignalLevel.CONFIRMED_SETUP: "CONFIRMED SETUP",
}


@dataclass
class Alert:
    strategy_key: str
    strategy_name: str
    kind: str  # WATCH | POTENTIAL SETUP | CONFIRMED SETUP | INVALIDATED SETUP
    direction: str | None
    message: str
    timeframe: str | None = None
    entry_zone: list | None = None
    stop_loss: float | None = None
    take_profits: list | None = None
    risk_reward: float | None = None
    timestamp_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "kind": self.kind,
            "direction": self.direction,
            "message": self.message,
            "timeframe": self.timeframe,
            "entry_zone": self.entry_zone,
            "stop_loss": self.stop_loss,
            "take_profits": self.take_profits,
            "risk_reward": self.risk_reward,
            "timestamp_epoch": self.timestamp_epoch,
        }


class AlertManager:
    def __init__(self, max_history: int = 100) -> None:
        self._prev_level: dict[str, int] = {}
        self._history: list[Alert] = []
        self._max = max_history

    def process(self, signal: dict, *, now_epoch: float | None = None) -> Alert | None:
        """Compare a signal to the strategy's previous level; emit if changed."""
        key = signal.get("strategy_key")
        if key is None:
            return None
        level = int(signal.get("level", 0))
        prev = self._prev_level.get(key, 0)
        self._prev_level[key] = level
        if level == prev:
            return None

        name = signal.get("strategy_name", key)
        direction = signal.get("direction")
        ts = time.time() if now_epoch is None else now_epoch

        alert: Alert | None = None
        if level > prev and level in (v.value for v in _LEVEL_LABELS):
            kind = _LEVEL_LABELS[SignalLevel(level)]
            met = signal.get("confirmations", []) or []
            missing = signal.get("missing_confirmations", []) or []
            reason = f"{len(met)}/{len(met) + len(missing)} conditions satisfied."
            alert = Alert(
                strategy_key=key,
                strategy_name=name,
                kind=kind,
                direction=direction,
                message=f"XAUUSD {(direction or '').upper()} — {kind}. {reason}".strip(),
                timeframe=signal.get("timeframe"),
                entry_zone=signal.get("entry_zone"),
                stop_loss=signal.get("stop_loss"),
                take_profits=signal.get("take_profits"),
                risk_reward=signal.get("risk_reward"),
                timestamp_epoch=ts,
            )
        elif prev >= SignalLevel.POTENTIAL_SETUP.value and level < prev:
            alert = Alert(
                strategy_key=key,
                strategy_name=name,
                kind="INVALIDATED SETUP",
                direction=direction,
                message=f"XAUUSD {name} setup weakened/invalidated.",
                timeframe=signal.get("timeframe"),
                timestamp_epoch=ts,
            )

        if alert is not None:
            self._history.append(alert)
            if len(self._history) > self._max:
                self._history = self._history[-self._max :]
        return alert

    def process_many(self, signals: list[dict], *, now_epoch: float | None = None) -> list[Alert]:
        out = []
        for s in signals:
            a = self.process(s, now_epoch=now_epoch)
            if a is not None:
                out.append(a)
        return out

    def recent(self, limit: int = 20) -> list[dict]:
        return [a.to_dict() for a in self._history[-limit:][::-1]]
