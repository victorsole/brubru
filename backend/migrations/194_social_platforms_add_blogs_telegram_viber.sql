-- 194_social_platforms_add_blogs_telegram_viber.sql
-- Phase 4 prep (28 Jun 2026). The D1-D4 audit found the official EU social-media directory
-- (WBQL sheet1) uses three platforms not in migration 193's seed: blogs, telegram, viber.
-- The social_platforms reference table is extensible exactly so this is one INSERT, not a
-- schema change. Without them the D5 wiring FK would reject those directory rows.
INSERT INTO public.social_platforms (code, name, fetch_tier, notes) VALUES
    ('blogs',    'Blogs',    'open', 'europa.eu / institutional blog pages; web/RSS readable'),
    ('telegram', 'Telegram', 'gated','Bot API / public channels; gated read'),
    ('viber',    'Viber',    'none', 'community channels, no usable read API')
ON CONFLICT (code) DO NOTHING;
