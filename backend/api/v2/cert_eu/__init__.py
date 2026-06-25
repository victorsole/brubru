"""
/api/v2/cert-eu — Cybersecurity Service for the Union institutions, bodies, offices
and agencies (CERT-EU).

The EU institutions' cybersecurity service, its own folder. Resources under the
folder prefix: /api/v2/cert-eu/{news,advisories,publications,topics}. cert.europa.eu
serves the blog with plain requests; its publication listings are client-rendered,
so advisories and publications are read through Playwright on the cron path.

Reads from economy_items (body row seeded by migration 166); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cert_eu", prefix="/cert-eu",
    body_name="Cybersecurity Service for the Union institutions, bodies, offices and agencies",
    acronym="CERT-EU", tag="v2-cert-eu",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CERT-EU blog.",
         "extra": "Blog posts from CERT-EU on cyber threats, incidents, defensive "
                  "practices and analysis affecting the EU institutions."},
        {"item_type": "advisory", "slug": "advisories", "noun": "security advisories",
         "source": "the CERT-EU security advisories archive (current and previous year).",
         "extra": "CERT-EU security advisories on vulnerabilities, each with its advisory "
                  "id (e.g. 2026-008), the affected product and the severity, with the "
                  "publication date. Filter with q (e.g. a vendor or product name)."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the CERT-EU threat-intelligence and security-guidance libraries.",
         "extra": "CERT-EU Cyber Briefs, Threat Landscape Reports, threat-intelligence "
                  "frameworks and security guidance, with their publication dates."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CERT-EU about, IICB and publication-hub pages.",
         "extra": "Snapshots of CERT-EU's about page, the Interinstitutional "
                  "Cybersecurity Board (IICB) and its annual reports, and the security "
                  "advisories, security guidance and threat-intelligence hubs."},
    ],
)
