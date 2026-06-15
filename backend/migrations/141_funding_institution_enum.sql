-- 141_funding_institution_enum.sql
-- Add a FUNDING institution so My EU Calendar can carry EU Funding & Tenders
-- Portal events (info days, webinars, conferences) as their own distinct filter
-- entry, rather than folding them under the Commission.
--
-- Idempotent (ADD VALUE IF NOT EXISTS). ALTER TYPE ... ADD VALUE is allowed
-- outside an explicit transaction on PostgreSQL 12+ (Supabase = PG15). No new
-- tables, so no Data-API grants required.
--
-- Created: 15 June 2026 (MEUB My EU Calendar — F&T Portal events ingestion).

ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'FUNDING';
