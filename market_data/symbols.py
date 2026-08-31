"""Broker-specific symbol mapping (pure Python).

Brokers name gold differently: XAUUSD, XAUUSDm, GOLD, XAUUSD.a, XAUUSD.raw, ...
The platform uses a single canonical symbol ("XAUUSD") internally and maps to
whatever the connected broker/provider actually expects. The user selects the
correct broker symbol; we never assume a single universal name.
"""

from __future__ import annotations

from market_data.provider import SymbolSpec

CANONICAL_XAUUSD = "XAUUSD"

# Common broker aliases for gold seen across MT4/MT5 brokers and data vendors.
# The mapping is case-insensitive on lookup.
_KNOWN_ALIASES: dict[str, str] = {
    "XAUUSD": CANONICAL_XAUUSD,
    "XAUUSDM": CANONICAL_XAUUSD,
    "XAUUSD.A": CANONICAL_XAUUSD,
    "XAUUSD.RAW": CANONICAL_XAUUSD,
    "XAUUSD.PRO": CANONICAL_XAUUSD,
    "XAUUSD_": CANONICAL_XAUUSD,
    "XAUUSDC": CANONICAL_XAUUSD,
    "GOLD": CANONICAL_XAUUSD,
    "GOLD.": CANONICAL_XAUUSD,
    "GOLDUSD": CANONICAL_XAUUSD,
    "XAU/USD": CANONICAL_XAUUSD,
    "OANDA:XAU_USD": CANONICAL_XAUUSD,
}


class SymbolMapper:
    """Maps broker symbols to the canonical symbol and holds the active spec."""

    def __init__(self, spec: SymbolSpec | None = None) -> None:
        # Default active spec is plain XAUUSD; the user can override the broker
        # symbol once they know what their broker uses.
        self._spec = spec or SymbolSpec()
        self._aliases = dict(_KNOWN_ALIASES)

    @property
    def canonical(self) -> str:
        return self._spec.canonical

    @property
    def spec(self) -> SymbolSpec:
        return self._spec

    def register_alias(self, broker_symbol: str, canonical: str = CANONICAL_XAUUSD) -> None:
        self._aliases[broker_symbol.strip().upper()] = canonical

    def resolve(self, broker_symbol: str) -> str | None:
        """Return the canonical symbol for ``broker_symbol`` or ``None`` if unknown."""
        if not broker_symbol:
            return None
        return self._aliases.get(broker_symbol.strip().upper())

    def is_gold(self, broker_symbol: str) -> bool:
        return self.resolve(broker_symbol) == CANONICAL_XAUUSD

    def set_broker_symbol(self, broker_symbol: str, *, digits: int | None = None) -> SymbolSpec:
        """Select the broker symbol the active feed should request.

        Registers the alias (so future lookups resolve) and updates the active
        spec. Returns the new spec.
        """
        cleaned = broker_symbol.strip()
        if not cleaned:
            raise ValueError("broker_symbol must not be empty")
        self.register_alias(cleaned, CANONICAL_XAUUSD)
        self._spec = SymbolSpec(
            canonical=CANONICAL_XAUUSD,
            broker_symbol=cleaned,
            digits=digits if digits is not None else self._spec.digits,
            point=10 ** (-digits) if digits is not None else self._spec.point,
            description=self._spec.description,
        )
        return self._spec

    def known_aliases(self) -> list[str]:
        return sorted(self._aliases.keys())
