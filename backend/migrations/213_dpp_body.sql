-- 213_dpp_body.sql
--
-- Registers the Digital Product Passport as an /api/v2 body folder.
--
-- The DPP is not an EU institution, it is a horizontal regulatory regime created by
-- ESPR Article 9 to 15 and operationalised by Commission Implementing Regulation (EU)
-- 2026/1778. It gets its own body folder because it spans six laws and ten product
-- sectors, and every one of them has to be answerable in one place: which act binds a
-- product, when its passport becomes mandatory, what data the passport must carry, and
-- which harmonised standard gives presumption of conformity.
--
-- economy_items.body_code is a FOREIGN KEY to economy_bodies(code), so the folder
-- cannot hold a single row until this body exists.
--
-- is_eu_institution is FALSE: the row describes a regime administered by the
-- Commission (DG GROW and DG ENV), not a body with its own legal personality.

INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution)
VALUES (
    'dpp',
    'dpp',
    'Regulatory regimes',
    'DPP',
    'Digital Product Passport',
    'The EU regime requiring products placed on the single market to carry a digital '
    'product passport: a structured, machine-readable record of composition, '
    'circularity, environmental impact, repair and end-of-life information, registered '
    'in a central registry managed by the Commission. Created by Regulation (EU) '
    '2024/1781 (ESPR) Articles 9 to 15 and implemented by Commission Implementing '
    'Regulation (EU) 2026/1778. Batteries are the first product group with a hard '
    'deadline (18 February 2027); textiles, garments and footwear follow.',
    'https://single-market-economy.ec.europa.eu/single-market/digital-product-passport_en',
    FALSE
)
ON CONFLICT (code) DO UPDATE SET
    family   = EXCLUDED.family,
    name     = EXCLUDED.name,
    mandate  = EXCLUDED.mandate,
    website  = EXCLUDED.website;

-- economy_bodies / economy_items already carry their Supabase Data API grants from the
-- migration that created them; this migration adds a row, not a table, so no new GRANT
-- is required. See memory/feedback_supabase_data_api_grants.md for the table rule.
