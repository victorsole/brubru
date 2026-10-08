-- 281: the EuroVoc descriptors Cellar assigns to each resolution, as eu_laws has (276).
--
-- ep_resolutions.eurovoc_codes was empty on all 353 rows (8 Oct 2026): nothing ever
-- filled it. The Publications Office indexes every resolution it publishes in the OJ C
-- series against EuroVoc (7 to 11 descriptors on the 12 sampled), and since
-- scripts/backfill_texts_adopted_celex.py each adopted text carries its real CELEX,
-- so the descriptors can be read rather than guessed. Same shape and states as
-- eu_laws: [{id, uri, label, domain}]; [] = on Cellar, no descriptors yet; NULL = not
-- read (the text is not in the OJ yet). eurovoc_codes keeps the descriptor ids.
-- Writer: scripts/sync_resolution_eurovoc.py.
ALTER TABLE ep_resolutions
    ADD COLUMN IF NOT EXISTS eurovoc            jsonb,
    ADD COLUMN IF NOT EXISTS eurovoc_domain     text,
    ADD COLUMN IF NOT EXISTS eurovoc_fetched_at timestamptz;

COMMENT ON COLUMN ep_resolutions.eurovoc IS 'EuroVoc descriptors from Cellar: [{id, uri, label, domain}]. [] = on Cellar, none yet; NULL = not read (text not in the OJ yet).';
COMMENT ON COLUMN ep_resolutions.eurovoc_domain IS 'EuroVoc domain carried by most descriptors (ties: lowest notation; 72 GEOGRAPHY only if sole).';
COMMENT ON COLUMN ep_resolutions.eurovoc_fetched_at IS 'When the descriptors were last read from Cellar. Bookkeeping: does not move updated_at.';

-- Bookkeeping stamps must not count as a change. Setting followup_checked_at for the
-- first time re-stamped updated_at on 350 rows (8 Oct 2026), so incremental-sync
-- clients re-pulled most of the corpus for no visible change. The trigger's second
-- argument lists columns ignored when deciding whether a row changed.
DROP TRIGGER IF EXISTS trg_ep_resolutions_touch_if_changed ON ep_resolutions;
CREATE TRIGGER trg_ep_resolutions_touch_if_changed
    BEFORE UPDATE ON ep_resolutions
    FOR EACH ROW EXECUTE FUNCTION
    brubru_touch_if_changed('updated_at', 'eurovoc_fetched_at,followup_checked_at', 'created_at');
