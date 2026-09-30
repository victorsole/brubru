-- secondary_acts: make the CELEX the identity the database enforces.
--
-- GovClipping found 80 CELEX values held by two rows each. The cause is one line in
-- scripts/ingest_regdel_acts.py:
--
--     ON CONFLICT (reference) DO UPDATE ...
--
-- `reference` is the Commission's C(YYYY)NNNN number, and there is a UNIQUE index on it
-- (secondary_acts_reference_key), which is why that upsert looked safe. It is not: a
-- C-number is a LABEL the Commission can re-issue, and the same act arriving under a new
-- one conflicts with nothing, so a second row is inserted for a CELEX we already hold.
-- The identity is the CELEX.
--
-- This table was already de-duplicated once for this exact line: 783 rows still carry a
-- merged_from entry from that cleanup. The script was never changed, so the duplicates
-- came back. A guard that lives only inside one script is a guard the next writer walks
-- past, so the constraint belongs here, in the schema.
--
-- The index is PARTIAL because 731 acts legitimately have no CELEX: adopted by the
-- College but not yet published in the OJ (569 of them carry a 2026 C-number), or still
-- draft. NULL is the correct value there and must stay unconstrained -- a plain UNIQUE
-- would be satisfied by NULLs in Postgres anyway, but the partial form states the intent
-- and keeps the index small.
--
-- Run 258_ AFTER scripts/merge_duplicate_secondary_acts.py --apply. The CREATE will fail
-- loudly if any duplicate remains, which is the behaviour we want: it is the gate that
-- proves the merge finished, not a step that quietly tidies up after it.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS ux_secondary_acts_celex
    ON public.secondary_acts (celex)
    WHERE celex IS NOT NULL AND celex <> '';

COMMENT ON INDEX public.ux_secondary_acts_celex IS
    'CELEX is the identity of a secondary act. Partial because 731 adopted-but-unpublished '
    'and draft acts have no CELEX yet. Added 30 Sep 2026 after the second duplicate '
    'incident caused by ON CONFLICT (reference) in ingest_regdel_acts.py.';

COMMENT ON COLUMN public.secondary_acts.reference IS
    'The Commission C(YYYY)NNNN number. A LABEL, not an identity: the same act can be '
    'issued a different C-number, and upserting on this column created duplicate rows '
    'twice (783 pairs, then 80). Upsert on celex when the act has one.';

COMMENT ON COLUMN public.secondary_acts.adoption_date IS
    'Date of adoption, from Cellar (cdm:work_date_document). NOT from the RegDel export: '
    'its only date column is "Planned adoption date" and it holds a quarter string such '
    'as "Q3 2026", which is not a date. NULL where the act has no CELEX to look up.';

COMMIT;
