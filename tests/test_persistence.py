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
