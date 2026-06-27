"""Aggregate the estate scan (estate_scan.jsonl) into the findings that drive the
EU Extract Engine issues report. Safe to run on a partial file (live monitoring).

Run:  python3.12 scripts/extract_estate_report.py [JSONL_PATH]
"""
import json
import sys
from collections import Counter

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    "/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/estate_scan.jsonl"

rows = [json.loads(l) for l in open(PATH) if l.strip()]
n = len(rows)
print(f"# Estate scan report  ({n} URLs)\n")

# --- reachability ---
kinds = Counter(r["kind"] for r in rows)
status = Counter(str(r.get("status")) for r in rows)
print("## URL kinds")
for k, c in kinds.most_common():
    print(f"  {k:9} {c:5}  ({100*c//n}%)")
print("\n## HTTP status")
for s, c in status.most_common(10):
    print(f"  {s:5} {c:5}  ({100*c//n}%)")
challenged = sum(1 for r in rows if r.get("challenged"))
errs = Counter(r.get("err") for r in rows if r.get("status") == "ERR")
print(f"\n  anti-bot challenged: {challenged}")
print(f"  network errors: {dict(errs)}")

# --- platforms (200 HTML only) ---
plat = Counter(r.get("platform") for r in rows if r.get("platform"))
print("\n## Platform distribution (reachable HTML)")
for p, c in plat.most_common():
    print(f"  {p:11} {c:5}")

# --- listing extraction quality ---
listings = [r for r in rows if r["kind"] == "listing" and r.get("status") == 200 and "n" in r]
with_items = [r for r in listings if r.get("n", 0) > 0]
print(f"\n## Listing extraction quality  ({len(listings)} reachable listings)")
if listings:
    print(f"  with items (requests path): {len(with_items)} ({100*len(with_items)//max(len(listings),1)}%)")
    print(f"  needs browser (0 via requests): {sum(1 for r in listings if r.get('needs_browser'))}")
    if with_items:
        avg_date = sum(r.get("date_cov", 0) for r in with_items) / len(with_items)
        print(f"  avg date coverage: {avg_date:.0f}%")
        print(f"  listings <50% dated: {sum(1 for r in with_items if r.get('date_cov',0)<50)}")
        print(f"  listings with junk titles: {sum(1 for r in with_items if r.get('junk',0))}")
        print(f"  listings with mojibake: {sum(1 for r in with_items if r.get('moji',0))}")
        print(f"  listings with duplicate items: {sum(1 for r in with_items if r.get('dup',0))}")
        print(f"  listings with >=2 short titles: {sum(1 for r in with_items if r.get('short',0)>=2)}")
        print(f"  listings with no-url items: {sum(1 for r in with_items if r.get('no_url',0))}")

# --- worst offenders ---
print("\n## Domains needing a browser (top 15)")
nb = Counter(r["domain"] for r in rows if r.get("needs_browser"))
for d, c in nb.most_common(15):
    print(f"  {c:3}  {d}")
print("\n## 404 / error URLs by domain (top 15)")
bad = Counter(r["domain"] for r in rows if r.get("status") in ("404", "ERR") or
              (isinstance(r.get("status"), int) and r["status"] >= 400))
for d, c in bad.most_common(15):
    print(f"  {c:3}  {d}")

# --- source-data hygiene (issues in the api_*.md URLs themselves) ---
zwsp = sum(1 for r in rows if "​" in r["url"])
http = sum(1 for r in rows if r["url"].startswith("http://"))
print(f"\n## Source-data hygiene (api_*.md)")
print(f"  URLs with zero-width spaces: {zwsp}")
print(f"  URLs still http:// (not https): {http}")
