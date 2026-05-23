-- Migration 0004 — Table ticker_lei_mapping
-- Run sur DEV : psql -h 192.168.1.47 -p 5434 -U sauhabah -d ethical_finance -f 0004_ticker_lei_mapping.sql

BEGIN;

CREATE TABLE IF NOT EXISTS ticker_lei_mapping (
    ticker              VARCHAR(20)  PRIMARY KEY,
    lei                 VARCHAR(20)  DEFAULT NULL,
    legal_name          TEXT         DEFAULT NULL,
    source              VARCHAR(20)  DEFAULT NULL,   -- 'gleif', 'info-financiere', 'manual'
    has_esef_filing     BOOLEAN      DEFAULT FALSE,
    esef_filing_count   INT          DEFAULT 0,
    last_period_end     DATE         DEFAULT NULL,   -- dernière période disponible sur xbrl.org
    verified_at         TIMESTAMP    DEFAULT NULL,
    created_at          TIMESTAMP    DEFAULT NOW(),
    updated_at          TIMESTAMP    DEFAULT NOW()
);

-- Index pour lookup rapide
CREATE INDEX IF NOT EXISTS idx_tlm_lei         ON ticker_lei_mapping(lei);
CREATE INDEX IF NOT EXISTS idx_tlm_has_esef    ON ticker_lei_mapping(has_esef_filing);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_ticker_lei_mapping_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tlm_updated_at ON ticker_lei_mapping;
CREATE TRIGGER trg_tlm_updated_at
    BEFORE UPDATE ON ticker_lei_mapping
    FOR EACH ROW EXECUTE FUNCTION update_ticker_lei_mapping_updated_at();

COMMIT;

-- Vérification
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'ticker_lei_mapping'
ORDER BY ordinal_position;
