-- 211: let a package declare the shape of its own review table.
--
-- The findings table has eight hardcoded columns -- status, article, obligation,
-- criticality, deadline, confidence, evidence, action -- and every one of the 58
-- packages is reviewed through them. That is the right default and the wrong
-- ceiling. A textile Digital Product Passport review wants substance, threshold
-- and test method next to each obligation. A trade-defence package wants the
-- duty rate and the TARIC code, and has no use for a deadline column at all.
-- Neither is a different set of requirements; both are a different table.
--
-- Taken from Mike OSS, whose tabular review workflows carry a `table-columns.yaml`
-- rather than shipping a fixed table per workflow: the system applies fixed
-- prompts and renders whatever the workflow declared.
--
-- `review_profile` is null for every existing package, which means "use the
-- default eight". Nothing changes until a package opts in.
--
-- `extra_fields` holds the values of any declared `extracted` column, keyed by
-- column id. Kept on the finding rather than in a side table because it is
-- written once by the analyser, read with the finding, and never queried on its
-- own.

ALTER TABLE public.law_clusters
    ADD COLUMN IF NOT EXISTS review_profile JSONB;

COMMENT ON COLUMN public.law_clusters.review_profile IS
    'Optional review-table shape for this package: {"columns": [{"id","kind","label"...}]}. Null means the default eight columns. `kind` is "builtin" for one of the known columns or "extracted" for a field the analyser fills per finding into gap_findings.extra_fields.';

ALTER TABLE public.gap_findings
    ADD COLUMN IF NOT EXISTS extra_fields JSONB;

COMMENT ON COLUMN public.gap_findings.extra_fields IS
    'Values for the review profile''s extracted columns, keyed by column id. Null when the package uses the default profile.';

-- Findings are always fetched by analysis, never by extra_fields content, so no
-- index: a GIN index here would cost write time on every run and buy nothing.
