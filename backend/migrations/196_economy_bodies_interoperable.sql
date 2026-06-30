-- Migration 196 (30 Jun 2026)
-- Phase 1: register the EU Interoperable body for /api/v2/interoperable.
-- The Interoperable Europe Portal (DG DIGIT) aggregates news, events and
-- reusable solutions across many thematic collections (OSOR, SEMIC, EU GovTech,
-- EIF/Monitoring, Public Sector Tech Watch, EUPL, CAMSS/EIRA, Digital-Ready
-- Policymaking, Regulatory Sandboxes, Guidelines, the Academy). Items are stored
-- in economy_items under body_code='interoperable'; the collection is parsed
-- from public_url at query time. Playwright-fed, refreshed locally.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution)
VALUES ('interoperable', 'interoperable',
        'Single market — digital & electronic communications',
        'INTEROP', 'Interoperable Europe Portal',
        'The European Commission (DG DIGIT) portal for cross-border interoperability '
        'of public services: news, events and reusable interoperability solutions '
        'shared across thematic collections.',
        'https://interoperable-europe.ec.europa.eu', false)
ON CONFLICT (code) DO NOTHING;
