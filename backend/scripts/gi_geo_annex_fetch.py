"""
1.1 — annex/technical-document recovery. Coarse-mapped GIs whose real area is an
ENUMERATED municipality list that our first extraction truncated (it grabbed the
"Zone NUTS" subsection instead of the commune prose above it).

Re-fetch the eAmbrosia SUMMARY SHEET (fiche technique) PDF, take the full
delimited-area section, and run the LAU matcher on it (same clustering guard).

The attachment API only serves the PDF to the register's own browser session, so
we fetch through Playwright's request context (direct HTTP 500s / returns the SPA
shell). Attachment id = summarySheets[0].uri from the eAmbrosia roster.

  python3.12 scripts/gi_geo_annex_fetch.py --country FR --limit 8 --dry-run
  python3.12 scripts/gi_geo_annex_fetch.py --country FR
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
import requests
from core.config import settings
from gi_geo_phase_c2 import load_lau_gazetteer, resolve_lau, write_geometry as write_lau_geom

ROSTER = "https://webgate.ec.europa.eu/eambrosia-api/api/v1/geographical-indications"
ATTACH = "https://ec.europa.eu/geographical-indications-register/eambrosia-public-api/api/v1/attachments/{}"
REGISTER = "https://ec.europa.eu/geographical-indications-register/"

# delimited-area / geographical-area headings, and the NUTS subsection that ends the list
_GEO_HEAD = re.compile(
    r"(zone d[ée]limit|aire g[ée]ographique|zona delimitat|zona geogr[áa]fic|"
    r"defined area|geographical area|abgegrenztes gebiet|geografisches gebiet|"
    r"[áa]rea delimitad|[áa]rea geogr[áa]fic|afgebakend|obszar)", re.I)
_GEO_END = re.compile(r"(zone nuts|nuts\b|cartes de la zone|maps of the|a\.\s)", re.I)


def geo_section(text: str) -> str:
    m = _GEO_HEAD.search(text)
    if not m:
        return ""
    tail = text[m.end():m.end() + 4000]
    e = _GEO_END.search(tail)
    return tail[:e.start()] if e else tail[:1500]


class Browser:
    """Playwright request context primed with the register session cookies."""
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._p = sync_playwright().start()
        self.b = self._p.chromium.launch(headless=True)
        self.ctx = self.b.new_context()
        pg = self.ctx.new_page()
        pg.goto(REGISTER, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        return self

    def pdf(self, attach_id: str) -> bytes | None:
        for _ in range(3):
            try:
                r = self.ctx.request.get(ATTACH.format(attach_id), headers={"Accept": "application/pdf,*/*"}, timeout=45000)
                body = r.body()
                if body[:4] == b"%PDF":
                    return body
            except Exception:
                pass
            time.sleep(2)
        return None

    def __exit__(self, *a):
        self.b.close(); self._p.stop()


def pdf_text(data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as f:
        f.write(data); f.flush()
        out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=60)
        return out.stdout.decode("utf-8", "ignore")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    roster = requests.get(ROSTER, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=120).json()
    sheet = {x["fileNumber"]: (x.get("summarySheets") or [{}])[0].get("uri")
             for x in roster if x.get("fileNumber")}

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[annex] loading LAU gazetteer...", flush=True)
    gaz, mw, parent = load_lau_gazetteer(cur)
    cur.execute("""SELECT file_number, protected_name, countries FROM gi_details
        WHERE %s=ANY(countries) AND geographical_area ~* 'commune|comuni|t[ée]rmino|concelho|gemeinde|localit'
          AND (geo_geom_confidence LIKE 'name_nuts%%' OR geo_shape IS NULL)
        ORDER BY protected_name""" + (f" LIMIT {a.limit}" if a.limit else ""), (a.country,))
    rows = cur.fetchall()
    print(f"[annex] targets: {len(rows)}")

    stats = {"no_sheet": 0, "no_pdf": 0, "no_section": 0, "no_match": 0, "resolved": 0}
    with Browser() as br:
        for fn, nm, ctry in rows:
            aid = sheet.get(fn)
            if not aid:
                stats["no_sheet"] += 1; continue
            data = br.pdf(str(aid))
            if not data:
                stats["no_pdf"] += 1; continue
            sec = geo_section(pdf_text(data))
            if not sec:
                stats["no_section"] += 1; continue
            codes = resolve_lau(sec, ctry or [], gaz, mw, parent)
            if not codes:
                stats["no_match"] += 1; continue
            stats["resolved"] += 1
            if a.dry_run:
                cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
                print(f"  {nm[:26]:26} {len(codes)} LAU: {(cur2.fetchone()[0] or '')[:56]}")
            else:
                write_lau_geom(cur, fn, codes)
                cur.execute("UPDATE gi_details SET geo_geom_confidence='annex_lau' WHERE file_number=%s", (fn,))
            if not a.dry_run and stats["resolved"] % 20 == 0:
                print(f"  ...{stats['resolved']} resolved", flush=True)
    print(f"[annex] {stats}")
    c.close()


if __name__ == "__main__":
    main()
