"""Paper-trading engine (pure Python) — simulated execution on live data.

Drives a virtual account from price updates and strategy signals. It simulates
market/limit/stop orders, stop-loss / take-profit, partial exits and trailing
stops with realistic (adverse) fills, and enforces risk limits. It records a
full journal and cleanly distinguishes a SIGNAL from an executed TRADE.

CRITICAL: this engine can never place a real order. Every "fill" is simulated.
"""

from __future__ import annotations

from dataclasses import dataclass

from paper_trading.account import PaperAccount
from paper_trading.config import PaperAccountConfig
from paper_trading.execution import PaperCostModel, position_lots
from paper_trading.journal import PaperJournal
from paper_trading.models import (
    JournalEntry,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperOrder,
    PaperPosition,
    PaperTradeRecord,
)
from paper_trading.performance import overall_performance, performance_by_strategy
from strategy_engine.strategy import SignalLevel


@dataclass
class SignalDecision:
    executed: bool
    reason: str
    position_id: str | None = None

    def to_dict(self) -> dict:
        return {"executed": self.executed, "reason": self.reason, "position_id": self.position_id}


class PaperTradingEngine:
    def __init__(self, config: PaperAccountConfig | None = None) -> None:
        self.config = config or PaperAccountConfig()
        self.account = PaperAccount(self.config)
        self.journal = PaperJournal()
        self._cost = self._make_cost()
        self.last_bid: float | None = None
        self.last_ask: float | None = None
        self.last_mid: float | None = None
        self.last_epoch: float = 0.0

    def _make_cost(self) -> PaperCostModel:
        c = self.config
        return PaperCostModel(
            spread=c.spread,
            slippage=c.slippage,
            latency_slippage=c.latency_slippage,
            commission_per_lot=c.commission_per_lot,
            value_per_unit=c.value_per_unit,
        )

    # ---------------------------------------------------------- controls
    def pause(self) -> None:
        self.account.paused = True
        self._log("info", "Paper trading paused.")

    def resume(self) -> None:
        self.account.paused = False
        self._log("info", "Paper trading resumed.")

    def reset(self) -> None:
        self.account.reset()
        self.journal.clear()
        self._log("info", "Paper account reset.")

    def update_config(self, config: PaperAccountConfig) -> None:
        self.config = config
        self.account.config = config
        self._cost = self._make_cost()
        self.account.reset()
        self.journal.clear()
        self._log("info", "Paper account reconfigured and reset.")

    # ---------------------------------------------------------- price feed
    def on_price(self, bid: float, ask: float, epoch: float) -> None:
        self.account.roll_day(epoch)
        self.last_bid, self.last_ask, self.last_epoch = bid, ask, epoch
        self.last_mid = (bid + ask) / 2.0
        mid = self.last_mid

        self._process_pending_orders(mid, epoch)
        self._manage_positions(mid, epoch)
        self.account.update_drawdown(mid)
        self._check_daily_loss()

    # ---------------------------------------------------------- signals
    def on_signal(self, signal: dict, strategy_name: str | None = None) -> SignalDecision:
        key = signal.get("strategy_key", "unknown")
        name = strategy_name or signal.get("strategy_name") or key
        level = int(signal.get("level", 0))
        # Always journal the signal itself (signal != trade).
        self.journal.add(
            JournalEntry(
                epoch=self.last_epoch,
                kind="signal",
                message=f"{signal.get('level_name', level)} "
                f"{(signal.get('direction') or '').upper()} [{name}]",
                strategy_key=key,
                strategy_name=name,
                payload={
                    "level": level,
                    "direction": signal.get("direction"),
                    "confidence_score": signal.get("confidence_score"),
                },
            )
        )
        decision = self._evaluate_signal(signal, key, name)
        if decision.executed:
            self.journal.add(
                JournalEntry(
                    epoch=self.last_epoch,
                    kind="trade_opened",
                    message=f"Opened {signal.get('direction','').upper()} [{name}] "
                    f"pos {decision.position_id}",
                    strategy_key=key,
                    strategy_name=name,
                )
            )
        else:
            # This is the explicit SIGNAL-vs-TRADE record: signal seen, not traded.
            self.journal.add(
                JournalEntry(
                    epoch=self.last_epoch,
                    kind="rejected",
                    message=f"Signal NOT executed [{name}]: {decision.reason}",
                    strategy_key=key,
                    strategy_name=name,
                    payload={"reason": decision.reason},
                )
            )
        return decision

    def _evaluate_signal(self, signal: dict, key: str, name: str) -> SignalDecision:
        if self.last_mid is None:
            return SignalDecision(False, "No live market price yet.")
        if self.account.paused:
            return SignalDecision(False, "Trading is paused.")
        if self.account.halted:
            return SignalDecision(False, self.account.halt_reason or "Trading halted.")

        level = int(signal.get("level", 0))
        if level < self.config.min_signal_level:
            return SignalDecision(
                False,
                f"Signal level {level} below execution threshold "
                f"{self.config.min_signal_level}.",
            )

        direction = signal.get("direction")
        stop = signal.get("stop_loss")
        tps = signal.get("take_profits") or []
        if direction not in ("long", "short") or stop is None or not tps:
            return SignalDecision(False, "No actionable setup (missing direction/stop/target).")

        if self.account.open_position_count() >= self.config.max_open_positions:
            return SignalDecision(False, "Maximum open positions reached (risk limit).")

        mid = self.last_mid
        entry_fill = self._cost.entry_fill(direction, mid)
        if direction == "long" and not (stop < entry_fill < tps[0]):
            return SignalDecision(False, "Invalid geometry: need stop < price < target for long.")
        if direction == "short" and not (tps[0] < entry_fill < stop):
            return SignalDecision(False, "Invalid geometry: need target < price < stop for short.")

        equity = self.account.equity(mid)
        lots = position_lots(
            equity,
            self.config.risk_per_trade_pct,
            entry_fill,
            stop,
            self.config.value_per_unit,
            self.config.max_position_lots,
        )
        if lots <= 0:
            return SignalDecision(False, "Computed position size is zero (check stop/risk).")

        pos = self._open_position(
            direction=direction,
            entry_fill=entry_fill,
            lots=lots,
            stop=stop,
            tp=tps[0],
            tp2=tps[1] if len(tps) > 1 else None,
            strategy_key=key,
            strategy_name=name,
            regime=signal.get("regime"),
        )
        return SignalDecision(True, "Executed (paper).", position_id=pos.id)

    # ---------------------------------------------------------- manual orders
    def submit_market_order(
        self,
        direction: str,
        stop: float,
        tp: float,
        lots: float | None = None,
        *,
        strategy_key: str = "manual",
        strategy_name: str = "Manual",
    ) -> SignalDecision:
        signal = {
            "strategy_key": strategy_key,
            "strategy_name": strategy_name,
            "level": SignalLevel.CONFIRMED_SETUP.value,
            "direction": direction,
            "stop_loss": stop,
            "take_profits": (tp,),
        }
        return self.on_signal(signal, strategy_name)

    # ---------------------------------------------------------- position ops
    def _open_position(
        self,
        *,
        direction: str,
        entry_fill: float,
        lots: float,
        stop: float,
        tp: float | None,
        tp2: float | None,
        strategy_key: str,
        strategy_name: str,
        regime: str | None,
    ) -> PaperPosition:
        pid = self.account.next_id("pos")
        pos = PaperPosition(
            id=pid,
            direction=direction,
            entry_price=entry_fill,
            lots=lots,
            initial_lots=lots,
            stop_loss=stop,
            take_profit=tp,
            take_profit_2=tp2,
            strategy_key=strategy_key,
            strategy_name=strategy_name,
            regime=regime,
            opened_epoch=self.last_epoch,
            highest_price=self.last_mid or entry_fill,
            lowest_price=self.last_mid or entry_fill,
        )
        self.account.positions[pid] = pos
        return pos

    def close_position(self, position_id: str, reason: str = "manual_close") -> bool:
        pos = self.account.positions.get(position_id)
        if pos is None or self.last_mid is None:
            return False
        self._close_full(pos, self.last_mid, reason, self.last_epoch)
        return True

    def close_all(self, reason: str = "close_all") -> int:
        if self.last_mid is None:
            return 0
        count = 0
        for pos in list(self.account.positions.values()):
            self._close_full(pos, self.last_mid, reason, self.last_epoch)
            count += 1
        return count

    def _manage_positions(self, mid: float, epoch: float) -> None:
        for pos in list(self.account.positions.values()):
            self._update_trailing(pos, mid)
            if pos.direction == "long":
                if pos.stop_loss is not None and mid <= pos.stop_loss:
                    self._close_full(pos, pos.stop_loss, "stop_loss", epoch)
                    continue
                if pos.take_profit is not None and mid >= pos.take_profit:
                    self._handle_take_profit(pos, epoch)
            else:
                if pos.stop_loss is not None and mid >= pos.stop_loss:
                    self._close_full(pos, pos.stop_loss, "stop_loss", epoch)
                    continue
                if pos.take_profit is not None and mid <= pos.take_profit:
                    self._handle_take_profit(pos, epoch)

    def _handle_take_profit(self, pos: PaperPosition, epoch: float) -> None:
        target = pos.take_profit
        if (
            self.config.partial_tp_enabled
            and not pos.partial_taken
            and pos.take_profit_2 is not None
        ):
            self._partial_close(pos, target, self.config.partial_tp_fraction, epoch)
        else:
            self._close_full(pos, target, "take_profit", epoch)

    def _update_trailing(self, pos: PaperPosition, mid: float) -> None:
        if not self.config.trailing_enabled or self.config.trailing_distance <= 0:
            return
        dist = self.config.trailing_distance
        if pos.direction == "long":
            pos.highest_price = max(pos.highest_price, mid)
            new_stop = pos.highest_price - dist
            if pos.stop_loss is None or new_stop > pos.stop_loss:
                pos.stop_loss = new_stop
        else:
            pos.lowest_price = min(pos.lowest_price, mid)
            new_stop = pos.lowest_price + dist
            if pos.stop_loss is None or new_stop < pos.stop_loss:
                pos.stop_loss = new_stop

    def _partial_close(
        self, pos: PaperPosition, exit_mid: float, fraction: float, epoch: float
    ) -> None:
        lots_to_close = pos.lots * fraction
        exit_fill = self._cost.exit_fill(pos.direction, exit_mid)
        net = self._cost.net_pnl(pos.direction, pos.entry_price, exit_fill, lots_to_close)
        self.account.balance += net
        pos.realized_pnl += net
        pos.lots -= lots_to_close
        pos.partial_taken = True
        if self.config.move_stop_to_breakeven_on_partial:
            pos.stop_loss = pos.entry_price
        pos.take_profit = pos.take_profit_2  # remainder runs to the next target
        self.journal.add(
            JournalEntry(
                epoch=epoch,
                kind="info",
                message=f"Partial exit {fraction:.0%} of {pos.id} at {exit_fill:.2f} "
                f"(net {net:.2f}); stop -> breakeven.",
                strategy_key=pos.strategy_key,
                strategy_name=pos.strategy_name,
            )
        )

    def _close_full(self, pos: PaperPosition, exit_mid: float, reason: str, epoch: float) -> None:
        exit_fill = self._cost.exit_fill(pos.direction, exit_mid)
        net = self._cost.net_pnl(pos.direction, pos.entry_price, exit_fill, pos.lots)
        self.account.balance += net
        total_pnl = pos.realized_pnl + net
        record = PaperTradeRecord(
            id=self.account.next_id("trade"),
            strategy_key=pos.strategy_key,
            strategy_name=pos.strategy_name,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_fill,
            lots=pos.initial_lots or pos.lots,
            pnl=total_pnl,
            return_pct=(
                total_pnl / self.config.starting_balance if self.config.starting_balance else 0.0
            ),
            exit_reason=reason,
            regime=pos.regime,
            opened_epoch=pos.opened_epoch,
            closed_epoch=epoch,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
        )
        self.account.closed_trades.append(record)
        self.account.positions.pop(pos.id, None)
        self.journal.add(
            JournalEntry(
                epoch=epoch,
                kind="trade_closed",
                message=f"Closed {pos.direction.upper()} {pos.id} ({reason}) "
                f"P&L {total_pnl:.2f}",
                strategy_key=pos.strategy_key,
                strategy_name=pos.strategy_name,
                payload={"pnl": round(total_pnl, 2), "reason": reason},
            )
        )

    def _process_pending_orders(self, mid: float, epoch: float) -> None:
        for order in list(self.account.pending_orders.values()):
            if order.status is not OrderStatus.PENDING or order.price is None:
                continue
            triggered = False
            if order.order_type is OrderType.LIMIT:
                triggered = (order.side is OrderSide.BUY and mid <= order.price) or (
                    order.side is OrderSide.SELL and mid >= order.price
                )
            elif order.order_type is OrderType.STOP:
                triggered = (order.side is OrderSide.BUY and mid >= order.price) or (
                    order.side is OrderSide.SELL and mid <= order.price
                )
            if triggered:
                direction = "long" if order.side is OrderSide.BUY else "short"
                entry_fill = self._cost.entry_fill(direction, mid)
                order.status = OrderStatus.FILLED
                order.filled_lots = order.requested_lots
                order.avg_fill_price = entry_fill
                self._open_position(
                    direction=direction,
                    entry_fill=entry_fill,
                    lots=order.requested_lots,
                    stop=order.stop_loss,
                    tp=order.take_profit,
                    tp2=None,
                    strategy_key=order.strategy_key,
                    strategy_name=order.strategy_name,
                    regime=order.regime,
                )
                self.account.pending_orders.pop(order.id, None)

    def add_pending_order(self, order: PaperOrder) -> str:
        order.id = self.account.next_id("ord")
        order.created_epoch = self.last_epoch
        self.account.pending_orders[order.id] = order
        return order.id

    # ---------------------------------------------------------- risk halts
    def _check_daily_loss(self) -> None:
        limit = -(self.config.max_daily_loss_pct / 100.0) * self.config.starting_balance
        if not self.account.halted and self.account.realized_daily_pnl() <= limit:
            self.account.halted = True
            self.account.halt_reason = (
                f"Daily loss limit reached ({self.config.max_daily_loss_pct:.1f}% of starting "
                f"balance). New entries blocked until reset or next day."
            )
            self._log("info", self.account.halt_reason)

    def _log(self, kind: str, message: str) -> None:
        self.journal.add(JournalEntry(epoch=self.last_epoch, kind=kind, message=message))

    # ---------------------------------------------------------- state / views
    def state(self) -> dict:
        mid = self.last_mid
        return {
            "account": self.account.snapshot(mid),
            "config": self.config.to_dict(),
            "last_price": {
                "bid": self.last_bid,
                "ask": self.last_ask,
                "mid": mid,
                "epoch": self.last_epoch,
            },
            "positions": [
                p.to_dict(mid, self.config.value_per_unit) for p in self.account.positions.values()
            ],
            "pending_orders": [o.to_dict() for o in self.account.pending_orders.values()],
        }

    def performance(self) -> dict:
        return {
            "overall": overall_performance(
                self.account.closed_trades, self.config.starting_balance
            ),
            "by_strategy": performance_by_strategy(
                self.account.closed_trades, self.config.starting_balance
            ),
        }

    def closed_trades(self, limit: int = 100) -> list[dict]:
        return [t.to_dict() for t in self.account.closed_trades[-limit:][::-1]]

    def journal_entries(self, limit: int = 50, kind: str | None = None) -> list[dict]:
        return self.journal.recent(limit, kind)
