"""Concrete real market-data providers.

These implement the same :class:`market_data.provider.MarketDataProvider`
interface as the simulated provider, so the rest of the platform is agnostic
to the data source. They require network access (and usually an API key),
which is configured via environment variables — never hard-coded.

Currently included:
    * :class:`GenericRestProvider` — polls any HTTP JSON quote endpoint.

Vendor-specific providers (Finnhub/Twelve Data/broker bridges) can be added
here without touching the aggregation, storage, or UI layers.
"""

from market_data.providers.rest_polling import GenericRestProvider, RestProviderConfig

__all__ = ["GenericRestProvider", "RestProviderConfig"]
