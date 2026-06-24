#!/bin/bash
# setup_db.sh – runs as a docker-entrypoint-initdb.d script inside the
# timescaledb container to apply the initial schema migration.
set -e

echo "[HCB] Running initial database migration..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable TimescaleDB extension
    CREATE EXTENSION IF NOT EXISTS timescaledb;

    -- WALLET
    CREATE TABLE IF NOT EXISTS wallet (
        wallet_id        VARCHAR(42)      PRIMARY KEY,
        first_seen       TIMESTAMPTZ      NOT NULL,
        total_trades     INTEGER          NOT NULL DEFAULT 0,
        win_rate         DECIMAL(5, 4),
        avg_position_usd DECIMAL(18, 4),
        composite_score  DECIMAL(5, 4),
        label            VARCHAR(50),
        updated_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    );

    -- MARKET
    CREATE TABLE IF NOT EXISTS market (
        market_id        VARCHAR(100)    PRIMARY KEY,
        question         TEXT            NOT NULL,
        category         VARCHAR(100),
        created_at       TIMESTAMPTZ,
        close_time       TIMESTAMPTZ,
        resolved_at      TIMESTAMPTZ,
        resolution       VARCHAR(50),
        total_volume_usd DECIMAL(18, 4)  DEFAULT 0
    );

    -- TRADE
    CREATE TABLE IF NOT EXISTS trade (
        trade_id        VARCHAR(66)      PRIMARY KEY,
        wallet_id       VARCHAR(42)      NOT NULL REFERENCES wallet(wallet_id),
        market_id       VARCHAR(100)     NOT NULL REFERENCES market(market_id),
        outcome         VARCHAR(10)      NOT NULL,
        amount_usd      DECIMAL(18, 4)   NOT NULL,
        shares          DECIMAL(18, 8)   NOT NULL,
        price_at_entry  DECIMAL(5, 4)    NOT NULL,
        tx_timestamp    TIMESTAMPTZ      NOT NULL,
        resolved        BOOLEAN          NOT NULL DEFAULT FALSE,
        won             BOOLEAN
    );

    CREATE INDEX IF NOT EXISTS idx_trade_wallet ON trade(wallet_id);
    CREATE INDEX IF NOT EXISTS idx_trade_market ON trade(market_id);
    CREATE INDEX IF NOT EXISTS idx_trade_ts     ON trade(tx_timestamp DESC);

    -- BEHAVIORAL_SCORE (TimescaleDB hypertable)
    CREATE TABLE IF NOT EXISTS behavioral_score (
        id                  BIGSERIAL,
        wallet_id           VARCHAR(42)     NOT NULL REFERENCES wallet(wallet_id),
        win_rate            DECIMAL(5, 4),
        position_size_score DECIMAL(5, 4),
        timing_score        DECIMAL(5, 4),
        consistency_score   DECIMAL(5, 4),
        composite_score     DECIMAL(5, 4)   NOT NULL,
        computed_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
        PRIMARY KEY (id, computed_at)
    );

    SELECT create_hypertable(
        'behavioral_score',
        'computed_at',
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '1 day'
    );

    CREATE INDEX IF NOT EXISTS idx_bs_wallet_time
        ON behavioral_score(wallet_id, computed_at DESC);

    -- ALERT_RULE
    CREATE TABLE IF NOT EXISTS alert_rule (
        rule_id     SERIAL          PRIMARY KEY,
        rule_name   VARCHAR(100)    NOT NULL,
        metric      VARCHAR(50)     NOT NULL,
        operator    VARCHAR(10)     NOT NULL,
        threshold   DECIMAL(10, 4)  NOT NULL,
        active      BOOLEAN         NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
    );

    -- Seed default rules
    INSERT INTO alert_rule (rule_name, metric, operator, threshold) VALUES
        ('High CBS Alert',    'composite_score', '>',  0.8),
        ('High Win Rate',     'win_rate',        '>',  0.75),
        ('Large Position',    'avg_position_usd','>',  5000.0)
    ON CONFLICT DO NOTHING;

    -- ALERT
    CREATE TABLE IF NOT EXISTS alert (
        alert_id            BIGSERIAL       PRIMARY KEY,
        wallet_id           VARCHAR(42)     NOT NULL REFERENCES wallet(wallet_id),
        rule_id             INTEGER         NOT NULL REFERENCES alert_rule(rule_id),
        composite_score     DECIMAL(5, 4),
        triggered_metric    DECIMAL(10, 4),
        dispatched_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
        channels_notified   TEXT[]
    );

    CREATE INDEX IF NOT EXISTS idx_alert_wallet ON alert(wallet_id);
    CREATE INDEX IF NOT EXISTS idx_alert_time   ON alert(dispatched_at DESC);
EOSQL

echo "[HCB] Migration complete."
