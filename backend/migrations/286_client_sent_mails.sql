-- 286: client_sent_mails, what each client has already been sent (9 Oct 2026).
--
-- Why: on 9 Oct 2026 the DPP watch said URGENT for a fifth morning running about items the
-- client had received on Monday 5 October: the two JRC workshops, the battery and VAT
-- consultations. The watch decides "urgent" from the item's date alone, so a deadline that
-- has been told stays urgent until it passes, and a real change drowns in the repetition.
-- URGENT has to mean "new AND dated". The watch therefore needs to know what each client
-- has been sent, and it runs on Railway, where a local file would not exist: so a table.
--
-- One row per message sent to a client. It stores NO message text: only the subject, the
-- Gmail thread, the identifiers the message mentioned (normalised URLs, TRIS numbers, OEIL
-- procedure references, Have Your Say initiative ids, parliamentary question numbers) and
-- the dates it mentioned. A deadline counts as "told" only when its date appears among
-- mentioned_dates, so a deadline that moves after the mail is new again.
--
-- Private client data: service_role only, like mcp_requests.

CREATE TABLE IF NOT EXISTS public.client_sent_mails (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_key      TEXT        NOT NULL,                       -- same key as backend/data/client_sources/<key>.json
    sent_at         TIMESTAMPTZ NOT NULL,
    channel         TEXT        NOT NULL DEFAULT 'email',
    subject         TEXT        NOT NULL DEFAULT '',
    thread_ref      TEXT,                                       -- Gmail thread id, or any stable reference
    identifiers     TEXT[]      NOT NULL DEFAULT '{}',          -- normalised, see services/clients/told_ledger.py
    mentioned_dates DATE[]      NOT NULL DEFAULT '{}',
    source          TEXT        NOT NULL DEFAULT 'scan',        -- 'scan' (read from the text) or 'manual'
    note            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT client_sent_mails_source_check CHECK (source IN ('scan', 'manual'))
);

-- One row per (client, thread message): re-recording the same mail updates it, never doubles it.
CREATE UNIQUE INDEX IF NOT EXISTS uq_client_sent_mails_thread
    ON public.client_sent_mails (client_key, thread_ref) WHERE thread_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_client_sent_mails_client_time
    ON public.client_sent_mails (client_key, sent_at DESC);

ALTER TABLE public.client_sent_mails ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS client_sent_mails_service_all ON public.client_sent_mails;
CREATE POLICY client_sent_mails_service_all ON public.client_sent_mails
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.client_sent_mails TO service_role;
REVOKE ALL ON public.client_sent_mails FROM anon, authenticated;
