"""/api/v2/dpp — the EU Digital Product Passport regime.

Not an institution: a horizontal regulatory regime created by Regulation (EU) 2024/1781
(ESPR) Articles 9 to 15 and operationalised by Commission Implementing Regulation (EU)
2026/1778, which set up the central registry that went live on 20 July 2026.

The folder answers the four questions an operator, a regulator or a passport platform
actually asks, and which no single Commission page answers together:

  * which act binds my product, and what does it oblige      -> /legal-framework
  * when does my sector's passport become mandatory          -> /sectors
  * how does registration work, and what comes back          -> /registry
  * what data must the passport carry, in what shape         -> /data-points, /standards

Every item carries the canonical five datapoints (public_url, body_txt, body_html,
document_date, creation_date). Bodies are composed at backfill time, never at request
time, so the folder answers from the database alone. For the legal-framework resource
the body is the FULL TEXT of the act, not a summary.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="dpp",
    prefix="/dpp",
    body_name="Digital Product Passport",
    acronym="DPP",
    tag="v2-dpp",
    resources=[
        {
            "item_type": "law",
            "slug": "legal-framework",
            "noun": "acts",
            "source": "EUR-Lex and the Publications Office Cellar graph.",
            "extra": (
                "The acts that create digital product passport obligations, each with "
                "its registry hook: the ESPR framework itself, the implementing "
                "regulation for the registry, the harmonised-standards decision, and "
                "the sectoral laws named in Implementing Regulation (EU) 2026/1778 "
                "Article 1 (batteries, construction products, toys, detergents). The "
                "detail endpoint returns the full text of the act."
            ),
        },
        {
            "item_type": "sector",
            "slug": "sectors",
            "noun": "sector profiles",
            "source": "the Commission DPP sector pages and the ESPR working plan.",
            "extra": (
                "One profile per product group in the rollout: batteries, textiles and "
                "apparel, iron and steel, aluminium, tyres, construction products, "
                "furniture, mattresses, toys, detergents and ICT. Each carries the "
                "indicative date its passport becomes mandatory, its legal basis and "
                "the state of its delegated act."
            ),
        },
        {
            "item_type": "registry",
            "slug": "registry",
            "noun": "registry facts",
            "source": "the Commission DPP registry pages and Reg. (EU) 2026/1778.",
            "extra": (
                "How registration works: the production and acceptance environments, "
                "the two registration pathways (user interface and API), what the "
                "unique registration identifier is and, importantly, what it is not "
                "(Article 13(5) states it is not proof of compliance)."
            ),
        },
        {
            "item_type": "standard",
            "slug": "standards",
            "noun": "harmonised standards",
            "source": "Commission Implementing Decision (EU) 2026/1736, Annex.",
            "extra": (
                "The six EN standards whose references were published in the OJ and "
                "which therefore carry a presumption of conformity for DPP "
                "requirements: data exchange protocols, unique identifiers, data "
                "carriers, storage and persistence, APIs, and system interoperability."
            ),
        },
        {
            "item_type": "data_point",
            "slug": "data-points",
            "noun": "data points",
            "source": (
                "Commission guidance 'Digital Batteries Passport: data points by "
                "category', version 1.0 of 28 July 2026."
            ),
            "extra": (
                "The 71 concrete fields the battery passport must carry, each with its "
                "legal source in Regulation (EU) 2023/1542 and its applicability to "
                "electric-vehicle, light-means-of-transport and industrial batteries. "
                "This is the schema a passport platform builds against, and the "
                "template the later sectors follow. Where the guidance layout could "
                "not be read unambiguously the item says so in its body rather than "
                "asserting an obligation: check `applicability_confidence` in the body."
            ),
        },
        {
            "item_type": "guidance",
            "slug": "guidance",
            "noun": "guidance documents",
            "source": "Commission DPP guidance, user guides and FAQs.",
            "extra": (
                "Commission-published guidance including the registry user guide for "
                "economic operators and the battery passport data-point guidance."
            ),
        },
        {
            "item_type": "audience",
            "slug": "audiences",
            "noun": "audience guides",
            "source": "the Commission DPP audience pages.",
            "extra": (
                "What the passport means for each group the regime addresses: economic "
                "operators, consumers, repairers and recyclers, and public authorities."
            ),
        },
        {
            "item_type": "news",
            "slug": "news",
            "noun": "news items",
            "source": "the Commission single-market newsroom, filtered to DPP.",
            "extra": "Commission announcements on the passport, the registry and sector milestones.",
        },
        {
            "item_type": "event",
            "slug": "events",
            "noun": "events",
            "source": "the Commission single-market events listing, filtered to DPP.",
            "extra": "Webinars and stakeholder events on the passport, past and upcoming.",
        },
    ],
)
