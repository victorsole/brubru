-- Migration 166 (25 Jun 2026) — seed the CERT-EU body row for the
-- /api/v2/cert-eu folder. Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cert_eu', 'cert_eu', 'Interinstitutional services', 'CERT-EU',
  'Cybersecurity Service for the Union institutions, bodies, offices and agencies',
  'The interinstitutional cybersecurity service that supports all EU institutions, bodies, offices and agencies in protecting against, detecting and responding to cyber threats: it issues security advisories on vulnerabilities, publishes threat intelligence (Cyber Briefs and Threat Landscape Reports) and security guidance, runs incident response, and supports the Interinstitutional Cybersecurity Board (IICB).',
  'https://cert.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
