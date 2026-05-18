-- ============================================================
-- ethical-finance — Migration v2
-- À exécuter dans le conteneur PostgreSQL :
-- sudo docker exec -i ethical-finance-db psql -U sauhabah -d ethical_finance < migrations/v2_portfolio_auth.sql
-- ============================================================

-- ── 1. users ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. user_portfolios ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_portfolios (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker     VARCHAR(20) NOT NULL,
    qty        NUMERIC(18, 6) NOT NULL,
    avg_price  NUMERIC(18, 4) NOT NULL,
    currency   VARCHAR(3) NOT NULL DEFAULT 'EUR',
    opened_at  TIMESTAMPTZ DEFAULT NOW(),
    closed_at  TIMESTAMPTZ,
    notes      TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_portfolios_user_id ON user_portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_user_portfolios_ticker  ON user_portfolios(ticker);

-- ── 3. signals_history ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals_history (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker            VARCHAR(20) NOT NULL,
    date              DATE NOT NULL,
    strategy_id       VARCHAR(50) NOT NULL,   -- ex: 'epr5', 'momentum'
    signal_buy        BOOLEAN NOT NULL DEFAULT FALSE,
    signal_sell       BOOLEAN NOT NULL DEFAULT FALSE,
    rf_score          NUMERIC(5, 4),
    lstm_score        NUMERIC(5, 4),
    sentiment_score   NUMERIC(5, 4),
    fundamental_score NUMERIC(5, 4),
    technical_score   NUMERIC(5, 4),
    composite_score   NUMERIC(5, 4),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, date, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_history_ticker   ON signals_history(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_history_date     ON signals_history(date);
CREATE INDEX IF NOT EXISTS idx_signals_history_strategy ON signals_history(strategy_id);

-- ── 4. nav_history (ajout colonnes v2) ───────────────────────
-- Crée la table si elle n'existe pas encore
CREATE TABLE IF NOT EXISTS nav_history (
    ticker             VARCHAR(20) NOT NULL,
    date               DATE NOT NULL,
    nav                NUMERIC(18, 6),
    nav_div_reinvested NUMERIC(18, 6),
    split_factor       NUMERIC(10, 6) DEFAULT 1.0,
    PRIMARY KEY (ticker, date)
);

-- Ajoute les colonnes v2 si la table existait déjà
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='nav_history' AND column_name='nav_div_reinvested'
    ) THEN
        ALTER TABLE nav_history ADD COLUMN nav_div_reinvested NUMERIC(18, 6);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='nav_history' AND column_name='split_factor'
    ) THEN
        ALTER TABLE nav_history ADD COLUMN split_factor NUMERIC(10, 6) DEFAULT 1.0;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_nav_history_ticker ON nav_history(ticker);
CREATE INDEX IF NOT EXISTS idx_nav_history_date   ON nav_history(date);

-- ── Vérification ──────────────────────────────────────────────
SELECT table_name, COUNT(*) as colonnes
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('users', 'user_portfolios', 'signals_history', 'nav_history')
GROUP BY table_name
ORDER BY table_name;
