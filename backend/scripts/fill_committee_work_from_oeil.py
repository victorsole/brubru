#!/usr/bin/env python3.12
"""Give committee work items the text of their OEIL procedure file.

A full walk of /api/v2/parliament/ep-documents (2 Oct 2026) found 548 bodies under
400 characters: the 575 committee work items carry no description, so their body was
committee, role and procedure reference. The procedure file on OEIL is the text of
that work: status, key players, rapporteurs, key events, documents.

505 were filled by copying legislative_carriages.oeil_text_body (the same OEIL page,
already fetched). This reads the rest straight from OEIL through the headless browser
(OEIL is behind the Parliament's WAF) and keeps the page's <main>. Only an empty
full_description is written, and a page that is not a procedure file is refused.

    python3.12 scripts/fill_committee_work_from_oeil.py --rehearse
    python3.12 scripts/fill_committee_work_from_oeil.py --apply
"""
from __future__ import annotations

import argparse
import html as _html
import importlib.util
import pathlib
import re
import sys
from urllib.parse import quote

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

OEIL = "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"
MIN_CHARS = 400

PICK = text("SELECT id, procedure_ref FROM committee_work_items "
            "WHERE coalesce(full_description, '') = '' ORDER BY procedure_ref")
STORE = text("UPDATE committee_work_items SET full_description = :t, last_updated = now() "
             "WHERE id = :i AND coalesce(full_description, '') = ''")


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _main_text(h: str) -> str:
    h = re.sub(r"<(script|style|nav|header|footer|form|noscript|svg)\b[^>]*>.*?</\1>", " ", h,
               flags=re.S | re.I)
    m = re.search(r"<main\b[^>]*>(.*?)</main>", h, flags=re.S | re.I)
    h = m.group(1) if m else h
    h = re.sub(r"</(p|li|h[1-6]|div|tr|td|th)>|<br\s*/?>", "\n", h, flags=re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", h))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    eng = create_engine(_db(), pool_pre_ping=True)
    with eng.connect() as c:
        rows = list(c.execute(PICK))
    print(f"[INFO] committee work items with no text: {len(rows)}")
    if not rows:
        return 0
    spec = importlib.util.spec_from_file_location(
        "waf_browser_fetcher", BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["waf_browser_fetcher"] = mod
    spec.loader.exec_module(mod)
    refs = sorted({r.procedure_ref for r in rows})
    urls = {ref: OEIL.format(ref=quote(ref)) for ref in refs}
    res = mod.fetch_bytes_isolated(list(urls.values()), timeout_s=1800)

    texts, refused = {}, {}
    for ref, u in urls.items():
        st, body, err = res.get(u, (None, b"", "not fetched"))
        t = _main_text(body.decode("utf-8", "ignore")) if body else ""
        # A procedure file states its own reference; a search or error page does not.
        if st == 200 and len(t) >= MIN_CHARS and ref in t:
            texts[ref] = t
        else:
            refused[ref] = f"{st} len={len(t)}"
    print(f"[INFO] procedure files read: {len(texts)} of {len(refs)}")
    for ref, why in list(refused.items())[:10]:
        print(f"   refused {ref}: {why}")
    if args.rehearse:
        for ref, t in list(texts.items())[:3]:
            print(f"   {ref}: {t[:120]!r}")
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    with eng.begin() as c:
        for r in rows:
            if r.procedure_ref in texts:
                n += c.execute(STORE, {"t": texts[r.procedure_ref], "i": r.id}).rowcount
    print(f"[INFO] stored: {n}")
    if n == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every stored text is the work item's own OEIL procedure file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
