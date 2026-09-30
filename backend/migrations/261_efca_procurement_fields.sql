-- 261: EFCA procurement rows: drop vacancies, merge duplicates, move to the procurement fields
--
-- API audit, 30 Sep 2026 ("Walk · EFCA"); Victor's decisions that day.
-- * /en/content/open-calls-tender now lists EFCA job vacancies; 2 were stored as tenders.
-- * 26 procedures were stored twice: EFCA moved from /en/node/NNN to slug addresses and
--   the row identity was the address. Keep the OLDER id of each pair, set it to the address
--   EFCA's procedures table links today, delete the newer copy.
-- * tender_reference = the EFCA reference already held in guid (calls for interest hold an
--   address in guid: the old writer read a column name the calls table does not have; the
--   next sync fills their references).
-- * deadline takes the old document_date, and document_date is CLEARED (the ECDC lesson,
--   migration 258): the new reader sets it only from a Funding & Tenders notice.
-- Backup: backend/data/backups/economy_items_efca_procurement_2026_09_30.csv
DELETE FROM public.economy_items
 WHERE body_code = 'efca' AND item_type = 'tender' AND id IN (1461772, 1461773)
   AND public_url LIKE '%/careers/%';
-- * Calls for interest EFCA no longer lists are removed (Victor, 30 Sep 2026: "Remove
--   them"): the 7 stored calls whose address is not among the 6 on EFCA's calls table.
DELETE FROM public.economy_items
 WHERE body_code = 'efca' AND item_type = 'eoi_call'
   AND id IN (483269, 483270, 483271, 483272, 483273, 1461808, 1461809);
DELETE FROM public.economy_items
 WHERE body_code = 'efca' AND item_type = 'tender'
   AND id IN (1461781, 1461782, 1461783, 1461784, 1461785, 1461786, 1461787, 1461788, 1461789, 1461790, 1461791, 1461792, 1461793, 1461794, 1461795, 1461796, 1461797, 1461798, 1461799, 1461800, 1461801, 1461802, 1461803, 1461804, 1461805, 1461806);
UPDATE public.economy_items
   SET public_url = CASE id
         WHEN 483242 THEN 'https://www.efca.europa.eu/en/node/562'
         WHEN 483243 THEN 'https://www.efca.europa.eu/en/node/561'
         WHEN 483244 THEN 'https://www.efca.europa.eu/en/node/589'
         WHEN 483245 THEN 'https://www.efca.europa.eu/en/node/573'
         WHEN 483246 THEN 'https://www.efca.europa.eu/en/node/581'
         WHEN 483247 THEN 'https://www.efca.europa.eu/en/node/578'
         WHEN 483248 THEN 'https://www.efca.europa.eu/en/node/577'
         WHEN 483249 THEN 'https://www.efca.europa.eu/en/node/572'
         WHEN 483250 THEN 'https://www.efca.europa.eu/en/node/592'
         WHEN 483251 THEN 'https://www.efca.europa.eu/en/node/594'
         WHEN 483252 THEN 'https://www.efca.europa.eu/en/node/588'
         WHEN 483253 THEN 'https://www.efca.europa.eu/en/node/580'
         WHEN 483254 THEN 'https://www.efca.europa.eu/en/node/583'
         WHEN 483255 THEN 'https://www.efca.europa.eu/en/node/587'
         WHEN 483256 THEN 'https://www.efca.europa.eu/en/node/495'
         WHEN 483257 THEN 'https://www.efca.europa.eu/en/node/452'
         WHEN 483258 THEN 'https://www.efca.europa.eu/en/node/448'
         WHEN 483259 THEN 'https://www.efca.europa.eu/en/node/443'
         WHEN 483260 THEN 'https://www.efca.europa.eu/en/node/441'
         WHEN 483261 THEN 'https://www.efca.europa.eu/en/node/440'
         WHEN 483262 THEN 'https://www.efca.europa.eu/en/node/439'
         WHEN 483263 THEN 'https://www.efca.europa.eu/en/node/438'
         WHEN 483264 THEN 'https://www.efca.europa.eu/en/node/434'
         WHEN 483265 THEN 'https://www.efca.europa.eu/en/node/436'
         WHEN 483266 THEN 'https://www.efca.europa.eu/en/node/435'
         WHEN 483267 THEN 'https://www.efca.europa.eu/en/node/437'
       END
 WHERE body_code = 'efca' AND id IN (483242, 483243, 483244, 483245, 483246, 483247, 483248, 483249, 483250, 483251, 483252, 483253, 483254, 483255, 483256, 483257, 483258, 483259, 483260, 483261, 483262, 483263, 483264, 483265, 483266, 483267);
UPDATE public.economy_items
   SET tender_reference = CASE WHEN guid NOT LIKE 'http%' THEN guid END,
       deadline = COALESCE(deadline, document_date),
       document_date = NULL
 WHERE body_code = 'efca' AND item_type IN ('tender', 'eoi_call');
