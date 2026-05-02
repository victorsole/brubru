-- 049_immc_tags.sql
--
-- Phase 5 of docs/applications/euvoc.md — surface inter-institutional
-- handoff signals on legislative_carriages.
--
-- Provenance: the public Cellar graph does not literally expose
-- "immc:*" predicates. We project the IMMC-equivalent semantics from the
-- `cdm:event_legal_*` predicate family (initiated_by_institution,
-- responsibility_of_institution, session_council, part_of_dossier,
-- date, type). The column name "immc_tags" matches the conceptual
-- vocabulary partners expect; the JSONB shape is documented in
-- services/api_clients/immc_client.py.
--
-- Shape (per-row JSONB):
--   {
--     "events": [
--       {
--         "type": "<cdm:event_legal_type concept URI>",
--         "date": "<ISO 8601>",
--         "initiated_by": "<cdm:event_legal_initiated_by_institution URI>",
--         "responsibility_of": "<URI>",
--         "associated_with": ["<URI>", ...],
--         "session_council": "<URI or null>",
--         "dossier": "<URI or null>"
--       }, ...
--     ],
--     "fetched_at": "<ISO 8601>"
--   }

ALTER TABLE legislative_carriages
    ADD COLUMN IF NOT EXISTS immc_tags JSONB NOT NULL DEFAULT '{}'::JSONB;

CREATE INDEX IF NOT EXISTS ix_legcarr_immc_events
    ON legislative_carriages USING GIN ((immc_tags -> 'events'));

COMMENT ON COLUMN legislative_carriages.immc_tags IS
    'IMMC-equivalent inter-institutional handoff events projected from '
    'cdm:event_legal_* predicates. See services/api_clients/immc_client.py '
    'for the JSONB shape contract.';
