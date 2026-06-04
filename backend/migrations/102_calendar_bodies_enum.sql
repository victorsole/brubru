-- 102_calendar_bodies_enum.sql
-- Extend institution_enum so My EU Calendar can carry events from the EU bodies
-- that are not Commission DGs and not already enumerated: EDPS, Ombudsman, EIB,
-- ECA, ECHA, ENISA, EUIPO, EUAA, Eurojust, FRA, EU-OSHA, Eurofound, ACER, ECDC,
-- AMLA, CEPOL, EIT, CPVO, EMSA, EEAS.
--
-- Idempotent (ADD VALUE IF NOT EXISTS). Unused values are harmless, so wiring a
-- slow body later needs no second migration. ALTER TYPE ... ADD VALUE is allowed
-- outside an explicit transaction on PostgreSQL 12+ (Supabase = PG15); run the
-- statements as-is. No new tables, so no Data-API grants required.
--
-- Created: 1 June 2026 (MEUB My EU Calendar — all-EU bodies event ingestion).

ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EDPS';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'OMBUDSMAN';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EIB';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'ECA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'ECHA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'ENISA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EUIPO';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EUAA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EUROJUST';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'FRA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EU_OSHA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EUROFOUND';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'ACER';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'ECDC';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'AMLA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'CEPOL';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EIT';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'CPVO';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EMSA';
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EEAS';
