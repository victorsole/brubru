-- Migration 144 (15 Jun 2026)
-- Audit finding #3: backfill the EEAS row in economy_bodies so the
-- Move 5 FWC scraper (ingest_eu_institution_frameworks) does not
-- FK-fail on a fresh DB / staging spin-up.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, is_eu_institution)
VALUES ('eeas', 'institutions', 'eu_institution', 'EEAS',
        'European External Action Service', true)
ON CONFLICT (code) DO NOTHING;
