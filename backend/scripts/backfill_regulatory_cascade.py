"""Backfill the regulatory cascade and Commission guidance for every cluster law.

What this answers
-----------------
A cluster told a user which act binds them and nothing about what hangs off it.
Only 25 of 351 laws across the 58 clusters had any derived act recorded, so for
326 of them a user could not see the delegated and implementing regulations
that carry the operative detail, nor the Commission notices that explain how to
comply.

How
---
Phase A  Brubru's own v2 endpoint, dogfooded:
         GET /api/v2/legislative/eur-lex/laws/{celex}/relationships
         Keep only cdm:resource_legal_based_on_resource_legal with
         direction=incoming, i.e. acts built ON this law.

Phase B  Titles for everything discovered, in a handful of batched Cellar
         SPARQL queries rather than one HTTP call per act.

Phase C  Classify by CELEX sector and title, then upsert.

Classification, and why the filter matters
------------------------------------------
"Based on" is a wide net. For GDPR it returns 84 acts, and a naive import would
put European Parliament own-initiative resolutions and Commission staff working
documents into a compliance corpus as though they imposed duties. Sector and
document-type codes separate them cleanly:

  3....R/L/D  + "Delegated"    -> delegated     binding, creates obligations
  3....R/L/D  + "Implementing" -> implementing  binding, creates obligations
  5....XC/DC  + guidance words -> guidance      Commission notice, guideline,
                                                Q&A or working plan. The words
                                                are required: the C series is
                                                mostly routine traffic.
  5....IP                      -> EXCLUDED      EP resolution, binds nobody
  5....SC / PC / JC            -> EXCLUDED      staff working doc, proposal
  everything else              -> EXCLUDED

Usage:
  python3.12 -m scripts.backfill_regulatory_cascade --dry-run --limit 10
  python3.12 -m scripts.backfill_regulatory_cascade --apply
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import psycopg2
import psycopg2.extras

API_BASE = "https://brubru-production.up.railway.app"
SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"
BASED_ON = "resource_legal_based_on_resource_legal"

CELEX_RE = re.compile(r"^(?P<sector>\d)(?P<year>\d{4})(?P<type>[A-Z]{1,2})(?P<num>\d+)")

# A C-series document is only guidance if it says so. The first dry run kept
# 469 "guidance" rows from 12 laws, most of them routine publications such as
# "Summary of European Union decisions on marketing authorisations in respect of
# medicinal products", republished several times a year. Extrapolated to 351
# laws that was roughly 15,000 rows of noise presented to users as
# implementation guidance. Require the document to announce itself.
GUIDANCE_WORDS = re.compile(
    r"\b(guidance|guideline|guidelines|interpretative notice|interpretive notice|"
    r"commission notice|questions and answers|working plan|explanatory note|"
    r"technical guidance|best practice)\b", re.IGNORECASE)

# Routine C-series traffic that is not guidance however it is worded.
NOT_GUIDANCE = re.compile(
    r"^\s*(summary of|publication of (an|a) (application|communication)|"
    r"information communicated|list of|notification of|"
    r"authorisation for state aid|prior notification|non-opposition|"
    r"communication in accordance with|update of the list|"
    r"euro exchange rates|call for proposals|invitation to submit)",
    re.IGNORECASE)


def api_key() -> str:
    k = os.environ.get("BRUBRU_API_KEY", "")
    if not k:
        raise SystemExit("BRUBRU_API_KEY not set")
    return k


def connect():
    url = os.environ.get("DATABASE_URL") or ""
    return psycopg2.connect(url.replace(":5432/", ":6543/"), connect_timeout=25)


def fetch_relationships(celex: str, key: str, timeout=90):
    """Acts built ON this law. Returns [] on any failure -- a law we could not
    reach is skipped, never guessed at."""
    url = f"{API_BASE}/api/v2/legislative/eur-lex/laws/{celex}/relationships"
    req = urllib.request.Request(url, headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read())
    except Exception:
        return []
    out = []
    for row in payload.get("data") or []:
        if row.get("direction") != "incoming":
            continue
        if not str(row.get("relation", "")).endswith(BASED_ON):
            continue
        child = row.get("related_celex")
        if child:
            out.append(child)
    return out


def fetch_titles(celexes, chunk=60):
    """One SPARQL round trip per chunk instead of one HTTP call per act."""
    titles = {}
    celexes = sorted(set(celexes))
    for i in range(0, len(celexes), chunk):
        batch = celexes[i:i + chunk]
        values = " ".join(
            f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in batch)
        q = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?title WHERE {{
  VALUES ?celex {{ {values} }}
  ?act cdm:resource_legal_id_celex ?celex .
  ?expr cdm:expression_belongs_to_work ?act ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
        cdm:expression_title ?title .
}}"""
        try:
            url = SPARQL + "?" + urllib.parse.urlencode(
                {"query": q, "format": "application/sparql-results+json"})
            with urllib.request.urlopen(url, timeout=120) as r:
                d = json.loads(r.read())
            for b in d["results"]["bindings"]:
                titles.setdefault(b["celex"]["value"], b["title"]["value"])
        except Exception as exc:
            print(f"    [warn] title batch {i//chunk} failed: {str(exc)[:70]}")
        time.sleep(1)
    return titles


