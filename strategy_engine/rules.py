"""User strategy builder — rule engine (pure Python).

Lets users compose strategies from AND/OR groups of conditions over indicators,
price, volatility, and time/session. Rules are JSON-serializable so custom
strategies persist to the database and reload without code changes.

A rule strategy produces the same explainable Signal as a built-in one and can
NEVER execute a trade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from strategy_engine.indicators import atr, ema, last_defined, macd, rsi, sma
from strategy_engine.scoring import ScoreCard
from strategy_engine.strategies import _common as C
from strategy_engine.strategy import (
    MarketContext,
    MarketRegime,
    Signal,
    Strategy,
    StrategyMetadata,
)

OPERATORS = ("gt", "lt", "gte", "lte", "eq", "cross_above", "cross_below")
_OP_SYMBOLS = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "eq": "=="}


class RuleError(ValueError):
    """Raised for malformed rule definitions."""


@dataclass
class RuleContext:
    """Precomputed inputs for evaluating rules against one timeframe."""

    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float | None]
    now_epoch: float | None = None
    _cache: dict = field(default_factory=dict)

    @classmethod
    def from_candles(cls, candles: list, now_epoch: float | None = None) -> RuleContext:
        d = C.extract(candles)
        return cls(d.opens, d.highs, d.lows, d.closes, d.volumes, now_epoch)

    def series(self, operand: dict) -> list[float | None]:
        """Return (and cache) the full series for an operand."""
        kind = operand.get("kind")
        key = repr(sorted(operand.items()))
        if key in self._cache:
            return self._cache[key]
        params = operand.get("params", {}) or {}
        if kind == "price":
            field_name = operand.get("field", "close")
            src = {
                "close": self.closes,
                "open": self.opens,
                "high": self.highs,
                "low": self.lows,
            }.get(field_name, self.closes)
            series: list[float | None] = list(src)
        elif kind == "ema":
            series = ema(self.closes, int(params.get("period", 20)))
        elif kind == "sma":
            series = sma(self.closes, int(params.get("period", 20)))
        elif kind == "rsi":
            series = rsi(self.closes, int(params.get("period", 14)))
        elif kind == "atr":
            series = atr(self.highs, self.lows, self.closes, int(params.get("period", 14)))
        elif kind == "macd":
            res = macd(self.closes)
            which = params.get("line", "macd")
            series = {"macd": res.macd, "signal": res.signal, "hist": res.histogram}.get(
                which, res.macd
            )
        elif kind in ("constant", "time_hour"):
            series = []  # scalar operands handled in value()
        else:
            raise RuleError(f"Unknown operand kind: {kind!r}")
        self._cache[key] = series
        return series

    def value(self, operand: dict, offset: int = 0) -> float | None:
        """Resolve an operand to a scalar at index ``-1-offset``."""
        kind = operand.get("kind")
        if kind == "constant":
            return float(operand.get("value", 0.0))
        if kind == "time_hour":
            if self.now_epoch is None:
                return None
            return float(datetime.fromtimestamp(self.now_epoch, tz=timezone.utc).hour)
        series = self.series(operand)
        idx = len(series) - 1 - offset
        if idx < 0 or idx >= len(series):
            return None
        return series[idx]


def _describe_operand(operand: dict) -> str:
    kind = operand.get("kind")
    params = operand.get("params", {}) or {}
    if kind == "constant":
        return str(operand.get("value"))
    if kind == "price":
        return f"price.{operand.get('field', 'close')}"
    if kind == "time_hour":
        return "hour(UTC)"
    if kind in ("ema", "sma", "rsi", "atr"):
        return f"{kind.upper()}{params.get('period', '')}"
    if kind == "macd":
        return f"MACD.{params.get('line', 'macd')}"
    return str(kind)


@dataclass
class Condition:
    left: dict
    operator: str
    right: dict

    def describe(self) -> str:
        sym = _OP_SYMBOLS.get(self.operator, self.operator)
        return f"{_describe_operand(self.left)} {sym} {_describe_operand(self.right)}"

    def evaluate(self, ctx: RuleContext) -> bool:
        if self.operator not in OPERATORS:
            raise RuleError(f"Unknown operator: {self.operator!r}")
        lv = ctx.value(self.left, 0)
        rv = ctx.value(self.right, 0)
        if lv is None or rv is None:
            return False
        if self.operator == "gt":
            return lv > rv
        if self.operator == "lt":
            return lv < rv
        if self.operator == "gte":
            return lv >= rv
        if self.operator == "lte":
            return lv <= rv
        if self.operator == "eq":
            return abs(lv - rv) < 1e-9
        # Cross operators need the previous bar too.
        lp = ctx.value(self.left, 1)
        rp = ctx.value(self.right, 1)
        if lp is None or rp is None:
            return False
        if self.operator == "cross_above":
            return lp <= rp and lv > rv
        return lp >= rp and lv < rv  # cross_below

    def to_dict(self) -> dict:
        return {
            "type": "condition",
            "left": self.left,
            "operator": self.operator,
            "right": self.right,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Condition:
        return cls(left=d["left"], operator=d["operator"], right=d["right"])


@dataclass
class ConditionGroup:
    logic: str  # "and" | "or"
    children: list  # list of Condition | ConditionGroup

    def evaluate(self, ctx: RuleContext) -> bool:
        results = [child.evaluate(ctx) for child in self.children]
        if not results:
            return False
        return all(results) if self.logic == "and" else any(results)

    def leaves(self) -> list[Condition]:
        out: list[Condition] = []
        for child in self.children:
            if isinstance(child, ConditionGroup):
                out.extend(child.leaves())
            else:
                out.append(child)
        return out

    def evaluate_leaves(self, ctx: RuleContext) -> list[tuple[str, bool]]:
        return [(leaf.describe(), leaf.evaluate(ctx)) for leaf in self.leaves()]

    def to_dict(self) -> dict:
        return {
            "type": "group",
            "logic": self.logic,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConditionGroup:
        if d.get("type") != "group":
            raise RuleError("Expected a group node.")
        logic = d.get("logic", "and")
        if logic not in ("and", "or"):
            raise RuleError(f"Invalid logic: {logic!r}")
        children = []
        for child in d.get("children", []):
            if child.get("type") == "group":
                children.append(ConditionGroup.from_dict(child))
            else:
                children.append(Condition.from_dict(child))
        return cls(logic=logic, children=children)


class RuleStrategy(Strategy):
    """A user-defined strategy driven by AND/OR condition groups."""

    def __init__(
        self,
        *,
        key: str,
        name: str,
        description: str,
        timeframe: str = "15m",
        long_rules: ConditionGroup | None = None,
        short_rules: ConditionGroup | None = None,
        suitable_regimes: tuple[MarketRegime, ...] = (),
    ) -> None:
        self.timeframe = timeframe
        self.long_rules = long_rules
        self.short_rules = short_rules
        self.metadata = StrategyMetadata(
            key=key,
            name=name,
            description=description,
            suitable_timeframes=(timeframe,),
            suitable_regimes=suitable_regimes,
            indicators=("user-defined",),
            entry_conditions=tuple(
                leaf.describe() for leaf in (long_rules.leaves() if long_rules else [])
            ),
            invalidation_logic="Rule conditions no longer satisfied.",
            is_builtin=False,
        )

    def evaluate(self, context: MarketContext) -> Signal:
        candles = context.candles.get(self.timeframe) or []
        if len(candles) < 30:
            return C.no_setup(self.key, self.timeframe, "Insufficient history for custom rules.")
        ctx = RuleContext.from_candles(candles, context.now_epoch)
        d = C.extract(candles)
        price = d.closes[-1]
        atr_val = last_defined(atr(d.highs, d.lows, d.closes, 14)) or (price * 0.003)

        long_leaves = self.long_rules.evaluate_leaves(ctx) if self.long_rules else []
        short_leaves = self.short_rules.evaluate_leaves(ctx) if self.short_rules else []
        long_true = self.long_rules.evaluate(ctx) if self.long_rules else False
        short_true = self.short_rules.evaluate(ctx) if self.short_rules else False

        def _frac(leaves: list[tuple[str, bool]]) -> float:
            return (sum(1 for _, ok in leaves if ok) / len(leaves)) if leaves else 0.0

        if long_true or (
            not short_true and _frac(long_leaves) >= _frac(short_leaves) and long_leaves
        ):
            direction = "long"
            leaves = long_leaves
            group_true = long_true
            stop = price - 1.0 * atr_val
            targets = C.build_targets(price, stop, "long")
            entry_zone = (price - 0.2 * atr_val, price)
        elif short_leaves:
            direction = "short"
            leaves = short_leaves
            group_true = short_true
            stop = price + 1.0 * atr_val
            targets = C.build_targets(price, stop, "short")
            entry_zone = (price, price + 0.2 * atr_val)
        else:
            return C.no_setup(self.key, self.timeframe, "No rules matched.")

        score = ScoreCard()
        score.award("entry_trigger", _frac(leaves), "custom rule match fraction")
        score.award("trend", _frac(leaves), "rule-derived")
        rr = C.risk_reward(price, stop, targets[0]) if targets else None
        score.award("risk_reward", 1.0 if (rr and rr >= 1.5) else 0.4, f"R:R={rr}")

        # Treat the whole group as core conditions; level derives from fraction.
        core = leaves
        confirmations: list[tuple[str, bool]] = []
        if group_true:
            # Force a confirmed level by marking all core met (they are).
            core = [(label, True) for label, _ in leaves]

        return C.finalize(
            strategy_key=self.key,
            timeframe=self.timeframe,
            direction=direction,
            regime=MarketRegime.UNKNOWN,
            core=core,
            confirmations=confirmations,
            entry_zone=entry_zone,
            stop_loss=stop,
            take_profits=targets,
            invalidation="Custom rule conditions no longer satisfied.",
            score=score,
            notes="User-defined strategy." if not group_true else None,
        )

    # --------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        return {
            "key": self.metadata.key,
            "name": self.metadata.name,
            "description": self.metadata.description,
            "timeframe": self.timeframe,
            "long_rules": self.long_rules.to_dict() if self.long_rules else None,
            "short_rules": self.short_rules.to_dict() if self.short_rules else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RuleStrategy:
        if not d.get("key") or not d.get("name"):
            raise RuleError("Custom strategy requires 'key' and 'name'.")
        long_rules = ConditionGroup.from_dict(d["long_rules"]) if d.get("long_rules") else None
        short_rules = ConditionGroup.from_dict(d["short_rules"]) if d.get("short_rules") else None
        if long_rules is None and short_rules is None:
            raise RuleError("Custom strategy needs at least one of long_rules/short_rules.")
        return cls(
            key=d["key"],
            name=d["name"],
            description=d.get("description", ""),
            timeframe=d.get("timeframe", "15m"),
            long_rules=long_rules,
            short_rules=short_rules,
        )


def validate_rule_dict(d: dict) -> list[str]:
    """Return a list of validation errors for a custom-strategy definition."""
    errors: list[str] = []
    try:
        RuleStrategy.from_dict(d)
    except RuleError as exc:
        errors.append(str(exc))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Invalid rule structure: {exc}")
    return errors
