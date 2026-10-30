-- 322: tenders.contract_folder_id, the procedure's id a TED notice states (cbc:ContractFolderID), so a
-- TED notice and the F&T Portal tender of the same procedure are one item (30 Oct 2026, Victor's go;
-- problem register O104 (c)).
--
-- An EU institution's tender is published on the F&T Portal under "<procedure id>-CN" (or -PIN, -EXA)
-- and on TED under a TED number; the only key they share is the procedure id, which the TED notice's
-- XML carries as its root cbc:ContractFolderID (eForms) and Brubru did not store (the parser read a
-- document reference's id under that name, and nothing kept it). On 30 Oct 2026, 224 TED notices
-- (215 from EU buyers) name a procedure id that is a portal tender Brubru holds; 65,790 carry one.
--
-- The column is filled from each notice's stored XML by scripts/backfill_tender_contract_folder_id.py
-- (chunked, without moving updated_at: a fact the notice always had, not a change) and by the TED
-- ingest from then on. Run each statement on its own (CREATE INDEX CONCURRENTLY).
ALTER TABLE public.tenders ADD COLUMN IF NOT EXISTS contract_folder_id TEXT;
COMMENT ON COLUMN public.tenders.contract_folder_id IS
    'The procedure id the notice states (eForms cbc:ContractFolderID); an F&T Portal tender is <it>-CN, -PIN ...';
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenders_contract_folder_id ON public.tenders (contract_folder_id) WHERE contract_folder_id IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ft_calls_for_tenders_procedure_id ON public.ft_calls_for_tenders ((regexp_replace(tender_reference, '-[A-Z]+$', '')));
