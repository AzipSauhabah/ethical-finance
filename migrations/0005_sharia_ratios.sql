BEGIN;
ALTER TABLE ticker_fundamentals
    ADD COLUMN IF NOT EXISTS short_term_debt          BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS long_term_debt           BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS interest_bearing_debt    BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS interest_expense         BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS interest_income          BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS total_assets             BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS total_equity             BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS non_permissible_income   BIGINT           DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS sharia_debt_ratio        DOUBLE PRECISION DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS sharia_liquidity_ratio   DOUBLE PRECISION DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS sharia_income_ratio      DOUBLE PRECISION DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS sharia_ratios_updated_at TIMESTAMP        DEFAULT NULL;
COMMIT;
