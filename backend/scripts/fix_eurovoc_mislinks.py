"""
Step 1b-fix: recover the full body for fragment-suspect acts.

Many CELEX in eu_laws link a fragment (annex / corrigendum) instead of the act
body (one OJ-issue folder mixes several acts, so the local file cannot be
disambiguated by globbing). We refetch those acts authoritatively from the
Publications Office Cellar (publications.europa.eu/resource/celex/{celex}, which
is WAF-free), clean the OJ boilerplate, and update the corpus.

Two modes:
  (default) FETCH  -> writes recovered.jsonl {celex, text, n_words, est_tokens, http_ok}
  --merge          -> rebuilds corpus.jsonl, replacing each fragment record's text
                      with the recovered body when it is longer, recomputing
                      est_tokens + fragment_suspect (now: True iff still < 150 words).

Resumable (recovered.jsonl is append-only; done CELEX are skipped). Polite delay,
retry with backoff. No fabrication: text is the fetched act or the record is marked
http_ok=false and left as-is. No GPU, no LLM.

Run:  python3.12 scripts/fix_eurovoc_mislinks.py --limit 15   # test
      python3.12 scripts/fix_eurovoc_mislinks.py              # full fetch
      python3.12 scripts/fix_eurovoc_mislinks.py --merge      # fold into corpus.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "eurovoc_corpus"
CORPUS = CORPUS_DIR / "corpus.jsonl"
RECOVERED = CORPUS_DIR / "recovered.jsonl"

_HEAD = {"User-Agent": "Brubru/1.0 (EU Policy Assistant; +https://brubru.eu)",
         "Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"}
_BOILER = re.compile(
    r"^([A-Z]_\w+\.\w+\.(xml|fmx)|EN|ENG|Official Journal.*|of the European (Union|Communities)|"
    r"[LCP]\s?\d+/\d+|\d{1,2}\.\d{1,2}\.\d{4}|L series|C series|\d{4}/\d+)\s*$", re.I)


def _clean(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    lines = [l.strip() for l in soup.get_text("\n").split("\n")]
    i = 0
    while i < len(lines) and (not lines[i] or _BOILER.match(lines[i]) or len(lines[i]) < 3):
        i += 1
    txt = "\n".join(l for l in lines[i:] if l)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", txt)).strip()


def _fetch(celex: str, *, tries: int = 3) -> tuple[str, bool]:
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    for attempt in range(tries):
        try:
            r = httpx.get(url, headers=_HEAD, follow_redirects=True, timeout=90)
            if r.status_code != 200:
                return "", False
            txt = _clean(r.text)
            # Accept any 200 with substantive text: short Decisions / Recommendations
            # (types D/E/H) legitimately have no "Article" heading, so a keyword gate
            # wrongly rejected them (audit finding, 1 Jul 2026).
            return (txt, True) if len(txt.split()) >= 20 else ("", False)
        except Exception:
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
    return "", False


def fetch_mode(limit):
    # Re-fetch every SHORT act (< 150 words), regardless of CELEX type. The
    # original fragment flag only caught R/L/D; audit found E (CFSP) and H
    # (recommendations) mis-links too, so the recovery set is length-based.
    frag = [json.loads(l)["celex"] for l in CORPUS.read_text(encoding="utf-8").splitlines()
            if json.loads(l)["n_words"] < 150]
    done = set()
    if RECOVERED.exists():
        done = {json.loads(l)["celex"] for l in RECOVERED.read_text(encoding="utf-8").splitlines()}
    todo = [c for c in frag if c not in done]
    if limit:
        todo = todo[:limit]
    print(f"[fix] {len(frag)} fragment acts | {len(done)} recovered | {len(todo)} to do", flush=True)
    t0 = time.time(); ok = fail = 0
    with RECOVERED.open("a", encoding="utf-8") as f:
        for i, celex in enumerate(todo, 1):
            txt, hit = _fetch(celex)
            nw = len(txt.split())
            f.write(json.dumps({"celex": celex, "text": txt, "n_words": nw,
                                "est_tokens": int(nw * 1.3), "http_ok": hit}, ensure_ascii=False) + "\n")
            ok += hit; fail += (not hit)
            if i % 50 == 0:
                el = time.time() - t0
                print(f"  {i}/{len(todo)} | ok={ok} fail={fail} | {el:.0f}s "
                      f"| ~{(len(todo)-i)/max(1,i)*el/60:.0f} min left", flush=True)
                f.flush()
            time.sleep(0.25)
    print(f"\n[fetch done] recovered ok={ok} fail={fail} in {(time.time()-t0)/60:.1f} min -> {RECOVERED}")


def merge_mode():
    rec = {}
    for l in RECOVERED.read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if r["http_ok"] and r["text"]:
            rec[r["celex"]] = r
    out = []
    replaced = 0
    for l in CORPUS.read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        rc = rec.get(r["celex"])
        if rc and rc["n_words"] > r["n_words"]:
            r["text"] = rc["text"]; r["n_words"] = rc["n_words"]; r["est_tokens"] = rc["est_tokens"]
            r["recovered"] = True
            replaced += 1
        # post-recovery, a fragment is only a truly-tiny stub / unrecoverable act
        r["fragment_suspect"] = r["n_words"] < 50
        out.append(r)
    tmp = CORPUS.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    tmp.replace(CORPUS)
    print(f"[merge] replaced {replaced} fragment bodies with recovered text -> {CORPUS}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    if args.merge:
        merge_mode()
    else:
        fetch_mode(args.limit)


if __name__ == "__main__":
    main()
