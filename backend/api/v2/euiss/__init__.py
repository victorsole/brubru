"""/api/v2/euiss — European Union Institute for Security Studies (api_defence.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="euiss", prefix="/euiss", body_name="European Union Institute for Security Studies",
    acronym="EUISS", tag="v2-euiss",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the EUISS news listing.",
         "extra": "News from the EU Institute for Security Studies on its research, projects and events."},
        {"item_type": "publication", "slug": "publications", "noun": "publications", "source": "the EUISS publications (briefs, Chaillot Papers, analysis, commentary).",
         "extra": "EUISS research output: briefs, Chaillot Papers, analyses, commentary and books on EU foreign policy, security and defence. Filter with q (e.g. a topic or a region)."},
        {"item_type": "event", "slug": "events", "noun": "events", "source": "the EUISS events listing.",
         "extra": "Conferences, webinars and roundtables organised by the EUISS."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of EUISS about, topic, region and project pages.",
         "extra": "Snapshots of the EUISS's about page, its thematic topics (EU foreign policy, global governance, security and defence, transnational challenges, strategic foresight), its regional focuses and its projects (EU Cyber Direct, countering foreign interference, ChipDiplo, SCOPE)."},
    ],
)
