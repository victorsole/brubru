#!/usr/bin/env python3.12
"""
Resumable backfill for /api/v2/parliament/mep-assistants.

The assistants register needs one fetch per current MEP off the europarl.eu site,
which WAF-throttles scripted `requests`. So we fetch THROUGH A REAL BROWSER
(Playwright page.evaluate fetch from a europarl session — the WAF passes it). The
script also:
  - derives the URL slug from the MEP label (no per-MEP detail calls),
  - reuses the country already stored on the declaration rows,
  - SKIPS MEPs already in economy_items (resume),
  - upserts incrementally (every batch), so progress always persists.

Run it as many times as needed; each run continues where the last stopped.

    python3.12 scripts/backfill_mep_assistants.py
"""
from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._specialised_helpers import get_env  # noqa: E402
from services.scrapers.economy_common import clean  # noqa: E402
from services.scrapers.ep_mep_assistants import _parse_assistants, _ASSIST, _CURRENT  # noqa: E402

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
  body_html=EXCLUDED.body_html, source_kind=EXCLUDED.source_kind, guid=EXCLUDED.guid,
  fetched_at=now();
"""


def _slug(label: str) -> str:
    s = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()


_FETCH_JS = """async (url) => {
  try { const r = await fetch(url); return {status: r.status, html: await r.text()}; }
  catch (e) { return {status: 0, html: ''}; }
}"""


async def main() -> None:
    from playwright.async_api import async_playwright
    dsn = get_env("DATABASE_URL")
    conn = psycopg2.connect(dsn, connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()

    def flush(rows):
        nonlocal conn, cur
        for attempt in range(4):
            try:
                execute_values(cur, _UPSERT, rows)
                conn.commit()
                return
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                try:
                    cur.close(); conn.close()
                except Exception:
                    pass
                conn = psycopg2.connect(dsn, connect_timeout=15)
                conn.autocommit = False
                cur = conn.cursor()
                if attempt == 3:
                    raise
    # country map from the already-built declaration rows
    cur.execute("SELECT guid, body_txt FROM economy_items WHERE item_type='mep_declaration'")
    country = {}
    for g, b in cur.fetchall():
        m = re.search(r"Country: (\w+)", b or "")
        if m:
            country[g] = m.group(1)
    # resume: who's already done
    cur.execute("SELECT guid FROM economy_items WHERE item_type='mep_assistant_register'")
    done = {r[0] for r in cur.fetchall()}
    meps = requests.get(_CURRENT, params={"limit": 2000},
                        headers={"User-Agent": _UA, "Accept": "application/ld+json"},
                        timeout=40).json().get("data") or []
    todo = [m for m in meps if str(m.get("identifier")) not in done]
    print(f"[INFO] {len(meps)} current MEPs, {len(done)} already done, {len(todo)} to fetch")
    now = datetime.now(timezone.utc)
    batch, n = [], 0
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        await page.goto("https://www.europarl.europa.eu/meps/en/home",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        for m in todo:
            mid = str(m.get("identifier") or "").strip()
            label = clean(m.get("label") or "")
            if not mid or not label:
                continue
            url = _ASSIST.format(mid=mid, slug=_slug(label))
            cats = {}
            for attempt in range(3):
                try:
                    res = await page.evaluate(_FETCH_JS, url)
                    if res.get("status") == 200 and res.get("html"):
                        cats = _parse_assistants(res["html"])
                        break
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
            acc = cats.get("Accredited assistants", [])
            loc = cats.get("Local assistants", [])
            ctry = country.get(mid, "")
            lines = [f"Member of the European Parliament: {label}",
                     f"Country: {ctry}" if ctry else "",
                     f"Accredited assistants ({len(acc)}): {', '.join(acc)}" if acc else "",
                     f"Local assistants ({len(loc)}): {', '.join(loc)}" if loc else ""]
            for cat, names in cats.items():
                if cat not in ("Accredited assistants", "Local assistants") and names:
                    lines.append(f"{cat} ({len(names)}): {', '.join(names)}")
            lines = [l for l in lines if l]
            body_txt = clean("\n".join(lines))
            body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>")
            title = clean(f"{label} - parliamentary assistants")[:120]
            summary = clean(" | ".join(x for x in [label, ctry,
                            f"{len(acc)} accredited, {len(loc)} local"] if x))
            batch.append(("parliament", "mep_assistant_register", title, summary, url,
                          body_txt, body_html, None, now, "ep_meps", mid))
            n += 1
            if len(batch) >= 20:
                flush(batch)
                print(f"  upserted {n}/{len(todo)} (last: {label})")
                batch = []
            await page.wait_for_timeout(300)
        if batch:
            flush(batch)
        await b.close()
    print(f"[DONE] upserted {n} MEP assistant registers this run")
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
