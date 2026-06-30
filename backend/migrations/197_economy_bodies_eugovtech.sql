-- Migration 197 (30 Jun 2026)
-- Phase 2: register the EC GovTech body for /api/v2/eugovtech.
-- EU GovTech is a dedicated sub-portal (a collection on the Interoperable Europe
-- Portal, DG DIGIT) covering govtech for the public sector: news, events,
-- reusable solutions, the Knowledge Centre (reports & policy briefs), the
-- GovTech Atlas and GovTech4All challenges. Stored in economy_items under
-- body_code='eugovtech'. Playwright-fed, refreshed locally.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution)
VALUES ('eugovtech', 'eugovtech',
        'Single market — digital & electronic communications',
        'EUGOVTECH', 'EU GovTech',
        'The European Commission (DG DIGIT) EU GovTech community on the '
        'Interoperable Europe Portal: news, events, reusable solutions, the '
        'Knowledge Centre, the GovTech Atlas and GovTech4All public-sector challenges.',
        'https://interoperable-europe.ec.europa.eu/collection/eugovtech', false)
ON CONFLICT (code) DO NOTHING;