def classify(celex: str, title: str):
    """-> (act_type, status) or None to exclude."""
    m = CELEX_RE.match(celex or "")
    if not m or not title:
        return None
    sector, dtype = m.group("sector"), m.group("type")
    t = title.lower()
    if sector == "3" and dtype in ("R", "L", "D"):
        if "delegated" in t:
            return ("delegated", "adopted")
        if "implementing" in t:
            return ("implementing", "adopted")
        return None            # a base act, not something derived from the parent
    if sector == "5" and dtype in ("XC", "DC"):
        if NOT_GUIDANCE.match(title):
            return None
        if GUIDANCE_WORDS.search(title):
            return ("guidance", "published")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, help="only the first N cluster laws")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cache", default="/tmp/cascade_discovery.json",
                    help="reuse a previous discovery pass instead of re-querying")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the cache and re-query the API")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    key = api_key()
    conn = connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT DISTINCT l.celex, l.title
                     FROM cluster_laws cl JOIN eu_laws l ON l.id = cl.law_id
                    WHERE l.celex IS NOT NULL ORDER BY l.celex""")
    laws = cur.fetchall()
    if args.limit:
        laws = laws[:args.limit]
    cache_path = Path(args.cache)
    cached = None
    if cache_path.exists() and not args.refresh:
        try:
            cached = json.loads(cache_path.read_text())
            if len(cached.get("laws_scanned", [])) != len(laws):
                cached = None      # different law set, discovery is not reusable
        except Exception:
            cached = None

    if cached:
        children = cached["children"]
        titles = cached["titles"]
        print(f"Phases A+B: reusing cached discovery from {args.cache} "
              f"({len(children)} laws with children, {len(titles)} titles). "
              f"Pass --refresh to re-query.")
    else:
        print(f"Phase A: relationships for {len(laws)} cluster laws "
              f"({args.workers} workers)")
        t0 = time.time()
        children = {}
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for law, kids in zip(laws, ex.map(
                    lambda r: fetch_relationships(r["celex"], key), laws)):
                if kids:
                    children[law["celex"]] = kids
        n_pairs = sum(len(v) for v in children.values())
        print(f"  {len(children)} laws returned children, {n_pairs} parent-child pairs "
              f"({time.time()-t0:.0f}s)")

        all_children = {c for v in children.values() for c in v}
        print(f"\nPhase B: titles for {len(all_children)} distinct acts")
        titles = fetch_titles(all_children)
        print(f"  resolved {len(titles)}/{len(all_children)}")
        # Discovery costs ~6 minutes of API time; cache it so classification
        # can be re-tuned without paying for it again.
        cache_path.write_text(json.dumps({
            "laws_scanned": [r["celex"] for r in laws],
            "children": children, "titles": titles}))

    print("\nPhase C: classification")
    kept, excluded = [], Counter()
    for parent, kids in children.items():
        for child in kids:
            title = titles.get(child)
            c = classify(child, title or "")
            if not c:
                m = CELEX_RE.match(child or "")
                excluded[f"{m.group('sector')}...{m.group('type')}" if m else "unparseable"] += 1
                continue
            kept.append((parent, child, title, c[0], c[1]))

    by_type = Counter(k[3] for k in kept)
    print(f"  keep {len(kept)}:  " + "  ".join(f"{k}={v}" for k, v in by_type.most_common()))
    print(f"  exclude {sum(excluded.values())}:  "
          + "  ".join(f"{k}={v}" for k, v in excluded.most_common(8)))
    print("\n  samples kept:")
    for p, c, t, at, st in kept[:6]:
        print(f"    {p} -> {c} [{at}] {(t or '')[:66]}")

    # secondary_acts.reference is UNIQUE, so the table holds ONE row per act
    # regardless of how many parents it derives from -- and derived acts
    # routinely cite several. Deduping on (celex, parent_celex), as the first
    # version did, therefore passed rows the database then rejected:
    # "duplicate key value violates unique constraint secondary_acts_reference_key".
    # Dedupe on the reference, both against what is stored and within this
    # batch, and keep the first parent seen.
    cur.execute("SELECT reference FROM secondary_acts")
    existing = {r["reference"] for r in cur.fetchall()}
    new, seen = [], set()
    for k in kept:
        ref = k[1]
        if ref in existing or ref in seen:
            continue
        seen.add(ref)
        new.append(k)
    print(f"\n  already recorded: {len(kept)-len(new)}   to insert: {len(new)}")

    if not apply:
        conn.rollback(); cur.close(); conn.close()
        print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0

    now = datetime.utcnow()
    for parent, child, title, act_type, status in new:
        cur.execute(
            """INSERT INTO secondary_acts
                   (id, act_type, reference, title, parent_celex, status, celex,
                    source_url, first_seen, last_updated, description)
               VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (reference) DO NOTHING""",
            (act_type, child, (title or child)[:2000], parent, status, child,
             f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{child}",
             now, now,
             f"Derived from {parent}. Discovered via cdm:{BASED_ON} and classified "
             f"by CELEX sector on {now:%Y-%m-%d}."))
    conn.commit()

    cur.execute("""SELECT act_type::text, count(*) FROM secondary_acts
                    WHERE parent_celex IN (
                      SELECT DISTINCT l.celex FROM cluster_laws cl
                        JOIN eu_laws l ON l.id=cl.law_id WHERE l.celex IS NOT NULL)
                    GROUP BY 1 ORDER BY 2 DESC""")
    print(f"\n[OK] inserted {len(new)}. Cluster-law cascade now holds:")
    for t, n in cur.fetchall():
        print(f"  {t:<14} {n}")
    cur.execute("""SELECT count(DISTINCT parent_celex) FROM secondary_acts
                    WHERE parent_celex IN (
                      SELECT DISTINCT l.celex FROM cluster_laws cl
                        JOIN eu_laws l ON l.id=cl.law_id WHERE l.celex IS NOT NULL)""")
    print(f"  cluster laws with cascade data: {cur.fetchone()[0]} (was 25 of 351)")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
