"""Council press releases, read from the Council's own RSS feed.

Why (14 Oct 2026): /council-documents held 57 press releases, 14 August to 28 September
2026, and none after. They had been read from the press-release LISTING page by
`ingest_council_documents.py`, which is not scheduled because www.consilium.europa.eu
answers the Railway container with a browser check (HTTP 403). The same host serves an
RSS feed that answers 200, from this machine and from inside the Railway container
(both measured 14 Oct): about 20 items, four or five days of releases.

What it holds: the title, the link, the date (taken from the release's own path,
/en/press/press-releases/YYYY/MM/DD/slug, as the listing reader did), the feed's topic
and its one-paragraph description. Not the release's full text: each release page sits
behind the same browser check, which Brubru does not get past. A row already holding a
longer text keeps it.

Rows are written with the register ingest's own upsert and the listing reader's identity
(PR-YYYYMMDD-slug), so a release is one row whichever route found it.

Exit 1 when the feed cannot be read or lists nothing; 0 otherwise.

    python3.12 scripts/sync_council_press_releases.py            # dry run
    python3.12 scripts/sync_council_press_releases.py --apply
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from scripts.ingest_council_documents import SOURCE_PRESS, _engine, _persist  # noqa: E402
from services.scrapers.council_register import CouncilDoc  # noqa: E402

FEED = "https://www.consilium.europa.eu/en/rss/pressreleases.ashx"
_UA = {"User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu)"}
_PATH_RE = re.compile(r"/en/press/press-releases/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)")
_ATOM_UPDATED = "{http://www.w3.org/2005/Atom}updated"


def _clean(value: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def parse_feed(xml_bytes: bytes) -> list[tuple[CouncilDoc, str]]:
    """(document, description) for each release in the feed, in feed order."""
    out = []
    for item in ET.fromstring(xml_bytes).iter("item"):
        link = (item.findtext("link") or "").strip()
        title = _clean(item.findtext("title"))
        m = _PATH_RE.search(link)
        if not (link and title):
            continue
        if m:
            y, mo, d, slug = m.groups()
            ext_id, published = f"PR-{y}{mo}{d}-{slug[:80]}", date(int(y), int(mo), int(d))
        else:
            guid = (item.findtext("guid") or "").strip()
            updated = (item.findtext(_ATOM_UPDATED) or "")[:10]
            ext_id = f"PR-guid-{guid}" if guid else None
            published = date.fromisoformat(updated) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated) else None
            if not ext_id:
                continue
        topic = _clean(item.findtext("category"))
        out.append((CouncilDoc(external_id=ext_id, title=title, url=link, published=published,
                               subject_matters=[topic] if topic else [], category="press_release"),
                    _clean(item.findtext("description"))))
    return out


COPY_ARTICLE = """
    UPDATE institutional_publications p
       SET html_content = n.body_txt, summary = coalesce(p.summary, left(n.body_txt, 900))
      FROM eu_news_items n
     WHERE p.source_slug = :s
       AND rtrim(n.source_url, '/') = rtrim(p.url, '/')
       AND n.body_source = 'fetched:article' AND length(n.body_txt) >= 500
       AND length(coalesce(p.html_content, '')) < length(n.body_txt)"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    try:
        r = httpx.get(FEED, headers=_UA, timeout=40, follow_redirects=True)
        r.raise_for_status()
        releases = parse_feed(r.content)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] the Council press feed could not be read: {type(exc).__name__}: {exc}")
        return 1
    if not releases:
        print("[ERROR] the Council press feed listed no release")
        return 1

    engine = _engine()
    with engine.connect() as conn:
        stored = dict(conn.execute(text(
            "SELECT external_id, length(coalesce(html_content, '')) FROM institutional_publications "
            "WHERE source_slug = :s AND external_id = ANY(:ids)"),
            {"s": SOURCE_PRESS, "ids": [d.external_id for d, _ in releases]}).fetchall())
    new = [d for d, _ in releases if d.external_id not in stored]
    print(f"[press] {len(releases)} releases in the feed, {len(new)} not held, "
          f"newest {max((d.published for d, _ in releases if d.published), default=None)}")
    for doc, desc in releases:
        mark = "new " if doc.external_id not in stored else "held"
        print(f"  {mark} {doc.published} {doc.title[:90]}")
    if not args.apply:
        print("[press] dry run: nothing written")
        return 0
    inserted = 0
    with engine.begin() as conn:
        for doc, desc in releases:
            # Never trade a longer stored text for the feed's one paragraph.
            body = desc if desc and len(desc) > stored.get(doc.external_id, 0) else None
            inserted += _persist(conn, doc, SOURCE_PRESS, body)
        # The article itself, where the news text job has read it (15 Oct 2026): the same
        # release, at the same address, reaches eu_news_items, whose job reads Council pages
        # through a browser, while this feed carries one paragraph or none. 24 of 77 releases
        # were served with no text; 20 had it there.
        copied = conn.execute(text(COPY_ARTICLE), {"s": SOURCE_PRESS}).rowcount
    print(f"[press] written {len(releases)}, of which new {inserted}; article text copied for {copied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
