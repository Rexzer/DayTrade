"""Tests: in-memory trade store (pure persistence contract)."""

from backend.app.persistence.store import (
    InMemoryTradeStore,
    StoredOrder,
    StoredSignal,
    StoredTrade,
)


def test_save_and_read_signal():
    store = InMemoryTradeStore()
    sid = store.save_signal(
        StoredSignal(strategy_key="tf", symbol="XAUUSD", timeframe="1h", level=3, direction="long")
    )
    assert sid == 1
    rows = store.recent_signals()
    assert len(rows) == 1 and rows[0]["strategy_key"] == "tf" and rows[0]["id"] == 1


def test_save_and_read_order():
    store = InMemoryTradeStore()
    store.save_order(
        StoredOrder(
            account_label="Live", symbol="XAUUSD", side="buy", order_type="market", volume_lots=0.1
        )
    )
    rows = store.recent_orders()
    assert rows[0]["side"] == "buy" and rows[0]["volume_lots"] == 0.1


def test_save_and_read_trade():
    store = InMemoryTradeStore()
    store.save_trade(
        StoredTrade(
            strategy_key="tf",
            symbol="XAUUSD",
            side="long",
            volume_lots=0.1,
            entry_price=2400,
            exit_price=2410,
            pnl=100,
            mode="paper",
        )
    )
    rows = store.recent_trades()
    assert rows[0]["pnl"] == 100 and rows[0]["mode"] == "paper"


def test_ids_increment_across_types():
    store = InMemoryTradeStore()
    a = store.save_signal(StoredSignal("tf", "XAUUSD", "1h", 1, "long"))
    b = store.save_order(StoredOrder("Live", "XAUUSD", "buy", "market", 0.1))
    c = store.save_trade(StoredTrade("tf", "XAUUSD", "long", 0.1, 1, 2, 1))
    assert (a, b, c) == (1, 2, 3)


def test_recent_is_newest_first_and_limited():
    store = InMemoryTradeStore()
    for i in range(5):
        store.save_signal(StoredSignal(f"s{i}", "XAUUSD", "1h", 1, "long"))
    recent = store.recent_signals(limit=2)
    assert len(recent) == 2
    assert recent[0]["strategy_key"] == "s4"  # newest first


# ---------------------------------------------------------------- position -> trade


def test_stored_trade_from_position_maps_fields():
    from types import SimpleNamespace

    from backend.app.persistence.store import stored_trade_from_position

    pos = SimpleNamespace(
        symbol="XAUUSD",
        side="buy",
        volume=0.2,
        price_open=2400.0,
        price_current=2415.0,
        profit=30.0,
        time_epoch=1000.0,
    )
    trade = stored_trade_from_position(pos, mode="live", closed_epoch=2000.0)
    assert trade.symbol == "XAUUSD"
    assert trade.side == "buy"
    assert trade.volume_lots == 0.2
    assert trade.entry_price == 2400.0
    assert trade.exit_price == 2415.0  # last-known current price is the exit
    assert trade.pnl == 30.0
    assert trade.mode == "live"
    assert trade.opened_epoch == 1000.0
    assert trade.closed_epoch == 2000.0
    assert trade.exit_reason == "closed"


def test_stored_trade_from_position_tolerates_missing_fields():
    from types import SimpleNamespace

    from backend.app.persistence.store import stored_trade_from_position

    # A bare position exposing only the minimum should not raise.
    trade = stored_trade_from_position(SimpleNamespace(symbol="XAUUSD", side="sell"))
    assert trade.symbol == "XAUUSD"
    assert trade.side == "sell"
    assert trade.volume_lots == 0.0
    assert trade.entry_price is None
    assert trade.exit_price is None
    assert trade.pnl is None


def test_position_synchronizer_close_yields_persistable_trade():
    """An open->close transition produces a StoredTrade carrying the P&L."""
    from backend.app.persistence.store import (
        InMemoryTradeStore,
        stored_trade_from_position,
    )
    from execution_engine import BrokerPosition, PositionSynchronizer

    sync = PositionSynchronizer()
    pos = BrokerPosition(
        ticket=42,
        symbol="XAUUSD",
        side="buy",
        volume=0.1,
        price_open=2400.0,
        price_current=2412.0,
        profit=12.0,
        time_epoch=500.0,
    )
    # First snapshot: position is open (no closes yet).
    assert sync.diff([pos]).closed == []
    # Second snapshot: position gone -> reported as closed with last-known state.
    diff = sync.diff([])
    assert len(diff.closed) == 1
    closed = diff.closed[0]

    store = InMemoryTradeStore()
    store.save_trade(stored_trade_from_position(closed, mode="live", closed_epoch=900.0))
    rows = store.recent_trades()
    assert len(rows) == 1
    assert rows[0]["pnl"] == 12.0
    assert rows[0]["exit_price"] == 2412.0
    assert rows[0]["mode"] == "live"
