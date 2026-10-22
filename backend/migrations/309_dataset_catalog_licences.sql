-- 309: one licence rule for Brubru's own datasets (22 Oct 2026).
--
-- The catalogue gave all 8 datasets CC BY 4.0, the paid REST API and the chat
-- guides included, while the Catalan translations said MIT and the Terms said
-- all content was Beresol's. Victor's rule: data given away without a key is
-- CC BY 4.0, data behind a key is under Brubru's own terms (/terms#data-licence).
-- Written as the EU licence list's address (data.europa.eu scores dct:license
-- only when it is in that list), not the creativecommons.org page.
-- The seed scripts take the same rule from services/vocabularies/licences.py.

UPDATE brubru_dataset_catalog
   SET license = CASE
         WHEN dcat_uri IN ('https://brubru.beresol.eu/datasets/catalan-eu-laws',
                           'https://brubru.beresol.eu/datasets/europa-source-registry')
           THEN 'http://publications.europa.eu/resource/authority/licence/CC_BY_4_0'
         ELSE 'https://brubru.beresol.eu/terms#data-licence'
       END,
       updated_at = now()
 WHERE license IS DISTINCT FROM CASE
         WHEN dcat_uri IN ('https://brubru.beresol.eu/datasets/catalan-eu-laws',
                           'https://brubru.beresol.eu/datasets/europa-source-registry')
           THEN 'http://publications.europa.eu/resource/authority/licence/CC_BY_4_0'
         ELSE 'https://brubru.beresol.eu/terms#data-licence'
       END;
