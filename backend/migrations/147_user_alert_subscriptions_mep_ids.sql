-- Migration 147: extend user_alert_subscriptions for MEP-author tracking
--
-- Adds an optional mep_ids INTEGER[] column. When set, the saved-search runner
-- treats the subscription as an "author watch" — matches against
--   parliamentary_questions.asking_mep_ids && mep_ids,
--   texts_adopted.rapporteur_mep_id::int = ANY(mep_ids),
--   mep_amendments.mep_ids && mep_ids,
--   ep_resolutions where rapporteur name resolves to one of these MEPs (best-effort).
--
-- When mep_ids IS NULL the subscription is topic-only (existing behaviour).
-- query_phrase + mep_ids may be combined (AND) when both are set.
--
-- No backfill needed — existing 3 Marga subscriptions stay topic-only.

ALTER TABLE user_alert_subscriptions
    ADD COLUMN IF NOT EXISTS mep_ids INTEGER[] DEFAULT NULL;

COMMENT ON COLUMN user_alert_subscriptions.mep_ids IS
    'Optional list of EP MEP IDs (data.europarl.europa.eu /meps). When set, the alert runner matches docs authored by these MEPs (parliamentary_questions, texts_adopted rapporteur, mep_amendments authors).';
