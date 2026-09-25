-- One EU act appeared as two API records with different ids (GovClipping, 25 Sep 2026).
--
-- `secondary_acts` is written by three ingestors that upsert ON CONFLICT (reference).
-- `backfill_regulatory_cascade.py` writes the CELEX itself into `reference`, so when the
-- same act already existed under its Commission document number (C(2013)9763 for
-- 32014R0241) the conflict never fired and a second row was inserted. That second row is
-- a stub: no text_body, and a 128-character "Derived from ..." description. GovClipping
-- identifies acts by CELEX, so whichever row they processed last won and the stub could
-- overwrite the full text of the act.
--
-- 783 CELEX values had more than one row: 778 stub+real pairs, 4 pairs of real rows that
-- share a CELEX under two different Commission document numbers, and 1 group of three.
--
-- Merging cannot just delete the extra row. Measured before touching anything:
--   * 729 pairs agree on parent_celex          -> the stub adds nothing
--   *  22 pairs have parent_celex ONLY on the stub -> deleting it loses the relationship
--   *  28 pairs name DIFFERENT parents, both real: 32017R1569 supplements both Regulation
--     (EU) 536/2014 and Directive 2001/20/EC, and the column holds one value
--
-- So the survivor records what was merged into it. Nothing is dropped silently, the
-- second parent stays queryable, and the merge can be read back and undone.
ALTER TABLE secondary_acts ADD COLUMN IF NOT EXISTS merged_from JSONB;

COMMENT ON COLUMN secondary_acts.merged_from IS
    'Rows merged into this one because they shared its CELEX: a JSON array of '
    '{id, reference, parent_celex, first_seen, source}. Null when nothing was merged. '
    'Written by scripts/merge_duplicate_secondary_acts.py (25 Sep 2026).';

CREATE INDEX IF NOT EXISTS ix_secondary_acts_celex ON secondary_acts (celex);
