-- 226_unique_oeil_procedure_ref.sql
--
-- Stop legislative_carriages acquiring duplicate rows for the same EU procedure.
--
-- Why (found by /news, 4 September 2026; merged 7 September 2026)
-- ---------------------------------------------------------------
-- Three ingest paths each create their own row and nothing enforced uniqueness:
-- LEGISLATIVE_TRAIN, OEIL_DIRECT and EURLEX. Three procedures had ended up with
-- two rows each -- 2026/0013(COD) Digital Networks Act, 2026/0068(COD) Industrial
-- Accelerator Act and 2026/0074(COD) EU Inc.
--
-- The damage is not cosmetic. Users were tracking BOTH copies, so a user on copy A
-- never saw the documents or events attached to copy B, and Position Analysis
-- produced two snapshots for the same file that disagreed with each other. One copy
-- also held the CELEX while the other did not.
--
-- The three duplicates were merged on 7 September 2026 by
-- scripts/merge_duplicate_carriages.py. This index is what stops them coming back;
-- without it the next sync recreates the problem.
--
-- Why a PARTIAL index
-- -------------------
-- 1,370 of 3,274 carriages (41.8%) legitimately have NO oeil_procedure_ref: EUR-Lex
-- and Legislative Train rows often predate an OEIL reference. A plain UNIQUE index
-- would technically allow them, because NULL never equals NULL in Postgres -- but
-- relying on that is exactly the trap recorded in
-- feedback_null_propagation_and_silent_fallback_hide_failures, where an ON CONFLICT
-- on a nullable column silently stopped being a dedup. The `WHERE ... IS NOT NULL`
-- clause states the intent in the schema instead of leaving it to a NULL-semantics
-- rule the next reader has to remember, and it keeps 1,370 pointless entries out of
-- the index.
--
-- Pre-flight
-- ----------
-- Verified immediately before writing this file: 3,274 rows, 0 duplicates among the
-- 1,904 non-NULL refs. If a duplicate has appeared since, the CREATE fails with a
-- unique-violation naming the offending value; re-run
-- `python3.12 scripts/merge_duplicate_carriages.py --apply` and then this migration.
-- It is not safe to force past it: a duplicate means two rows users may both be
-- tracking.
--
-- Apply:  psql "$DATABASE_URL" -f backend/migrations/226_unique_oeil_procedure_ref.sql
-- Safe to re-run (IF NOT EXISTS).

CREATE UNIQUE INDEX IF NOT EXISTS uq_legislative_carriages_oeil_procedure_ref
    ON public.legislative_carriages (oeil_procedure_ref)
    WHERE oeil_procedure_ref IS NOT NULL;

COMMENT ON INDEX public.uq_legislative_carriages_oeil_procedure_ref IS
    'One carriage per OEIL procedure reference. Added 7 September 2026 after three '
    'procedures were found duplicated across the LEGISLATIVE_TRAIN, OEIL_DIRECT and '
    'EURLEX ingest paths, with users tracking both copies. Partial on IS NOT NULL '
    'because 42% of carriages legitimately have no OEIL reference.';

-- No RLS or GRANT changes: this adds an index to an existing table, it does not
-- create one. The Supabase Data API grant rule applies to new public.* TABLES.
