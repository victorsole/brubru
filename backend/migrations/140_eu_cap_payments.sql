-- Migration 140 — eu_cap_payments
-- Common Agricultural Policy fund payments by Member State, from the DG REGIO
-- Cohesion Open Data Platform (Socrata): EAGF (qgpc-e9qr "2023-2027 EAGF
-- Payments") and EAFRD (7wr2-9vpr "2023-2027 EU Payments by MS - EAFRD").
-- One row per fund x Member State. Amounts in EUR. Backs
-- /api/v2/funding/eagf and /api/v2/funding/eafrd. Standard v2 item contract
-- (5 datapoints + composed body). Full-refresh backfill; weekly tier.

CREATE TABLE IF NOT EXISTS eu_cap_payments (
    id                    BIGSERIAL PRIMARY KEY,
    fund                  TEXT NOT NULL,        -- EAGF | EAFRD
    ms                    TEXT,                 -- Member State ISO code
    planned_eu_amount     NUMERIC,              -- EAFRD: planned EU amount (latest adopted); EAGF: null
    net_pre_financing     NUMERIC,              -- EAFRD only
    net_interim_payments  NUMERIC,              -- EAFRD only
    total_eur             NUMERIC,              -- EAGF total allocation / EAFRD total net payments
    payment_rate          NUMERIC,              -- EAFRD: payments / planned (0-1); EAGF: null
    fy_2023               NUMERIC,              -- EAGF annual; EAFRD null
    fy_2024               NUMERIC,
    fy_2025               NUMERIC,
    fy_2026               NUMERIC,
    fy_2027               NUMERIC,
    -- standard datapoints
    public_url            TEXT,
    body_txt              TEXT,
    body_html             TEXT,
    body_source           VARCHAR(24),
    document_date         TIMESTAMPTZ,
    source_dataset        TEXT,
    raw                   JSONB,
    fetched_at            TIMESTAMPTZ DEFAULT NOW(),
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cap_payments_fund ON eu_cap_payments (fund);
CREATE INDEX IF NOT EXISTS ix_cap_payments_ms   ON eu_cap_payments (ms);

ALTER TABLE eu_cap_payments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_cap_payments_read ON eu_cap_payments;
CREATE POLICY p_cap_payments_read ON eu_cap_payments FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON eu_cap_payments TO anon, authenticated;
GRANT ALL    ON eu_cap_payments TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_cap_payments_id_seq TO service_role;
