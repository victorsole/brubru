"""Estate-wide CONTRACT validation with hallucination detection.

For one listing per EU body, run the full engine (detail-fetch fills body_txt/body_html
+ document_date) and check, per item:
  - did all 5 target datapoints get populated (or honestly stay empty)?
  - HALLUCINATION guards on the back-filled body:
    * wrongbody: the item's title words appear NOWHERE in body_txt -> the body is probably
      a different page (listing/boilerplate) wrongly assigned.
    * dupbody: two items on the same page share the same body -> one is a wrong fill.
Streams per-body results to JSONL so a multi-hour run is monitorable/resumable.

Run:  PYTHONPATH=. python3.12 -u scripts/extract_contract_validate.py [--limit 6] [--urls PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time

from services.extract import extract

_SIG = re.compile(r"[a-z]{5,}")  # significant title words (>=5 letters)


def _checks(items):
    body_hash = {}
    for it in items:
        b = (it.body_txt or "")
        if b:
            h = hashlib.md5(b[:400].encode("utf-8", "ignore")).hexdigest()
            body_hash[h] = body_hash.get(h, 0) + 1
    out = []
    for it in items:
        b = (it.body_txt or "")
        words = set(_SIG.findall((it.title or "").lower()))
        # body present + title has >=2 content words + NONE appear in body -> suspicious.
        # (>=2 avoids false positives on generic / single-proper-noun titles like
        # "Calls 2019" or "Data Expo Jaarbeurs", whose one significant word legitimately
        # may not sit in the body excerpt.)
        wrongbody = bool(b and len(words) >= 2 and not (words & set(_SIG.findall(b.lower()))))
        h = hashlib.md5(b[:400].encode("utf-8", "ignore")).hexdigest() if b else None
        dupbody = bool(h and body_hash.get(h, 0) > 1)
        out.append({
            "filled": sum(bool(x) for x in [it.public_url, it.body_txt, it.body_html,
                                            it.document_date, it.creation_date]),
            "no_body": not it.body_txt,
            "no_date": not it.document_date,
            "synthetic": bool(it.public_url and "#" in it.public_url),  # JS-span, no real detail page
            "wrongbody": wrongbody,
            "dupbody": dupbody,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--urls", default="/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/all_listings.json")
    ap.add_argument("--out", default="/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/contract_validation.jsonl")
    a = ap.parse_args()
    urls = json.load(open(a.urls))
    print(f"[validate] {len(urls)} bodies, full contract, limit={a.limit} -> {a.out}", flush=True)
    with open(a.out, "w") as fh:
        for i, u in enumerate(urls):
            rec = {"url": u, "domain": u.split("/")[2] if "://" in u else "?"}
            t0 = time.time()
            try:
                r = extract(u, item_type="news", limit=a.limit)
                items = r.get("items", [])
                ch = _checks(items)
                rec.update(n=len(items), via=r["fetched_via"],
                           full=sum(1 for c in ch if c["filled"] == 5),
                           no_body=sum(1 for c in ch if c["no_body"]),
                           no_date=sum(1 for c in ch if c["no_date"]),
                           synthetic=sum(1 for c in ch if c["synthetic"]),
                           wrongbody=sum(1 for c in ch if c["wrongbody"]),
                           dupbody=sum(1 for c in ch if c["dupbody"]),
                           sec=round(time.time() - t0))
            except Exception as e:
                rec.update(error=type(e).__name__, sec=round(time.time() - t0))
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(f"[{i+1}/{len(urls)}] {rec['domain']:42} n={rec.get('n','?'):>2} "
                  f"full={rec.get('full','?')} nobody={rec.get('no_body','?')} "
                  f"HALLUC(wrong={rec.get('wrongbody',0)},dup={rec.get('dupbody',0)}) "
                  f"{rec.get('sec','?')}s {rec.get('error','')}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
