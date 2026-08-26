"""Repair the distribution URLs in brubru_dataset_catalog.

Surfacing the catalogue in MEUB Brubru Databases turned its links into things a
user clicks, and clicking them showed the problem: eight distributions declared
format=JSON on https://brubru.beresol.eu/api/..., and that host does not proxy
/api/* at all. SiteGround's SPA fallback answers every one of them with the
React shell, HTTP 200, content-type text/html. A human gets a blank app screen;
a DCAT harvester following /api/datasets.ttl gets HTML labelled JSON.

Three defects, all pre-existing, all invisible while nothing read the table:

1. API distributions on the SiteGround host. They belong on the Railway origin,
   which serves the real JSON (401 without a key, which is the correct answer to
   an unauthenticated call, and proof the route exists).
2. "Brubru v1 REST API" pointed its JSON distribution at /api/v1/, which 404s
   even on the right host. The machine-readable entry point is /openapi.json.
3. The europa.eu source registry pointed at a GitHub path under the wrong
   organisation, and data/ is gitignored, so no corrected form of that URL can
   ever resolve. An unreachable distribution is worse than none: it promises a
   download that does not exist. Removed, and the dataset gets the five missing
   language descriptions so it is not the one English-only card in a Catalan
   user's catalogue.

Verifies by fetching every distribution afterwards and asserting that anything
declared JSON actually answers with JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

SITEGROUND = "https://brubru.beresol.eu"
ORIGIN = "https://brubru-production.up.railway.app"
REGISTRY = "https://brubru.beresol.eu/datasets/europa-source-registry"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# The v1 root is not a document; the OpenAPI spec is.
EXPLICIT = {f"{SITEGROUND}/api/v1/": f"{ORIGIN}/openapi.json"}

REGISTRY_DESC = {
    "en": ("Curated registry of 519 europa.eu sub-portals and feeds Brubru tracks "
           "for legislative and policy news. Each entry carries the source URL, "
           "ingestion method (API / RSS / HTML / Tavily), and current status."),
    "ca": ("Registre curat de 519 subportals i canals d'europa.eu que Brubru "
           "segueix per a notícies legislatives i de política. Cada entrada porta "
           "l'URL de la font, el mètode d'ingesta (API / RSS / HTML / Tavily) i "
           "l'estat actual."),
    "es": ("Registro curado de 519 subportales y canales de europa.eu que Brubru "
           "sigue para noticias legislativas y de política. Cada entrada incluye "
           "la URL de la fuente, el método de ingesta (API / RSS / HTML / Tavily) "
           "y su estado actual."),
    "fr": ("Registre curé de 519 sous-portails et flux europa.eu suivis par Brubru "
           "pour l'actualité législative et politique. Chaque entrée porte l'URL de "
           "la source, la méthode d'ingestion (API / RSS / HTML / Tavily) et son "
           "statut actuel."),
    "it": ("Registro curato di 519 sottoportali e feed di europa.eu seguiti da "
           "Brubru per le notizie legislative e di policy. Ogni voce riporta l'URL "
           "della fonte, il metodo di acquisizione (API / RSS / HTML / Tavily) e lo "
           "stato attuale."),
    "nl": ("Samengesteld register van 519 europa.eu-subportalen en -feeds die "
           "Brubru volgt voor wetgevings- en beleidsnieuws. Elke vermelding bevat "
           "de bron-URL, de inleesmethode (API / RSS / HTML / Tavily) en de huidige "
           "status."),
}


def rewrite(url: str) -> str | None:
    """New URL, or None to drop the distribution entirely."""
    if url in EXPLICIT:
        return EXPLICIT[url]
    if url.startswith(f"{SITEGROUND}/api/") and not url.startswith(f"{SITEGROUND}/api/docs"):
        return ORIGIN + url[len(SITEGROUND):]
    if "github.com" in url and "/data/europa_eu" in url:
        return None
    return url


def probe(url: str) -> tuple[int | str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.getcode(), r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", "")
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        rows = db.execute(text(
            "SELECT dcat_uri, title, distribution FROM brubru_dataset_catalog "
            "ORDER BY title")).fetchall()

        print("=== rewriting distribution URLs ===")
        changed = 0
        for r in rows:
            dists = r.distribution or []
            new = []
            touched = False
            for d in dists:
                old = d.get("access_url") or ""
                nu = rewrite(old)
                if nu is None:
                    print(f"  [DROP] {r.title[:38]:<38} {old}")
                    touched = True
                    continue
                if nu != old:
                    print(f"  [FIX]  {r.title[:38]:<38} {old}\n"
                          f"         {'':<38} -> {nu}")
                    d = {**d, "access_url": nu}
                    touched = True
                new.append(d)
            if touched:
                changed += 1
                if args.apply:
                    db.execute(text(
                        "UPDATE brubru_dataset_catalog SET distribution = CAST(:d AS jsonb), "
                        "updated_at = now() WHERE dcat_uri = :u"),
                        {"d": json.dumps(new, ensure_ascii=False), "u": r.dcat_uri})
        print(f"  {changed} dataset(s) affected")

        print("\n=== the one English-only dataset gets its six languages ===")
        if args.apply:
            db.execute(text(
                "UPDATE brubru_dataset_catalog SET description = CAST(:d AS jsonb), "
                "updated_at = now() WHERE dcat_uri = :u"),
                {"d": json.dumps(REGISTRY_DESC, ensure_ascii=False), "u": REGISTRY})
        print(f"  europa.eu source registry: {sorted(REGISTRY_DESC)}")

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0

        db.commit()

        print("\n=== verification: every distribution, as a client sees it ===")
        rows = db.execute(text(
            "SELECT title, description, distribution FROM brubru_dataset_catalog "
            "ORDER BY title")).fetchall()
        bad = []
        for r in rows:
            for d in (r.distribution or []):
                url = d["access_url"]
                fmt = (d.get("format") or "").upper()
                code, ctype = probe(url)
                # 401 is the right answer to an unauthenticated API call and
                # proves the route exists; 405 proves a POST-only JSON-RPC one.
                reachable = code in (200, 401, 405, 400)
                honest = True
                if fmt == "JSON" and code in (200, 401):
                    honest = "json" in ctype
                ok = reachable and honest
                if not ok:
                    bad.append((url, code, ctype))
                print(f"  {'OK ' if ok else 'BAD'} {str(code):<5} {fmt:<9} "
                      f"{ctype.split(';')[0]:<26} {url}")
        print(f"\n  broken distributions: {len(bad)} "
              f"{'OK' if not bad else 'FAIL'}")

        eng_only = [r.title for r in rows
                    if sorted((r.description or {}).keys()) == ["en"]]
        print(f"  English-only datasets: {len(eng_only)} "
              f"{'OK' if not eng_only else 'FAIL ' + str(eng_only)}")
        no_dist = [r.title for r in rows if not (r.distribution or [])]
        print(f"  datasets with no distribution: {len(no_dist)} "
              f"{no_dist if no_dist else ''}")
        if bad or eng_only:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
