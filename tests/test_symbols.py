"""Tests: broker-specific XAUUSD symbol mapping."""

from market_data.symbols import CANONICAL_XAUUSD, SymbolMapper


def test_known_aliases_resolve_to_canonical():
    m = SymbolMapper()
    for alias in ["XAUUSD", "XAUUSDm", "GOLD", "XAUUSD.a", "xauusd.raw", "XAU/USD"]:
        assert m.resolve(alias) == CANONICAL_XAUUSD, alias


def test_case_insensitive_resolution():
    m = SymbolMapper()
    assert m.resolve("gold") == CANONICAL_XAUUSD
    assert m.resolve("  XauUsdM  ") == CANONICAL_XAUUSD


def test_unknown_symbol_returns_none():
    m = SymbolMapper()
    assert m.resolve("EURUSD") is None
    assert m.resolve("") is None


def test_is_gold():
    m = SymbolMapper()
    assert m.is_gold("XAUUSDm") is True
    assert m.is_gold("GBPUSD") is False


def test_set_broker_symbol_updates_spec_and_registers_alias():
    m = SymbolMapper()
    spec = m.set_broker_symbol("XAUUSD.pro", digits=3)
    assert spec.broker_symbol == "XAUUSD.pro"
    assert spec.digits == 3
    assert abs(spec.point - 0.001) < 1e-9
    # Now resolvable.
    assert m.resolve("XAUUSD.pro") == CANONICAL_XAUUSD


def test_set_empty_symbol_raises():
    m = SymbolMapper()
    raised = False
    try:
        m.set_broker_symbol("   ")
    except ValueError:
        raised = True
    assert raised


def test_custom_alias_registration():
    m = SymbolMapper()
    assert m.resolve("GLD.x") is None
    m.register_alias("GLD.x")
    assert m.resolve("GLD.x") == CANONICAL_XAUUSD
