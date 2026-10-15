-- 294: a tabled text carries the date it was tabled.
--
-- /api/v2/parliament/plenary-tabled-texts served document_date null on all 46 rows
-- GovClipping walked on 15 Oct 2026: the API read adoption_date, which a tabled report or
-- motion never has, and the table kept no other date. EP Open Data gives each plenary
-- document's own date (A-10-2025-0001: 2025-01-17); scripts/sync_plenary_tabled_texts.py
-- writes it here.

ALTER TABLE plenary_tabled_texts ADD COLUMN IF NOT EXISTS document_date date;
CREATE INDEX IF NOT EXISTS plenary_tabled_texts_document_date_idx ON plenary_tabled_texts (document_date);
COMMENT ON COLUMN plenary_tabled_texts.document_date IS
    'The date of the tabled report or motion, from EP Open Data (plenary-documents document_date).';
