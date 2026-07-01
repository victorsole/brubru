"""
Step 1b of the PyEuroVoc retraining corpus.

Attach the full Formex text to every gold-labelled CELEX from Step 1a, producing
the training corpus:  data/eurovoc_corpus/corpus.jsonl  with one record per act:
  {celex, text, n_words, est_tokens, n_labels, ids, mts, domains,
   n_articles, n_recitals, fragment_suspect}

Text comes from eu_laws.xml_path parsed with the project FormexParser (title +
recitals + article paragraphs). Per CELEX we keep the LONGEST structured parse
across its linked files (some CELEX link a fragment/corrigendum alongside the
main body). No fabrication: text is the parsed act, or empty if unavailable.

fragment_suspect flags an act that SHOULD have a body (a Regulation / Directive /
Decision with gold labels) but parsed to <150 words or no structure. These are the
mis-links (e.g. a big act linked to an annex) to fix later via a Cellar fetch;
they are recorded, not silently kept.

est_tokens is a word x1.3 proxy (fast); exact tokenisation happens at Step 1c/2.
No GPU, no LLM. Read-only DB + local files.

Run:  python3.12 scripts/build_eurovoc_fulltext.py            # full
      python3.12 scripts/build_eurovoc_fulltext.py --limit 300
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.ERROR)  # FormexParser logs per-file parse errors; we handle them

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text as _sql  # noqa: E402
from services.parsers.formex_parser import FormexParser  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO / "backend" / "data" / "eurovoc_corpus"
GOLD = CORPUS_DIR / "gold_labels.jsonl"
OUT = CORPUS_DIR / "corpus.jsonl"
_WS = re.compile(r"[ \t ]+")
_NL = re.compile(r"\n{3,}")
_PARSER = FormexParser()


def _to_text(pl) -> tuple[str, int, int]:
    """(text, n_articles, n_recitals) from a ParsedLaw."""
    parts = [pl.title or ""]
    parts += [r.text for r in pl.recitals if r.text]
    for a in pl.articles:
        if a.title:
            parts.append(a.title)
        parts += [getattr(x, "text", "") or "" for x in a.paragraphs]
    for an in pl.annexes:
        if an.title:
            parts.append(an.title)
    txt = "\n".join(p.strip() for p in parts if p and p.strip())
    txt = _NL.sub("\n\n", _WS.sub(" ", txt)).strip()
    return txt, len(pl.articles), len(pl.recitals)


def _best_parse(paths: list[str]) -> tuple[str, int, int]:
    """Parse each linked file; keep the longest structured text."""
    best = ("", 0, 0)
    for xp in paths:
        fp = REPO / xp
        if not fp.exists():
            continue
        try:
            t, na, nr = _to_text(_PARSER.parse_file(fp))
            if len(t.split()) > len(best[0].split()):
                best = (t, na, nr)
        except Exception:
            continue
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    covered = []
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["ids"]:
            covered.append(r)
    if args.limit:
        covered = covered[: args.limit]

    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["celex"])
            except Exception:
                pass
    todo = [r for r in covered if r["celex"] not in done]

    db = SessionLocal()
    paths_by_celex: dict[str, list[str]] = {}
    codes = [r["celex"] for r in todo]
    for i in range(0, len(codes), 1000):  # batch the xml_path lookup
        chunk = codes[i: i + 1000]
        for c, xp in db.execute(_sql(
                "SELECT celex, xml_path FROM eu_laws WHERE celex = ANY(:cs) AND xml_path <> ''"),
                {"cs": chunk}).fetchall():
            paths_by_celex.setdefault(c, []).append(xp)
    db.close()

    print(f"[fulltext] {len(covered)} gold-labelled | {len(done)} done | {len(todo)} to do", flush=True)
    t0 = time.time()
    n = frag = empty = 0
    with OUT.open("a", encoding="utf-8") as f:
        for r in todo:
            celex = r["celex"]
            txt, na, nr = _best_parse(paths_by_celex.get(celex, []))
            nw = len(txt.split())
            ctype = celex[5] if len(celex) > 5 else ""  # R/L/D/... after the year
            fragment = bool(txt == "" or (ctype in ("R", "L", "D") and (nw < 150 or (na == 0 and nr == 0))))
            rec = {"celex": celex, "text": txt, "n_words": nw, "est_tokens": int(nw * 1.3),
                   "n_labels": len(r["ids"]), "ids": r["ids"], "mts": r["mts"],
                   "domains": r["domains"], "n_articles": na, "n_recitals": nr,
                   "fragment_suspect": fragment}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            frag += fragment
            empty += (txt == "")
            if n % 1000 == 0:
                el = time.time() - t0
                print(f"  {n}/{len(todo)} | frag={frag} empty={empty} | {el:.0f}s "
                      f"| ~{(len(todo)-n)/max(1,n)*el/60:.0f} min left", flush=True)
                f.flush()
    el = time.time() - t0
    print(f"\n[done] wrote {n} records in {el/60:.1f} min | fragment_suspect={frag} "
          f"({100*frag//max(1,n)}%) | empty_text={empty}\n  -> {OUT}")


if __name__ == "__main__":
    main()
