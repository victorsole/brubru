"""Full text of EFSA Journal articles from Europe PMC.

212 EFSA publications in economy_items link the EFSA Journal on Wiley
(efsa.onlinelibrary.wiley.com), which answers every request with a Cloudflare
challenge, so they served no body (5 Oct 2026). The journal is open access and
Europe PMC holds the same articles: DOI -> PMCID -> full-text XML.

A body is stored only when Europe PMC's title matches the row's own title, so a
DOI that resolves to another article can never write its text here.

    python3.12 scripts/fetch_efsa_journal_bodies.py            # dry run
    python3.12 scripts/fetch_efsa_journal_bodies.py --apply
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text  # noqa: E402

from api.v1._body import body_from_html_or_text  # noqa: E402
from core.database import SessionLocal  # noqa: E402

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def _norm(s: str) -> str:
    # Europe PMC writes species names as escaped markup: "&lt;i&gt;Cannabis sativa&lt;/i&gt;".
    s = re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(s or "")))
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Brubru/1.0 (hello@beresol.eu)"})
    return urllib.request.urlopen(req, timeout=60).read()


def full_text(doi: str, title: str) -> tuple[str | None, str]:
    q = urllib.parse.quote(f'DOI:"{doi}"')
    hits = json.loads(_get(f"{EPMC}/search?query={q}&format=json&resultType=core"))
    results = hits.get("resultList", {}).get("result", [])
    if not results:
        return None, "not in Europe PMC"
    hit = results[0]
    if _norm(hit.get("title", ""))[:80] != _norm(title)[:80]:
        return None, "Europe PMC title differs"
    pmcid = hit.get("pmcid")
    if not pmcid:
        return None, "no PMCID (abstract only)"
    root = ET.fromstring(_get(f"{EPMC}/{pmcid}/fullTextXML"))
    parts = []
    for abstract in root.iter("abstract"):
        parts += [" ".join(p.itertext()).strip() for p in abstract.iter("p")]
    body = root.find(".//body")
    if body is not None:
        for el in body.iter():
            if el.tag == "title" and (el.text or "").strip():
                parts.append(" ".join(el.itertext()).strip())
            elif el.tag == "p":
                parts.append(" ".join(el.itertext()).strip())
    txt = "\n\n".join(p for p in parts if p)
    return (txt, "") if len(txt) >= 500 else (None, "full text too short")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    rows = db.execute(text(
        "SELECT id, title, public_url FROM economy_items WHERE body_code = 'efsa' "
        "AND public_url LIKE '%onlinelibrary.wiley.com/doi/%' "
        "AND coalesce(length(body_txt), 0) = 0 ORDER BY id")).fetchall()
    db.close()
    ok, reasons, found = 0, {}, []
    for r in rows:
        doi = r.public_url.split("/doi/", 1)[1].split("?")[0]
        try:
            txt, why = full_text(doi, r.title)
        except Exception as exc:  # noqa: BLE001
            txt, why = None, type(exc).__name__
        if txt:
            ok += 1
            found.append((r.id, txt))
        else:
            reasons[why] = reasons.get(why, 0) + 1
        time.sleep(0.3)
    print(f"[INFO] {len(rows)} rows; full text for {ok}; not stored: {reasons}")
    if args.apply and found:
        db = SessionLocal()
        for rid, txt in found:
            db.execute(text("UPDATE economy_items SET body_txt = :t, body_html = :h, "
                            "fetched_at = now() WHERE id = :id"),
                       {"t": txt, "h": body_from_html_or_text(txt)[0], "id": rid})
        db.commit()
        print(f"[OK] stored {len(found)}")
    return 0 if ok or not rows else 1


if __name__ == "__main__":
    sys.exit(main())
