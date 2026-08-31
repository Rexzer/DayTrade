-- =============================================================================
-- XAUUSD Trading Platform — PostgreSQL initialisation (Phase 1)
-- =============================================================================
-- This runs once when the Postgres container is first created.
--
-- The application's tables are created by SQLAlchemy models (see
-- backend/app/db/models.py) via `init_db()` or, in production, by database
-- migrations. This script only prepares the database itself.
--
-- All application timestamps are stored in UTC.
-- =============================================================================

-- Ensure the server operates in UTC.
SET TIME ZONE 'UTC';

-- Useful extension for future UUID / gen_random_uuid() usage.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- No seed data is inserted in Phase 1. In particular, NO account balances,
-- NO market prices, and NO news events are created — the platform must never
-- present fabricated data.
