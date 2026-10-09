-- 287: com_register_seen, the COM documents the Commission's document register has shown us (9 Oct 2026).
--
-- Why: COM(2026) 546 final, the fifth annual report on the Recovery and Resilience Facility,
-- is dated 7 October. A client found it on LinkedIn on 9 October. Brubru found COM documents only
-- through Cellar and EUR-Lex RSS, and Cellar did not hold the record until the morning of the
-- 9th, two days after its date: a Cellar-only radar cannot see a COM document on the day it is
-- adopted. The Commission's own document register (api/groupSearch, category COM) lists the
-- document with its date, type, department and titles; scripts/sync_com_register.py reads it
-- every run and compares it with commission_documents.
--
-- This table is what that job has SEEN, not a copy of the documents. It exists for two reasons:
-- to say "new on the register" without re-reading history, and to MEASURE the lead the register
-- has over Cellar (first_seen_at on the register against held_first_seen_at in our store), which
-- on 9 Oct could not be proven because the register response carries no registration timestamp.
--
-- Private working data: service_role only, like mcp_requests and client_sent_mails.

CREATE TABLE IF NOT EXISTS public.com_register_seen (
    reference           TEXT        PRIMARY KEY,                 -- 'COM(2026)546'
    doc_year            INTEGER     NOT NULL,
    doc_number          INTEGER     NOT NULL,
    doc_type            TEXT        NOT NULL DEFAULT '',         -- register type: REPORT, PROP_REG, COMMUNIC, ...
    doc_date            DATE,                                    -- the register's document date
    department          TEXT,
    version             TEXT,
    title               TEXT,                                    -- English title, from the main attachment
    celex               TEXT,                                    -- only when the REGISTER carries one; never derived
    url                 TEXT,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),      -- when OUR job first saw it on the register
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    celex_first_seen_at TIMESTAMPTZ,                             -- when the register first carried a CELEX
    cellar_first_seen_at TIMESTAMPTZ,                            -- when Cellar was first seen to hold it (the lead time is this minus first_seen_at)
    held_first_seen_at  TIMESTAMPTZ                              -- when our own store was first seen to hold it
);

CREATE INDEX IF NOT EXISTS idx_com_register_seen_date ON public.com_register_seen (doc_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_com_register_seen_num ON public.com_register_seen (doc_year, doc_number);

ALTER TABLE public.com_register_seen ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS com_register_seen_service_all ON public.com_register_seen;
CREATE POLICY com_register_seen_service_all ON public.com_register_seen
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.com_register_seen TO service_role;
REVOKE ALL ON public.com_register_seen FROM anon, authenticated;
