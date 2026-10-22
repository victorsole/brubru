"""Gate for EU Canon pages before they ship (22 Oct 2026).

What this catches, each found live on 22 Oct 2026:
  - a translation step's placeholder left in the page ("__MASK0__", "OJ_MASK1__CODE"): the
    Italian detergents page carried six, one inside its footer;
  - blocks still in English in a translation: 9 of 290 translations had 60 to 263 of them;
  - the wrong publisher: 20 pages in 6 languages said "Beresol SL, Brussels". The publisher is
    Beresol BV, registered in Apeldoorn (NL);
  - no credit to the EU source in the footer (Decision 2011/833/EU, Terms 6.3).

Usage (repo root):
    python3.12 backend/scripts/audit_canon_pages.py --slug 2026-405_detergents
    python3.12 backend/scripts/audit_canon_pages.py --all          # report every page
Exit 1 when a checked page fails.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
EUCANON = _REPO_ROOT / "frontend" / "public" / "eucanon"
LANGS = ("ca", "es", "fr", "it", "nl")

PLACEHOLDER = re.compile(r"__MASK|_MASK\d|MASK\d+__")
# A block that still shares more than half its word sequence (and 5+ words) with the English
# one, among blocks of 40+ characters that are not URLs, identifiers or dates.
UNTRANSLATED_RATIO = 0.5
MAX_UNTRANSLATED = 4
MIN_SHARED_WORDS = 5
WORDS = re.compile(r"[^\W\d_]{3,}")
WRONG_SEAT = re.compile(r"Beresol (?:SL|BV)</p>\s*<p>[^<]*(?:Brussel|Bruxelles|Bruselas)", re.S)
EU_CREDIT = ("2011/833", "/terms#data-licence")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        text = " ".join(data.split())
        if not self._skip and text:
            self.out.append(text)


def text_blocks(html: str) -> list[str]:
    parser = _Text()
    parser.feed(html)
    return parser.out


def untranslated_blocks(english: list[str], translated: list[str]) -> list[str]:
    """Blocks of the translation that are still mostly the English, aligned by position.
    Returns None-like empty list when the two pages do not align (structure differs)."""
    if abs(len(english) - len(translated)) > len(english) * 0.1:
        return []
    found = []
    for en, xx in zip(english, translated):
        if len(en) < 40 or re.match(r"^(https?://|CELEX|OJ |[\d/().,\s-]+$)", en):
            continue
        # words only (3+ letters): names, numbers and punctuation are the same in every language
        e, x = WORDS.findall(en.lower()), WORDS.findall(xx.lower())
        m = difflib.SequenceMatcher(None, e, x)
        shared = sum(block.size for block in m.get_matching_blocks())
        if shared >= MIN_SHARED_WORDS and m.ratio() > UNTRANSLATED_RATIO:
            found.append(xx)
    return found


def problems(path: Path, english_blocks: list[str] | None) -> list[str]:
    html = path.read_text(encoding="utf-8")
    found = []
    if PLACEHOLDER.search(html):
        found.append(f"placeholder left: {PLACEHOLDER.search(html).group(0)}")
    if "Beresol SL" in html:
        found.append("publisher written as Beresol SL (it is Beresol BV)")
    if WRONG_SEAT.search(html):
        found.append("publisher address is Brussels (Beresol BV is in Apeldoorn, NL)")
    if not any(c in html for c in EU_CREDIT):
        found.append("no EU source credit in the footer (Decision 2011/833/EU)")
    if english_blocks is not None:
        left = untranslated_blocks(english_blocks, text_blocks(html))
        if len(left) > MAX_UNTRANSLATED:
            found.append(f"{len(left)} blocks still in English, e.g. {left[0][:70]!r}")
    return found


def audit(slug_dirs: list[Path]) -> dict[str, list[str]]:
    report = {}
    for d in slug_dirs:
        en_path = d / "index.html"
        if not en_path.exists():
            continue
        english = text_blocks(en_path.read_text(encoding="utf-8"))
        report[str(en_path.relative_to(EUCANON))] = problems(en_path, None)
        for lang in LANGS:
            p = d / f"{lang}.html"
            if p.exists():
                report[str(p.relative_to(EUCANON))] = problems(p, english)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", action="append", help="canon folder, e.g. 2026-405_detergents (repeatable)")
    group.add_argument("--all", action="store_true", help="every folder under frontend/public/eucanon")
    args = ap.parse_args()
    dirs = sorted(p for p in EUCANON.iterdir() if p.is_dir()) if args.all else [EUCANON / s for s in args.slug]
    missing = [d.name for d in dirs if not (d / "index.html").exists()]
    if args.slug and missing:
        print(f"[ERROR] no such canon page: {', '.join(missing)}")
        return 2
    report = audit(dirs)
    failing = {page: found for page, found in report.items() if found}
    for page, found in sorted(failing.items()):
        for f in found:
            print(f"[FAIL] {page}: {f}")
    print(f"[{'OK' if not failing else 'ERROR'}] {len(report) - len(failing)} of {len(report)} pages pass")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
