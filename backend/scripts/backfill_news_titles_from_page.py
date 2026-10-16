"""News titles rebuilt from a URL slug get the title the page itself prints (16 Oct 2026).

51 Council press releases on /api/v2/news/all carried a title made from their address:
"Speech by president antonio costa at the opening ceremony of the irish presidency ...",
"Council highlights demographic dimension of europe s housing crisis" (capitals, accents,
apostrophes and commas lost; one French page title kept for an English release). The
stored article holds the real one: its <h1>, or the line whose letters are the slug's.
Only a title whose letters equal the slug's is replaced, and only by a line of the article
whose letters equal them too (or begin with them, a slug being cut at ~200 characters).

    python3.12 scripts/backfill_news_titles_from_page.py            # dry run
    python3.12 scripts/backfill_news_titles_from_page.py --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

ROWS = text("""SELECT id::text AS id, title, source_url, body_txt, body_html FROM eu_news_items
               WHERE institution = 'COUNCIL' AND source_url ~ 'consilium\\.europa\\.eu/.+/press-releases/'""")
STORE = text("UPDATE eu_news_items SET title = :t, updated_at = now() WHERE id = CAST(:id AS uuid)")


def letters(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def slug(url: str | None) -> str:
    return (url or "").rstrip("/").rsplit("/", 1)[-1]


def page_title(title: str, url: str, body_txt: str | None, body_html: str | None) -> str | None:
    """The article's own title when the stored one is its slug, else None."""
    key = letters(slug(url))
    if not key or letters(title) != key or len(key) < 15:
        return None
    candidates = []
    if body_html:
        h1 = BeautifulSoup(body_html, "html.parser").find("h1")
        if h1:
            candidates.append(h1.get_text(" ", strip=True))
    candidates += [ln.strip() for ln in (body_txt or "").split("\n")[:60] if ln.strip()]
    for c in candidates:
        lc = letters(c)
        # The slug may be cut, and a French slug can stand for an English page: the line
        # whose letters equal the slug's, or start with them.
        if lc == key or (len(key) >= 60 and lc.startswith(key)):
            return " ".join(c.split()) if c != title else None
    # A French slug ('declaration-a-la-presse-du-president-costa...') over an English page:
    # the page's own h1 when the body opens with it.
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = list(c.execute(ROWS))
    plan = [(r.id, r.title, page_title(r.title, r.source_url, r.body_txt, r.body_html)) for r in rows]
    plan = [p for p in plan if p[2]]
    slugged = sum(1 for r in rows if letters(r.title) == letters(slug(r.source_url)) and len(letters(r.title)) >= 15)
    print(f"[INFO] {len(rows)} Council press releases; {slugged} titled by their slug; {len(plan)} recoverable")
    for _, old, new in plan[:8]:
        print(f"   {old[:60]!r}\n   -> {new[:90]!r}")
    if not args.apply:
        print("[DRY RUN] nothing written")
        return 0
    with engine.begin() as c:
        for rid, _, new in plan:
            c.execute(STORE, {"id": rid, "t": new})
    print(f"[DONE] {len(plan)} titles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
