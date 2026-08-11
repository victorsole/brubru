-- 208: allow secondary_acts to hold Commission guidance, not only binding acts.
--
-- secondary_act_type_enum was {delegated, implementing}, which covers the acts
-- that CREATE obligations but not the documents that explain how to meet them:
-- Commission notices, guidelines and interpretive communications, published in
-- the C series. For EU Law Comply those are the second half of the answer -- a
-- user who learns that Article 25 binds them immediately wants the Commission's
-- guidance on applying it.
--
-- Kept in the same table rather than a new one because the relationship is
-- identical (parent act -> derived document) and every consumer already joins
-- on parent_celex. `act_type` is what separates "this imposes a duty on you"
-- from "this explains the duty", and callers that only want binding acts
-- filter on act_type IN ('delegated','implementing').
--
-- ALTER TYPE ... ADD VALUE cannot run inside a transaction block in older
-- Postgres, hence IF NOT EXISTS and a statement of its own.

ALTER TYPE secondary_act_type_enum ADD VALUE IF NOT EXISTS 'guidance';
