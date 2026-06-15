-- 142_consultations_source_body.sql
-- Turn EC Public Consultations into an all-EU hub: alongside the Commission's
-- Have Your Say consultations, ingest the decentralised EU agency consultations
-- (EIOPA, BEREC, ACER, EASA, EMA, AMLA, ECHA, SRB, ERA, ECB-SSM) that already
-- live in economy_items (item_type='consultation', the /api/v2/consultations/all
-- layer) into public_consultations so they are uniform and trackable.
--
-- Two nullable columns discriminate the source. Existing rows default to
-- 'commission'. Idempotent. No new table, so no Data-API grants required.
--
-- Created: 15 June 2026 (MEUB EC Public Consultations -> all-EU hub).

ALTER TABLE public_consultations
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'commission';

ALTER TABLE public_consultations
    ADD COLUMN IF NOT EXISTS source_body VARCHAR(20);

-- Filter helpers for the hub list endpoint.
CREATE INDEX IF NOT EXISTS ix_public_consultations_source ON public_consultations (source);
CREATE INDEX IF NOT EXISTS ix_public_consultations_source_body ON public_consultations (source_body);
