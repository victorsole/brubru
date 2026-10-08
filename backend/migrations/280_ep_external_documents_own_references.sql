-- 280: the adopted text and procedure a Commission follow-up names in its OWN text.
--
-- ep_external_documents.answers_to is EP Open Data's metadata link, and it is wrong
-- for about 1 in 10 recent follow-ups (38 of 367 since July 2024, measured 8 Oct 2026):
-- it holds the committee REPORT's number typed as an adopted-text id.
-- SP-2026-05-26-TA-10-2026-0270 claims to answer TA-10-2026-0270 (adopted 9 July 2026,
-- six weeks after the follow-up); its own text reads "References: 2025/2088(INI) /
-- A10-0270/2025 / P10_TA(2026)0020", the drones resolution.
--
-- Every follow-up opens with that reference line ("References:" or "Reference
-- numbers:"). These columns read it. GENERATED, so they can never drift from the body
-- and no writer has to remember them; NULL when the document has no English text or
-- no such line, in which case answers_to is the only link (see
-- services/matching/resolution_followups.py).
ALTER TABLE ep_external_documents
    ADD COLUMN IF NOT EXISTS ref_ta text GENERATED ALWAYS AS (
        substring(substring(body_txt from '(?:References|Reference numbers):[^\n]*')
                  from 'P[0-9]+_TA\([0-9]{4}\)[0-9]{4}')
    ) STORED,
    ADD COLUMN IF NOT EXISTS ref_procedure text GENERATED ALWAYS AS (
        replace(substring(substring(body_txt from '(?:References|Reference numbers):[^\n]*')
                          from '[0-9]{4}/[0-9]{4} ?\([A-Z]{3}\)'), ' ', '')
    ) STORED;

COMMENT ON COLUMN ep_external_documents.ref_ta IS
    'Adopted text (P10_TA(YYYY)NNNN) named in the follow-up''s own reference line; NULL when the text has none. Preferred over answers_to.';
COMMENT ON COLUMN ep_external_documents.ref_procedure IS
    'Procedure (YYYY/NNNN(XXX)) named in the follow-up''s own reference line; NULL when the text has none.';

CREATE INDEX IF NOT EXISTS idx_ep_external_documents_ref_ta ON ep_external_documents (ref_ta);
CREATE INDEX IF NOT EXISTS idx_ep_external_documents_ref_procedure ON ep_external_documents (ref_procedure);
CREATE INDEX IF NOT EXISTS idx_ep_external_documents_answers_to ON ep_external_documents USING gin (answers_to);
