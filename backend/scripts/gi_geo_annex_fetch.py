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
from gi_geo_phase_c7_commune import title_commune


# Romance/German PLURAL commune-list heading ("comuni di ...", "municipios de ...",
# "concelhos de ...", "communes de ..."). Restricting the LAU match to the text AFTER
# such a heading is what makes the Italian/Spanish sheets safe: province phrases
# ("province di Bari, BAT, Brindisi ..." = whole region) and single-comune wrappers
# ("provincia di Frosinone e ... comune di Anagni") sit OUTSIDE the list span, so their
# province-name-as-comune collisions (Frosinone-the-province -> Frosinone-the-comune)
# never enter the matcher.
# plural commune-list heads across the Italian phrasings ("comuni di", "seguenti
# comuni:", "territori comunali di:", "territorio comunale di X, Y e Z") plus the
# Romance/Iberian forms. Bare singular "comune di X" is deliberately NOT here (that is
# a whole-single-comune wrapper, e.g. Anagni) and even if a span slips through, the
# resolve_lau >=2 cluster guard drops any 1-comune result.
# connectors are WORD-BOUNDED: "di"/"de"/"des" must be whole words, NOT the prefix of
# "della"/"delle"/"degli"/"dei" ("comuni della provincia di X" is a province COUNT, not a
# list -- letting "de" match inside "della" captured province names as comuni).
_COMMUNE_LIST_HEAD = re.compile(
    r"\b(?:comuni|comunal[ei]|communes|municipios|municipis|concelhos|freguesias)"
    r"\s*(?:di\b|de\b|des\b|d[’']|:)\s*:?\s*", re.I)
# a "N comuni della provincia di X" / "comuni delle province" phrase means the area is a
# WHOLE province (or several) -- province-level, not an enumerated list. Its presence
# disqualifies the sheet from annex_lau; it stays at its honest NUTS3 province floor.
_PROVINCE_COUNT = re.compile(r"comun[ei]\s+(?:dell[ae]|dei|degli)\s+provinc", re.I)
# stop the span before the following section AND before any province tail
# ("... in provincia di Nuoro") whose province name could collide with a comune.
_LIST_STOP = re.compile(
    r"(\x0c|\n\s*\n|\n\s*\d+\s*[.)]|vitigni|descrizione del legame|principali|"
    r"in\s+provincia|della\s+provincia|nella\s+provincia|\bnuts\b)", re.I)


def commune_span(sec: str) -> str:
    """Concatenate only the enumerated commune-list spans (text after a PLURAL
    'comuni di' style heading), so the LAU matcher never sees surrounding province
    prose. Returns '' when the section is province-level or single-comune only."""
    spans = []
    for m in _COMMUNE_LIST_HEAD.finditer(sec):
        tail = sec[m.end():m.end() + 500]
        s = _LIST_STOP.search(tail)
        spans.append(tail[:s.start()] if s else tail[:300])
    return " , ".join(spans)


def resolve_annex(sec, name, countries, gaz, mw, parent, cluster_only=False):
    """Multi-commune: the >=2 clustering guard on the scoped section. Single-commune
    AOCs (Auxey-Duresses, Beaune, Chablis): fall back to the TITLE-commune match,
    which is clean — matching the section directly leaked fragments of the
    departement name ("La Cote" out of "Cote-d'Or").

    cluster_only=True disables the single-commune title fallback. Use for Italy:
    an Italian GI named after a town (Canelli, Barolo, Bra) spans MANY comuni, so a
    single-comune title write would UNDER-represent and regress the honest province-
    level (name_nuts3) approximation. Only the genuinely-enumerated short lists that
    the summary sheet actually names ("comuni di Vittoria, Comiso, Acate...") should
    win — those come through resolve_lau's >=2 cluster."""
    if cluster_only:
        # IT/ES: match ONLY inside the enumerated commune-list span; skip province-level
        # and single-comune sheets (they stay at their honest province floor / go to 1.2).
        if _PROVINCE_COUNT.search(sec):
            return set()
        span = commune_span(sec)
        return resolve_lau(span, countries, gaz, mw, parent) if span else set()
    codes = resolve_lau(sec, countries, gaz, mw, parent)
    if codes:
        return codes
    return title_commune(name, countries, gaz)

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
    ap.add_argument("--offset", type=int, default=0,
                    help="skip N targets — for chunked runs (the headless chromium context "
                         "hard-crashes over long runs, so process ~50 at a time)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cluster-only", action="store_true",
                    help="disable single-commune title fallback (safe for IT/ES where a "
                         "title-named town spans many comuni)")
    ap.add_argument("--all-coarse", action="store_true",
                    help="target EVERY coarse GI, not only those whose (truncated, "
                         "unreliable) stored geographical_area carries a commune marker. "
                         "The PDF section-scan + resolve_lau cluster guard is the real "
                         "filter; the stored text often lacks the list entirely.")
    ap.add_argument("--revalidate", action="store_true",
                    help="re-check EXISTING annex_lau rows against the current (fixed) "
                         "resolver. Rows that no longer resolve are CLEARED (geometry set "
                         "NULL) so phase C/C6 can re-floor them to their honest NUTS level.")
    a = ap.parse_args()

    roster = requests.get(ROSTER, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=120).json()
    sheet = {x["fileNumber"]: (x.get("summarySheets") or [{}])[0].get("uri")
             for x in roster if x.get("fileNumber")}

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[annex] loading LAU gazetteer...", flush=True)
    gaz, mw, parent = load_lau_gazetteer(cur)
    if a.revalidate:
        where = " AND geo_geom_confidence='annex_lau'"
    else:
        marker = "" if a.all_coarse else \
            " AND geographical_area ~* 'commune|comuni|t[ée]rmino|concelho|gemeinde|localit'"
        where = marker + " AND (geo_geom_confidence LIKE 'name_nuts%%' OR geo_shape IS NULL)"
    cur.execute("""SELECT file_number, protected_name, countries FROM gi_details
        WHERE %s=ANY(countries)""" + where + """
        ORDER BY protected_name""" + (f" LIMIT {a.limit}" if a.limit else "")
        + (f" OFFSET {a.offset}" if a.offset else ""), (a.country,))
    rows = cur.fetchall()
    print(f"[annex] targets: {len(rows)}")

    stats = {"no_sheet": 0, "no_pdf": 0, "no_section": 0, "no_match": 0, "resolved": 0, "cleared": 0}
    def clear(fn):
        """Revert a false-positive annex_lau row to unmapped so phase C/C6 re-floors it."""
        cur.execute("""UPDATE gi_details SET geo_shape=NULL, geo_centroid=NULL,
            geo_area_km2=NULL, geo_geometry=NULL, geo_lau=NULL, geo_nuts=NULL,
            geo_geom_confidence=NULL WHERE file_number=%s""", (fn,))
        stats["cleared"] += 1

    with Browser() as br:
        for fn, nm, ctry in rows:
            aid = sheet.get(fn)
            if not aid:
                stats["no_sheet"] += 1; continue           # transient/roster — never clear
            data = br.pdf(str(aid))
            if not data:
                stats["no_pdf"] += 1; continue              # transient fetch — never clear
            sec = geo_section(pdf_text(data))
            if not sec:
                stats["no_section"] += 1
                if a.revalidate and not a.dry_run:
                    clear(fn)
                continue
            codes = resolve_annex(sec, nm, ctry or [], gaz, mw, parent, cluster_only=a.cluster_only)
            if not codes:
                stats["no_match"] += 1
                if a.revalidate and not a.dry_run:
                    clear(fn)                               # fixed logic rejects it -> revert
                continue
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
