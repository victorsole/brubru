-- 315: ted_award_notices + ted_award_winners, TED contract awards whose buyer is an EU institution,
-- body or agency (26 Oct 2026, funding standard Phase 1 C: who wins contracts like this one).
--
-- Brubru held 104 TED result notices, none with a winner. These tables hold every eForms award
-- notice published since 1 Jan 2024 whose buyer has an EU-body web or e-mail address (TED's own
-- eu-ins-bod-ag label is not enough: about half of the notices it labels come from national buyers),
-- read from each notice's XML by scripts/sync_ted_awards.py (services/scrapers/ted_awards.py).
-- A winner is an organisation of a tender a contract was concluded with; the members of a joint
-- tender are each a row, the lead flagged. Served by /api/v2/funding/tender-awards and, as
-- contractor activities, by /api/v2/funding/partners.

CREATE TABLE IF NOT EXISTS public.ted_award_notices (
    publication_number   TEXT        PRIMARY KEY,          -- TED's "351840-2025"
    notice_uuid          TEXT,                             -- eForms notice identifier (BT-701)
    notice_version       TEXT,                             -- a change notice keeps the uuid, new version
    procedure_uuid       TEXT,
    changed_notice       TEXT,                             -- the uuid-version this notice changes
    superseded_by        TEXT,                             -- a later version of the same notice, held here
    notice_subtype       TEXT,                             -- can-standard, can-social, can-desg ...
    publication_date     DATE,
    dispatch_date        DATE,
    title                TEXT,
    description          TEXT,
    contract_nature      TEXT,                             -- services | supplies | works
    procedure_type       TEXT,                             -- open, restricted, neg-w-call ...
    cpv_main             TEXT,
    cpv_codes            TEXT[],
    body_code            TEXT,                             -- economy_bodies.code, from the buyer's web address
    contracting_authority TEXT,                            -- the first EU buyer's name
    buyer_country        TEXT,                             -- EU style code
    buyer_legal_type     TEXT,                             -- as TED states it
    buyers               JSONB,                            -- every EU buyer: name, country, city, legal_type, website, email
    awarded_value        NUMERIC,                          -- the notice's total value (BT-161), as stated
    awarded_value_currency TEXT,
    lots                 JSONB,                            -- lot_id, title, description, result, tenders_received
    lot_count            INTEGER     NOT NULL DEFAULT 0,
    winner_count         INTEGER     NOT NULL DEFAULT 0,
    public_url           TEXT        NOT NULL,
    body_txt             TEXT,
    body_html            TEXT,
    first_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated         TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ted_award_notices_publication_date ON public.ted_award_notices (publication_date);
CREATE INDEX IF NOT EXISTS idx_ted_award_notices_body_code ON public.ted_award_notices (body_code);
CREATE INDEX IF NOT EXISTS idx_ted_award_notices_uuid ON public.ted_award_notices (notice_uuid);
CREATE INDEX IF NOT EXISTS idx_ted_award_notices_last_updated ON public.ted_award_notices (last_updated);
CREATE INDEX IF NOT EXISTS idx_ted_award_notices_cpv ON public.ted_award_notices USING gin (cpv_codes);
CREATE INDEX IF NOT EXISTS idx_ted_award_notices_fts ON public.ted_award_notices
    USING gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

CREATE TABLE IF NOT EXISTS public.ted_award_winners (
    id                   BIGSERIAL   PRIMARY KEY,
    publication_number   TEXT        NOT NULL REFERENCES public.ted_award_notices (publication_number) ON DELETE CASCADE,
    tender_id            TEXT        NOT NULL,             -- TEN-0001
    org_ref              TEXT        NOT NULL,             -- ORG-0004, unique within the notice
    lot_id               TEXT,
    lot_title            TEXT,
    rank                 INTEGER,
    name                 TEXT        NOT NULL,
    country              TEXT,                             -- EU style code
    city                 TEXT,
    company_id           TEXT,                             -- as the notice gives it (a VAT, register or tax number)
    vat_key              TEXT,                             -- company_id when it is shaped like its own country's VAT number
    size                 TEXT,                             -- micro, small, medium, sme, large, as stated
    is_group_lead        BOOLEAN     NOT NULL DEFAULT false,
    group_size           INTEGER     NOT NULL DEFAULT 1,
    tender_value         NUMERIC,                          -- the tender's value, shared by a group's members
    tender_value_currency TEXT,
    contract_id          TEXT,
    contract_reference   TEXT,
    contract_title       TEXT,
    contract_date        DATE,
    award_date           DATE,
    first_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated         TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (publication_number, tender_id, org_ref)
);

CREATE INDEX IF NOT EXISTS idx_ted_award_winners_vat_key ON public.ted_award_winners (vat_key);
CREATE INDEX IF NOT EXISTS idx_ted_award_winners_country ON public.ted_award_winners (country);
CREATE INDEX IF NOT EXISTS idx_ted_award_winners_name_slug ON public.ted_award_winners
    (country, regexp_replace(lower(name), '[^[:alnum:]]+', '-', 'g'));

ALTER TABLE public.ted_award_notices ENABLE ROW LEVEL SECURITY;
CREATE POLICY ted_award_notices_public_read ON public.ted_award_notices
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.ted_award_notices FROM anon, authenticated;
GRANT SELECT ON public.ted_award_notices TO anon, authenticated;
GRANT ALL ON public.ted_award_notices TO service_role;

ALTER TABLE public.ted_award_winners ENABLE ROW LEVEL SECURITY;
CREATE POLICY ted_award_winners_public_read ON public.ted_award_winners
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.ted_award_winners FROM anon, authenticated;
GRANT SELECT ON public.ted_award_winners TO anon, authenticated;
GRANT ALL ON public.ted_award_winners TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.ted_award_winners_id_seq TO service_role;

CREATE TRIGGER trg_ted_award_notices_touch BEFORE UPDATE ON public.ted_award_notices
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
CREATE TRIGGER trg_ted_award_winners_touch BEFORE UPDATE ON public.ted_award_winners
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
