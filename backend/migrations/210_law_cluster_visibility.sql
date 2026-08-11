-- 210: let a compliance package exist without being offered to users.
--
-- Until now every row in law_clusters was browsable, so the catalogue advertised
-- 58 packages of which a substantial minority could not produce a trustworthy
-- gap analysis. Three failure shapes, all found on 10 August 2026:
--
--   1. Single-case decisions. "Amazon State Aid Decision", "China BEV
--      Countervailing Duties" and eight siblings are addressed to one named
--      undertaking or to a Member State ordered to recover aid. Running your own
--      documents against the Apple decision tells you nothing about your company.
--      They are reference material, not self-assessment material.
--
--   2. Too thin to be meaningful. Fewer than 10 binding requirements cannot
--      support a compliance score that anyone should act on.
--
--   3. Mostly somebody else's duties. Where a third or more of the binding
--      requirements bind Member States, the Commission or an EU agency, the
--      report comes back dominated by "not applicable" rows. That is now honest
--      rather than fabricated -- the addressee work saw to that -- but it is
--      still a poor package.
--
-- Hiding is deliberately NOT deleting. The rows, their requirements and their
-- cascade stay exactly as they are, so each can be curated and re-published one
-- at a time without re-ingesting anything. `is_published` is the only thing that
-- changes when a package is ready.
--
-- Default true, so any cluster created later is visible unless someone decides
-- otherwise, and so this migration cannot silently hide future work.

ALTER TABLE public.law_clusters
    ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT true;

COMMENT ON COLUMN public.law_clusters.is_published IS
    'False hides the package from browse, search and the For-you lens. Set false for single-case decisions, packages under 10 binding requirements, and packages where a third or more of the requirements bind someone other than the company being analysed. Direct access by id still works so existing analyses keep resolving.';

CREATE INDEX IF NOT EXISTS idx_law_clusters_published
    ON public.law_clusters (is_published) WHERE is_published;

-- 1. Single-case decisions: addressed to one undertaking or to a Member State.
UPDATE public.law_clusters
   SET is_published = false
 WHERE name ~* '(State Aid|Countervailing|Anti-Dumping|Duties)';

-- 2. Under 10 binding requirements.
UPDATE public.law_clusters c
   SET is_published = false
 WHERE (SELECT count(*) FROM public.law_requirements r
         WHERE r.cluster_id = c.id
           AND COALESCE(r.extra_metadata->>'interpretive', '') <> 'true') < 10;

-- 3. A third or more of the binding requirements bind someone else.
UPDATE public.law_clusters c
   SET is_published = false
 WHERE (SELECT count(*) FROM public.law_requirements r
         WHERE r.cluster_id = c.id
           AND COALESCE(r.extra_metadata->>'interpretive', '') <> 'true') > 0
   AND (SELECT count(*) FROM public.law_requirements r
         WHERE r.cluster_id = c.id
           AND COALESCE(r.extra_metadata->>'interpretive', '') <> 'true'
           AND COALESCE(r.extra_metadata->>'addressee', 'economic_operator') <> 'economic_operator')::numeric
       / (SELECT count(*) FROM public.law_requirements r
           WHERE r.cluster_id = c.id
             AND COALESCE(r.extra_metadata->>'interpretive', '') <> 'true')::numeric >= 0.33;

-- Explicit allowlist, applied last so it overrides every rule above.
-- 58 is the DPP-TEX package built for a named client and verified end to end.
-- 17, 18 and 21 were rebuilt on 10 August 2026 and each was checked against a
-- realistic company policy before being trusted here.
UPDATE public.law_clusters
   SET is_published = true
 WHERE id IN (58, 17, 18, 21);
