-- 300: one eu_laws row per CELEX, enforced by the database.
--
-- Until now idx_eu_laws_celex was a plain btree: nothing stopped a second row with the same CELEX. Writers
-- guarded it themselves, unevenly: sync_eu_laws_from_cellar.py inserts WHERE NOT EXISTS, import_corpus_update.py
-- keeps a map of held CELEX (since 7c69ffae, 15 Oct 2026), but import_leg_archive.import_document and the
-- law indexer check only the folder uuid. The 13 Oct 2026 import left 1,738 duplicates (removed by hand) and
-- 224 rows without CELEX that duplicated held acts (merged and removed on 15 Oct). Measured 15 Oct 2026 after
-- the clean-up: 30,684 rows, 30,684 with a CELEX, 0 duplicates, 0 empty strings, so the index builds.
--
-- Partial: NULL and '' are not identifiers, so rows without one are not compared (none exist today). A writer
-- that tries a second row now fails loudly instead of creating it. The plain index stays: it serves lookups by
-- a bound parameter, which the planner cannot prove to satisfy the partial predicate.
-- lock_timeout: the build takes a SHARE lock on 30k rows (well under a second); if a long writer holds the
-- table, fail fast rather than queue every other writer behind the build.

SET LOCAL lock_timeout = '10s';

CREATE UNIQUE INDEX IF NOT EXISTS uq_eu_laws_celex
    ON eu_laws (celex)
    WHERE celex IS NOT NULL AND celex <> '';

COMMENT ON INDEX uq_eu_laws_celex IS 'One eu_laws row per CELEX (migration 300, 15 Oct 2026); NULL and empty CELEX are not compared.';
