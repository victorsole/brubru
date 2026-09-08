"""Compose the `body_txt` / `body_html` / `body_source` datapoints for a news row.

Why this is a service and not a helper inside one script
--------------------------------------------------------
`eu_news_items` has THREE independent writers (`scripts/sync_dg_news.py`,
`scripts/sync_bespoke_news.py`, `scripts/sync_ft_news.py`) plus a raw-SQL insert in
`scripts/publish_dpp_to_meub.py`. Patching composition into each one guarantees the
fourth writer forgets it, which is the failure in `feedback_cli_wrapper_parity`.

So the single composition function lives here and is applied by a SQLAlchemy
`before_insert` / `before_update` listener on the model (see
`models/eu_news_item.py`). Every ORM writer gets it whether or not the author knew
this existed. `scripts/backfill_eu_news_bodies.py` imports the same function, so the
backfill and the live path can never diverge.

What it composes, and what it must never do
-------------------------------------------
It renders the fields the row holds -- title, summary, institution, date, source URL
-- into a readable body. It does NOT fetch the article and does NOT invent prose.
`body_source` records which shape was produced so a consumer is never misled:

    composed:title+summary   both present
    composed:title           summary empty; headline plus provenance

Writing a plausible-looking article body would be `feedback_backfill_no_hallucination`.
Composing a truthful rendering of known fields is what the v2 five-datapoint contract
requires of structured data (`feedback_api_endpoint_pattern_contract`).
"""
from __future__ import annotations

import html
from typing import Optional, Tuple


def _clean(v) -> str:
    return (v or "").strip()


def compose_news_body(
    title,
    summary,
    institution=None,
    news_date=None,
    url=None,
) -> Tuple[str, str, str]:
    """Return (body_txt, body_html, body_source). Pure and side-effect free."""
    title = _clean(title)
    summary = _clean(summary)
    institution = _clean(institution)
    url = _clean(url)

    when = ""
    if news_date is not None:
        try:
            when = f" on {news_date.isoformat()}"
        except AttributeError:
            when = f" on {news_date}"

    provenance_txt = f"Published by {institution}{when}." if institution else ""
    if url:
        provenance_txt = f"{provenance_txt} Source: {url}".strip()

    parts = [p for p in (title, summary, provenance_txt) if p]
    body_txt = "\n\n".join(parts)

    e_title, e_summary = html.escape(title), html.escape(summary)
    e_inst, e_when = html.escape(institution), html.escape(when)
    e_url = html.escape(url, quote=True)

    chunks = [f"<h1>{e_title}</h1>"]
    if summary:
        chunks.append(f"<p>{e_summary}</p>")
    foot = []
    if institution:
        foot.append(f"Published by {e_inst}{e_when}.")
    if url:
        foot.append(f'<a href="{e_url}" rel="noopener">Source</a>')
    if foot:
        chunks.append(f"<footer><p>{' '.join(foot)}</p></footer>")
    body_html = "<article>" + "".join(chunks) + "</article>"

    body_source = "composed:title+summary" if summary else "composed:title"
    return body_txt, body_html, body_source
