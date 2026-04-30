-- Migration 042: Amendator Featured Examples
-- Created: 2026-04-30
-- Purpose: Replace the hardcoded list of "Example URLs" in the Amendator (eurlex_url_input.tsx)
-- with a DB-backed, daily-rotating list of up to 10 active hot legislative files.
-- Items are soft-deactivated (kept in DB for audit) when displaced by newer entries.

CREATE TABLE IF NOT EXISTS public.amendator_featured_examples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    celex           TEXT,                                -- e.g. "52026PC0321" (CELEX) or any procedure ref
    eurlex_url      TEXT NOT NULL,                       -- canonical EUR-Lex URL or intcom URL pasted into the input
    title           TEXT NOT NULL,                       -- short label shown to user (e.g. "EU Inc. (28th Regime)")
    description     TEXT,                                -- one-line context for the example
    source          TEXT,                                -- where the example came from: "news", "manual", "skill", "carriage"
    position        INTEGER NOT NULL DEFAULT 0,          -- display order (lowest first); 0..9 active
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,       -- soft-delete flag; FALSE = retained but not shown
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at  TIMESTAMPTZ,
    UNIQUE (eurlex_url)
);

CREATE INDEX IF NOT EXISTS idx_afex_active_position
    ON public.amendator_featured_examples (is_active, position)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_afex_added_at
    ON public.amendator_featured_examples (added_at DESC);

ALTER TABLE public.amendator_featured_examples ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read amendator featured examples" ON public.amendator_featured_examples;
CREATE POLICY "Public read amendator featured examples"
    ON public.amendator_featured_examples
    FOR SELECT
    USING (TRUE);

-- Seed: 10 hot files from the recent /news cycles (April 2026 Strasbourg trio + companions)
INSERT INTO public.amendator_featured_examples
    (celex, eurlex_url, title, description, source, position, is_active)
VALUES
    ('52026PC0321',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52026PC0321',
     'EU Inc. (28th Regime Corporate Framework)',
     'Pan-European corporate regime — single legal form valid across all 27 Member States.',
     'manual', 0, TRUE),
    ('52026DC0380',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52026DC0380',
     'Better Regulation Communication COM(2026) 380',
     '"A Simpler, Clearer and Better Enforced EU Rulebook" + Annex I Regulatory Deep Cleaning Action Plan (12 areas).',
     'news', 1, TRUE),
    ('52026DC0370',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52026DC0370',
     'AccelerateEU Communication COM(2026) 370',
     'Commission response to the Iran war + Strait of Hormuz energy crisis (22 April 2026).',
     'news', 2, TRUE),
    ('32024R1157',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1157',
     'Waste Shipment Regulation (WSR) + DIWASS',
     'Regulation (EU) 2024/1157 — main provisions apply 21 May 2026; mandatory DIWASS digital system.',
     'news', 3, TRUE),
    ('32024L1385',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024L1385',
     'Violence Against Women Directive 2024/1385',
     'Consent-based rape definition debate — EP plenary 28 April 2026 vote on amending Article 5.',
     'news', 4, TRUE),
    ('32022R2065',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2065',
     'Digital Services Act (DSA)',
     'Meta preliminary finding 29 April 2026 (IP/26/920) — under-13 access to Instagram and Facebook.',
     'news', 5, TRUE),
    ('32024R1689',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689',
     'AI Act — Regulation (EU) 2024/1689',
     'Foundation regulation; harmonised standards M/613 + M/606 in development; AI Continent Action Plan.',
     'news', 6, TRUE),
    ('intcom:Ares(2025)3570423',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=intcom:Ares%282025%293570423',
     'Industrial Accelerator Act',
     'Single Market industrial competitiveness instrument — March 2026 College adoption.',
     'manual', 7, TRUE),
    ('52025PC0570',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52025PC0570',
     'MFF 2028-2034 — COM(2025) 570',
     'EP plenary adopted negotiating position 29 April 2026; in trilogue with Council.',
     'news', 8, TRUE),
    ('22026A00184',
     'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:22026A00184',
     'EU-Mercosur ITA — Provisional Application',
     'Council Decision; provisional application enters force 1 May 2026.',
     'news', 9, TRUE)
ON CONFLICT (eurlex_url) DO NOTHING;
