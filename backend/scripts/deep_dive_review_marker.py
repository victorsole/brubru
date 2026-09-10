#!/usr/bin/env python3.12
"""D5 (10 September 2026): stamp and read a machine-readable review date per deep-dive.

WHY
---
Deciding today whether the twelve deep-dives were current took an inferred
heuristic, because no page says when it was last checked:

  * `git log` on each page returns the SAME date for all twelve -- 10 September,
    the footer retrofit, which touched every file and changed no content. A
    commit date stopped being a content date the moment a sweep touched
    everything.
  * The fallback was "the newest date the prose happens to mention", which is a
    guess: /csam-regulation's newest mention is 3 August 2027, a forward-looking
    application date, not a review date.

So each page gets `<meta name="brubru:last-reviewed" content="YYYY-MM-DD">`, and
`--report` reads it back. A page reviewed and found already current is stamped
too -- that is the whole point, and the distinction the git date can no longer
make.

The date is NOT invented for pages nobody looked at: --stamp takes an explicit
list of base paths.

USAGE
    python3.12 -m backend.scripts.deep_dive_review_marker --report
    python3.12 -m backend.scripts.deep_dive_review_marker --stamp /eu-inc /biotech-act --date 2026-09-10 --apply
"""
import argparse
import datetime
import pathlib
import re
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = _REPO_ROOT / "frontend" / "public"
META_NAME = "brubru:last-reviewed"
_META_RE = re.compile(r'<meta\s+name="brubru:last-reviewed"\s+content="(\d{4}-\d{2}-\d{2})"\s*/?>')
_ANCHOR = '<meta name="viewport"'


def _pages(base_path: str):
    d = PUBLIC / base_path.lstrip("/")
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.html") if p.name in
                  {"index.html", "ca.html", "es.html", "fr.html", "it.html", "nl.html"})


def _base_paths():
    sys.path.insert(0, str(_REPO_ROOT / "backend"))
    from services.comparator.deep_dives import DEEP_DIVES
    return [d["base_path"] for d in DEEP_DIVES]


def report() -> int:
    print(f"{'deep-dive':36} {'last reviewed':14} pages stamped")
    print("-" * 72)
    unstamped = 0
    for bp in _base_paths():
        pages = _pages(bp)
        if not pages:
            print(f"  {bp[:34]:36} {'(no pages)':14}")
            continue
        dates = {}
        for p in pages:
            m = _META_RE.search(p.read_text(encoding="utf-8", errors="ignore"))
            dates[p.name] = m.group(1) if m else None
        stamped = [v for v in dates.values() if v]
        shown = sorted(set(stamped))
        if not stamped:
            unstamped += 1
        print(f"  {bp[:34]:36} {(','.join(shown) or 'NEVER'):14} {len(stamped)}/{len(pages)}")
    print(f"\n  {unstamped} deep-dive(s) have never been stamped.")
    return 0


def stamp(base_paths, date_str: str, apply: bool) -> int:
    datetime.date.fromisoformat(date_str)      # refuse a malformed date outright
    tag = f'  <meta name="{META_NAME}" content="{date_str}">\n'
    touched = 0
    for bp in base_paths:
        pages = _pages(bp)
        if not pages:
            print(f"  [warn] {bp}: no pages found")
            continue
        for p in pages:
            text = p.read_text(encoding="utf-8")
            if _META_RE.search(text):
                new = _META_RE.sub(f'<meta name="{META_NAME}" content="{date_str}">', text, count=1)
                action = "update"
            elif _ANCHOR in text:
                i = text.index(_ANCHOR)
                j = text.index(">", i) + 1
                new = text[:j] + "\n" + tag.rstrip("\n") + text[j:]
                action = "insert"
            else:
                print(f"  [warn] {p.relative_to(PUBLIC)}: no viewport anchor, skipped")
                continue
            if new != text:
                touched += 1
                if apply:
                    p.write_text(new, encoding="utf-8")
            print(f"  [{action}] {p.relative_to(PUBLIC)} -> {date_str}")
    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {touched} file(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--stamp", nargs="*", metavar="BASE_PATH")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    if not args.stamp:
        raise SystemExit("[ERROR] --stamp needs at least one base path; refusing to "
                         "stamp every page as reviewed when nobody reviewed them.")
    return stamp(args.stamp, args.date, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
