-- Migration 0007 — Portfolio Tracker multi-portefeuille

CREATE TABLE IF NOT EXISTS portfolios (
    id          SERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    type        TEXT DEFAULT 'CTO' CHECK (type IN ('CTO','PEA','PEA-PME','AV','CRYPTO','OTHER')),
    currency    TEXT DEFAULT 'EUR',
    broker      TEXT,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS transactions (
    id              SERIAL PRIMARY KEY,
    portfolio_id    INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    ticker          TEXT NOT NULL,
    date            DATE NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('BUY','SELL','DIVIDEND','SPLIT','FEE','DEPOSIT','WITHDRAWAL')),
    qty             DOUBLE PRECISION NOT NULL DEFAULT 0,
    price           DOUBLE PRECISION NOT NULL DEFAULT 0,
    fees            DOUBLE PRECISION DEFAULT 0,
    currency        TEXT DEFAULT 'USD',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tx_portfolio ON transactions(portfolio_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_tx_ticker ON transactions(ticker, date DESC);
