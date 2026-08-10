-- 212: seal a compliance run so it can be shown not to have changed.
--
-- A compliance report today asserts a score. A regulated client needs something
-- else: proof of what was examined, against which obligations, on which date.
-- The manifest fixes the documents (by SHA-256 of the extracted text the
-- analyser actually read), the obligations, the verdicts and the counts, and
-- `manifest_sha256` covers all of it. Where a signing key is configured the
-- digest is signed with Ed25519.
--
-- Sealed at completion rather than on demand: evidence has to be created at the
-- moment of the run. A manifest built later would attest whatever the data
-- happens to look like when someone asks for it, which is the opposite of the
-- point.
--
-- Kept on compliance_analyses rather than in a side table because a manifest is
-- one-to-one with a run, written once, and read with it.

ALTER TABLE public.compliance_analyses
    ADD COLUMN IF NOT EXISTS manifest JSONB,
    ADD COLUMN IF NOT EXISTS manifest_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS manifest_signature TEXT,
    ADD COLUMN IF NOT EXISTS manifest_key_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS sealed_at TIMESTAMPTZ;

COMMENT ON COLUMN public.compliance_analyses.manifest IS
    'What this run examined: document text hashes, obligation hashes, verdict hashes, counts and score. Built at completion by services/compliance/evidence_manifest.py.';
COMMENT ON COLUMN public.compliance_analyses.manifest_sha256 IS
    'SHA-256 over the canonical JSON of `manifest`. Verification recomputes this and compares each part against the current database.';
COMMENT ON COLUMN public.compliance_analyses.manifest_signature IS
    'Base64 Ed25519 signature over manifest_sha256, when COMPLY_SIGNING_KEY is set. Null means the manifest is a checksum only, which detects accident but not a determined party who can also rewrite the digest.';

-- Verification is always by analysis id; a sealed/unsealed split is the only
-- filter worth having and it is tiny.
CREATE INDEX IF NOT EXISTS idx_compliance_analyses_sealed
    ON public.compliance_analyses (sealed_at) WHERE sealed_at IS NOT NULL;
