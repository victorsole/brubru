-- 292: a delegated or implementing act's text says where it came from.
--
-- 88 delegated acts adopted by the Commission but not (yet) in the Official Journal,
-- among them the 43 whose objection period may still be running and the 24 Parliament or
-- Council objected to, carried no text: /legislative/delegated-acts composed a "body" from
-- their metadata. The Commission's document register serves the text it adopted (the
-- C(YYYY)NNNN document, with its annexes). That text is replaced by the Official Journal's
-- once the act is published, so each row must say which one it holds. Found 14 Oct 2026
-- auditing GovClipping's delegated-acts request.
--
--   official_journal     the published act, from Cellar
--   commission_document  the act as the Commission adopted it, from its document register
--
-- Existing texts on rows with a CELEX came from Cellar (fetch_secondary_act_bodies_xhtml,
-- fill_secondary_act_bodies_from_laws); the rest are left NULL rather than guessed.

-- Labelling the texts already held is not a change to any act, so the change signal is
-- held still for it: otherwise all ~6,500 rows would read as updated today and every
-- client's next incremental sync would pull the whole table again.

ALTER TABLE secondary_acts ADD COLUMN IF NOT EXISTS body_source varchar(24);

ALTER TABLE secondary_acts DISABLE TRIGGER trg_secondary_acts_touch;
UPDATE secondary_acts SET body_source = 'official_journal'
 WHERE body_source IS NULL AND coalesce(text_body, '') <> '' AND coalesce(celex, '') <> '';
ALTER TABLE secondary_acts ENABLE TRIGGER trg_secondary_acts_touch;

COMMENT ON COLUMN secondary_acts.body_source IS
    'Where text_body came from: official_journal (Cellar) or commission_document (the Commission document register, before publication). Migration 292.';
