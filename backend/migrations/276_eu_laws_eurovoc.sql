-- 276: the EuroVoc subject terms the Publications Office assigns to each law.
--
-- /laws served policy_area from Brubru's own classifier, which guesses: the 2013
-- decision electing the European Ombudsman read "Energy", a Dutch timber-monitoring
-- decision "Environment", and subject_matter held tokens such as "July" and "No".
-- Victor, 7 October 2026: replace it with the classification Cellar holds for every act.
--
-- eurovoc is [{id, uri, label, domain}] read from Cellar (cdm:work_is_about_concept_eurovoc),
-- labels and domains resolved through eurovoc_concepts (migration 199). eurovoc_domain is
-- the EuroVoc domain most of those descriptors belong to (ties: lowest domain number;
-- 72 GEOGRAPHY only when it is the act's sole domain, since it says where, not what).
-- eu_laws.policy_area is left as it is: the chat and search filter on that taxonomy.
ALTER TABLE eu_laws
    ADD COLUMN IF NOT EXISTS eurovoc            jsonb,
    ADD COLUMN IF NOT EXISTS eurovoc_domain     text,
    ADD COLUMN IF NOT EXISTS eurovoc_fetched_at timestamptz;

COMMENT ON COLUMN eu_laws.eurovoc IS 'EuroVoc descriptors from Cellar: [{id, uri, label, domain}]. [] = Cellar holds none yet.';
COMMENT ON COLUMN eu_laws.eurovoc_domain IS 'EuroVoc domain carried by most descriptors (ties: lowest notation; 72 GEOGRAPHY only if sole). Served as /laws policy_area.';
COMMENT ON COLUMN eu_laws.eurovoc_fetched_at IS 'When the descriptors were last read from Cellar.';

CREATE INDEX IF NOT EXISTS idx_eu_laws_eurovoc_domain ON eu_laws (eurovoc_domain);
