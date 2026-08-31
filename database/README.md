# Database

PostgreSQL is the primary datastore. All timestamps are stored in **UTC**;
conversion to local time happens only in the presentation layer.

## How tables are created

- **Development:** call `init_db()` (see `backend/app/db/session.py`) which runs
  `Base.metadata.create_all()`. A convenience is exposed via the backend on
  first run.
- **Production:** use migrations (Alembic is added in a later phase). Do not
  rely on `create_all()` in production.

## Models (Phase 1)

Defined in `backend/app/db/models.py`:

| Table | Purpose |
|-------|---------|
| `users` | Application users (hashed passwords only) |
| `accounts` | Trading account snapshots (never real money in Phase 1) |
| `broker_connections` | Broker/MT5 metadata — **no plaintext credentials** |
| `strategies` | Strategy definitions (registry mirror) |
| `strategy_parameters` | Per-strategy parameters |
| `signals` | Explainable signals (levels 0–4) |
| `orders` | Orders (none created in Phase 1) |
| `positions` | Positions (none in Phase 1) |
| `trades` | Closed trades + journal fields |
| `risk_settings` | Per-user risk limits |
| `notifications` | Outbound notifications |
| `news_events` | Economic calendar events (empty in Phase 1) |
| `system_logs` | Structured decision/audit log |

## Security notes

- Broker/MetaTrader **passwords are never stored here**. `broker_connections`
  keeps only a non-secret `login_hint` and a `secret_ref` pointer to an
  external secret store (wired up in Phase 5).
