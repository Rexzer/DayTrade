"""Event-driven backtester (pure Python) with strict no-look-ahead.

Anti-leakage design (critical):
    * At each primary bar, the strategy is evaluated on a MarketContext that
      contains ONLY candles fully closed by that bar's close time — across all
      timeframes. It can never see the current forming bar or any future bar.
    * A signal produced at the close of bar j is acted upon at the OPEN of bar
      j+1 (next-bar execution). No intrabar future prices are used to decide.
    * A position opened on bar j+1 is only managed from bar j+2 onward.
    * When both stop and target fall inside the same bar, the STOP is assumed
      to fill first (pessimistic), avoiding optimistic bias.

The result is fully reproducible for a given (strategy, candles, config).
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

from backtesting.config import BacktestConfig
from backtesting.execution import CostModel, position_lots
from backtesting.trade import OpenPosition, Trade
from market_data.provider import Timeframe
from market_data.timeframes import duration_seconds
from strategy_engine.strategy import MarketContext, Strategy


@dataclass
class BacktestResult:
    strategy_key: str
    config: dict
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[float, float]] = field(default_factory=list)
    starting_capital: float = 10_000.0
    ending_capital: float = 10_000.0
    bars_processed: int = 0
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "config": self.config,
            "starting_capital": self.starting_capital,
            "ending_capital": round(self.ending_capital, 2),
            "bars_processed": self.bars_processed,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [{"time": t, "equity": round(e, 2)} for t, e in self.equity_curve],
            "metrics": self.metrics,
        }


def _tf_duration(tf: str) -> int:
    return duration_seconds(Timeframe(tf))


class Backtester:
    def __init__(self, strategy: Strategy, config: BacktestConfig | None = None) -> None:
        self.strategy = strategy
        self.config = config or BacktestConfig()
        self.cost = CostModel(
            spread=self.config.spread,
            slippage=self.config.slippage,
            commission_per_lot=self.config.commission_per_lot,
            value_per_unit=self.config.value_per_unit,
        )

    # --------------------------------------------------------------- slicing
    def _prepare(self, candles_by_tf: dict[str, list]) -> dict[str, list[float]]:
        """Return {tf: [open_time,...]} for fast no-look-ahead slicing."""
        return {tf: [c.open_time_epoch for c in cs] for tf, cs in candles_by_tf.items()}

    def _slice_context(
        self,
        candles_by_tf: dict[str, list],
        open_times: dict[str, list[float]],
        decision_time: float,
    ) -> MarketContext:
        """Build a context containing only bars fully closed by decision_time."""
        sliced: dict[str, list] = {}
        for tf, cs in candles_by_tf.items():
            dur = _tf_duration(tf)
            # keep candles whose close (open_time + dur) <= decision_time
            cutoff = decision_time - dur
            idx = bisect_right(open_times[tf], cutoff)
            sliced[tf] = cs[:idx]
        return MarketContext(symbol="XAUUSD", candles=sliced, now_epoch=decision_time)

    # --------------------------------------------------------------- run
    def run(self, candles_by_tf: dict[str, list]) -> BacktestResult:
        cfg = self.config
        tf = cfg.primary_timeframe
        # Full history is always kept for indicator warm-up/context; the date
        # range restricts only which bars may OPEN a trade (leakage-free
        # sub-period testing — see _in_window).
        primary = candles_by_tf.get(tf, [])
        work = dict(candles_by_tf)
        open_times = self._prepare(work)
        dur = _tf_duration(tf)

        result = BacktestResult(
            strategy_key=self.strategy.key,
            config=cfg.to_dict(),
            starting_capital=cfg.starting_capital,
            ending_capital=cfg.starting_capital,
        )
        n = len(primary)
        if n <= cfg.warmup_bars + 2:
            result.equity_curve.append(
                (primary[0].open_time_epoch if primary else 0.0, cfg.starting_capital)
            )
            result.metrics = {}
            return result

        equity = cfg.starting_capital
        position: OpenPosition | None = None
        pending: dict | None = None  # {"direction","stop","tp"}
        entry_equity = equity

        result.equity_curve.append((primary[cfg.warmup_bars].open_time_epoch, equity))

        for j in range(cfg.warmup_bars, n):
            bar = primary[j]

            # 1) Manage an already-open position against THIS bar (entered <= j-1).
            if position is not None and position.entry_index < j:
                exit_price, reason = self._check_exit(position, bar)
                if exit_price is not None:
                    trade, equity = self._close(
                        position, bar, exit_price, reason, equity, entry_equity, j
                    )
                    result.trades.append(trade)
                    position = None

            # 2) Execute a pending entry at THIS bar's open (next-bar execution).
            if position is None and pending is not None:
                position, entry_equity = self._open(pending, bar, equity, j)
                pending = None

            # 3) While flat and inside the trading window, evaluate for a NEW
            #    signal to act on next bar.
            if position is None and self._in_window(bar.open_time_epoch):
                decision_time = bar.open_time_epoch + dur  # this bar's close
                ctx = self._slice_context(work, open_times, decision_time)
                signal = self.strategy.evaluate(ctx)
                pending = self._signal_to_entry(signal, bar)
            elif position is None:
                pending = None

            # Mark-to-market equity at bar close.
            mtm = equity
            if position is not None:
                mtm = equity + position.unrealized(bar.close, cfg.value_per_unit)
            result.equity_curve.append((bar.open_time_epoch + dur, mtm))

        # Close any residual position at the last close.
        if position is not None:
            last = primary[-1]
            exit_fill = self.cost.exit_fill(position.direction, last.close)
            trade, equity = self._finalize_close(
                position, last, exit_fill, "end_of_data", equity, entry_equity, n - 1
            )
            result.trades.append(trade)

        result.ending_capital = equity
        result.bars_processed = n - cfg.warmup_bars
        from backtesting.metrics import compute_metrics

        result.metrics = compute_metrics(
            result.trades,
            result.equity_curve,
            cfg.starting_capital,
            risk_free_rate=cfg.risk_free_rate,
        )
        return result

    # --------------------------------------------------------------- helpers
    def _in_window(self, open_time: float) -> bool:
        cfg = self.config
        if cfg.start_epoch is not None and open_time < cfg.start_epoch:
            return False
        if cfg.end_epoch is not None and open_time > cfg.end_epoch:
            return False
        return True

    def _signal_to_entry(self, signal, bar) -> dict | None:
        cfg = self.config
        if signal.level.value < cfg.min_signal_level:
            return None
        direction = signal.direction
        if direction == "long" and not cfg.allow_long:
            return None
        if direction == "short" and not cfg.allow_short:
            return None
        if direction not in ("long", "short"):
            return None
        if signal.stop_loss is None or not signal.take_profits:
            return None
        return {"direction": direction, "stop": signal.stop_loss, "tp": signal.take_profits[0]}

    def _passes_filters(self, entry_time: float) -> bool:
        cfg = self.config
        if cfg.session is not None:
            from datetime import datetime, timezone

            hour = datetime.fromtimestamp(entry_time, tz=timezone.utc).hour
            if not cfg.session.allows(hour):
                return False
        for start, end in cfg.news_blackout_epochs:
            if start <= entry_time <= end:
                return False
        return True

    def _open(self, pending: dict, bar, equity: float, j: int):
        cfg = self.config
        entry_open = bar.open
        direction = pending["direction"]
        stop = pending["stop"]
        tp = pending["tp"]

        # Validate geometry against the actual entry (next-bar open).
        if direction == "long" and not (stop < entry_open < tp):
            return None, equity
        if direction == "short" and not (tp < entry_open < stop):
            return None, equity
        if not self._passes_filters(bar.open_time_epoch):
            return None, equity

        fill = self.cost.entry_fill(direction, entry_open)
        lots = position_lots(
            equity, cfg.risk_per_trade_pct, fill, stop, cfg.value_per_unit, cfg.max_lot_size
        )
        if lots <= 0:
            return None, equity
        pos = OpenPosition(
            strategy_key=self.strategy.key,
            direction=direction,
            entry_time=bar.open_time_epoch,
            entry_price=fill,
            stop_loss=stop,
            take_profit=tp,
            lots=lots,
            entry_index=j,
        )
        return pos, equity

    def _check_exit(self, pos: OpenPosition, bar):
        """Return (intended_exit_price, reason) or (None, None). Stop wins ties."""
        if pos.direction == "long":
            hit_stop = bar.low <= pos.stop_loss
            hit_tp = pos.take_profit is not None and bar.high >= pos.take_profit
            if hit_stop:
                return pos.stop_loss, "stop_loss"
            if hit_tp:
                return pos.take_profit, "take_profit"
        else:
            hit_stop = bar.high >= pos.stop_loss
            hit_tp = pos.take_profit is not None and bar.low <= pos.take_profit
            if hit_stop:
                return pos.stop_loss, "stop_loss"
            if hit_tp:
                return pos.take_profit, "take_profit"
        return None, None

    def _close(self, pos, bar, intended_exit, reason, equity, entry_equity, j):
        exit_fill = self.cost.exit_fill(pos.direction, intended_exit)
        return self._finalize_close(pos, bar, exit_fill, reason, equity, entry_equity, j)

    def _finalize_close(self, pos, bar, exit_fill, reason, equity, entry_equity, j):
        pnl = self.cost.net_pnl(pos.direction, pos.entry_price, exit_fill, pos.lots)
        new_equity = equity + pnl
        trade = Trade(
            strategy_key=pos.strategy_key,
            direction=pos.direction,
            entry_time=pos.entry_time,
            exit_time=bar.open_time_epoch,
            entry_price=pos.entry_price,
            exit_price=exit_fill,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            lots=pos.lots,
            pnl=pnl,
            return_pct=(pnl / entry_equity) if entry_equity else 0.0,
            exit_reason=reason,
            bars_held=max(0, j - pos.entry_index),
        )
        return trade, new_equity
