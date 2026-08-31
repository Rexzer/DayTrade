"""Tests: paper-trading engine (simulated execution, risk, controls)."""

from paper_trading import PaperAccountConfig, PaperTradingEngine
from strategy_engine.strategy import SignalLevel


def _sig(
    direction="long", stop=90.0, tps=(115.0,), level=SignalLevel.CONFIRMED_SETUP, key="s", name="S"
):
    return {
        "strategy_key": key,
        "strategy_name": name,
        "level": level.value,
        "level_name": level.name,
        "direction": direction,
        "stop_loss": stop,
        "take_profits": tuple(tps),
        "regime": "strong_bullish",
    }


def _engine(**overrides):
    cfg = PaperAccountConfig(
        starting_balance=10_000,
        risk_per_trade_pct=1.0,
        spread=0.0,
        slippage=0.0,
        latency_slippage=0.0,
        commission_per_lot=0.0,
        value_per_unit=1.0,
        **overrides,
    )
    return PaperTradingEngine(cfg)


def _price(eng, mid, epoch):
    eng.on_price(mid, mid, epoch)  # zero spread => bid==ask==mid


def test_rejects_signal_without_price():
    eng = _engine()
    d = eng.on_signal(_sig(), "S")
    assert d.executed is False
    assert "price" in d.reason.lower()


def test_long_take_profit_is_a_win():
    eng = _engine()
    _price(eng, 100.0, 1000)
    d = eng.on_signal(_sig(stop=90.0, tps=(115.0,)), "S")
    assert d.executed
    _price(eng, 115.0, 1060)  # hits TP
    assert len(eng.account.positions) == 0
    t = eng.account.closed_trades[-1]
    assert t.exit_reason == "take_profit" and t.is_win
    # entry 100, exit 115, lots = 100/10 = 10 => pnl 150
    assert round(t.pnl, 2) == 150.0


def test_long_stop_loss_is_a_loss():
    eng = _engine()
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(stop=90.0, tps=(130.0,)), "S")
    _price(eng, 90.0, 1060)  # hits stop
    t = eng.account.closed_trades[-1]
    assert t.exit_reason == "stop_loss" and not t.is_win
    assert round(t.pnl, 2) == -100.0


def test_short_take_profit():
    eng = _engine()
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig("short", stop=110.0, tps=(85.0,)), "S")
    _price(eng, 85.0, 1060)
    t = eng.account.closed_trades[-1]
    assert t.direction == "short" and t.exit_reason == "take_profit" and t.is_win


def test_signal_below_min_is_not_executed():
    eng = _engine()
    _price(eng, 100.0, 1000)
    d = eng.on_signal(_sig(level=SignalLevel.WATCH), "S")
    assert d.executed is False
    assert "below execution threshold" in d.reason
    # The rejection is journalled (signal vs trade).
    kinds = [e["kind"] for e in eng.journal_entries(10)]
    assert "rejected" in kinds and "signal" in kinds


def test_max_open_positions_limit():
    eng = _engine(max_open_positions=1)
    _price(eng, 100.0, 1000)
    d1 = eng.on_signal(_sig(), "S")
    d2 = eng.on_signal(_sig(), "S")
    assert d1.executed and not d2.executed
    assert "Maximum open positions" in d2.reason


def test_daily_loss_limit_halts_new_entries():
    eng = _engine(max_daily_loss_pct=1.0)  # limit = -100
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(stop=90.0, tps=(130.0,)), "S")
    _price(eng, 90.0, 1060)  # ~ -100 loss => halts
    assert eng.account.halted is True
    d = eng.on_signal(_sig(), "S")
    assert d.executed is False
    assert "daily loss" in d.reason.lower()


def test_daily_loss_halt_clears_next_day():
    eng = _engine(max_daily_loss_pct=1.0)
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(stop=90.0, tps=(130.0,)), "S")
    _price(eng, 90.0, 1060)
    assert eng.account.halted
    # Advance ~2 days.
    _price(eng, 100.0, 1000 + 2 * 86400)
    assert eng.account.halted is False


def test_pause_blocks_and_resume_allows():
    eng = _engine()
    _price(eng, 100.0, 1000)
    eng.pause()
    assert eng.on_signal(_sig(), "S").executed is False
    eng.resume()
    assert eng.on_signal(_sig(), "S").executed is True


def test_reset_restores_starting_balance():
    eng = _engine()
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(), "S")
    _price(eng, 115.0, 1060)
    assert eng.account.balance != 10_000
    eng.reset()
    assert eng.account.balance == 10_000
    assert eng.account.positions == {}
    assert eng.account.closed_trades == []


def test_manual_close_position():
    eng = _engine()
    _price(eng, 100.0, 1000)
    d = eng.on_signal(_sig(), "S")
    assert eng.close_position(d.position_id) is True
    assert len(eng.account.positions) == 0
    assert eng.account.closed_trades[-1].exit_reason == "manual_close"


def test_trailing_stop_locks_in_profit():
    eng = _engine(trailing_enabled=True, trailing_distance=2.0)
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(stop=90.0, tps=(200.0,)), "S")  # far TP so trailing acts
    _price(eng, 110.0, 1060)  # highest 110 -> stop trails to 108
    pos = list(eng.account.positions.values())[0]
    assert round(pos.stop_loss, 2) == 108.0
    _price(eng, 108.0, 1120)  # trailing stop hit, in profit
    t = eng.account.closed_trades[-1]
    assert t.exit_reason == "stop_loss" and t.is_win


def test_partial_take_profit_then_runner():
    eng = _engine(partial_tp_enabled=True, partial_tp_fraction=0.5)
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(stop=90.0, tps=(110.0, 120.0)), "S")  # tp1=110, tp2=120
    pos = list(eng.account.positions.values())[0]
    initial = pos.lots
    _price(eng, 110.0, 1060)  # tp1 -> partial close half, stop -> breakeven
    pos = list(eng.account.positions.values())[0]
    assert pos.partial_taken is True
    assert round(pos.lots, 4) == round(initial * 0.5, 4)
    assert pos.stop_loss == pos.entry_price
    _price(eng, 120.0, 1120)  # tp2 -> full close
    assert len(eng.account.positions) == 0
    t = eng.account.closed_trades[-1]
    assert t.is_win and round(t.lots, 4) == round(initial, 4)


def test_performance_by_strategy_compare():
    eng = _engine(max_open_positions=1)
    # Strategy A: a win.
    _price(eng, 100.0, 1000)
    eng.on_signal(_sig(key="a", name="A", stop=90.0, tps=(115.0,)), "A")
    _price(eng, 115.0, 1060)
    # Strategy B: a loss.
    _price(eng, 100.0, 2000)
    eng.on_signal(_sig(key="b", name="B", stop=90.0, tps=(130.0,)), "B")
    _price(eng, 90.0, 2060)
    perf = eng.performance()
    keys = {r["strategy_key"] for r in perf["by_strategy"]}
    assert keys == {"a", "b"}
    assert perf["overall"]["num_trades"] == 2
