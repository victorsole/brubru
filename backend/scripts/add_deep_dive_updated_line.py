#!/usr/bin/env python3.12
"""Add the VISIBLE "Updated <date>" line the deep-dive gate expects.

D5 gave every page a machine-readable <meta name="brubru:last-reviewed">. That is
the better instrument -- but there was already a human-facing convention and I
did not look for it first: check_deep_dives.mjs warns when a page has no
"Updated <date>" marker, and industrial-accelerator-act and pharma-laws carry one
as a footer line.

Worth recording that the GATE's version of this check cannot really fail: it
tests /Updated|Actualizado|.../i against the WHOLE page, so eu-inc, biotech-act
and digital-networks-act pass it on ordinary prose ("updated strategic mapping",
"updated to support fibre"). Only two pages have a real marker. The meta tag
stays the machine-readable source; this adds the human-readable one.

Usage:
    python3.12 -m backend.scripts.add_deep_dive_updated_line SLUG --date 2026-09-10 [--apply]
"""
import argparse
import pathlib
import re
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = _REPO_ROOT / "frontend" / "public"

# Month names per language, so the visible line reads naturally rather than ISO.
_MONTHS = {
    "index": ["January","February","March","April","May","June","July","August","September","October","November","December"],
    "es": ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"],
    "ca": ["gener","febrer","març","abril","maig","juny","juliol","agost","setembre","octubre","novembre","desembre"],
    "fr": ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"],
    "it": ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"],
    "nl": ["januari","februari","maart","april","mei","juni","juli","augustus","september","oktober","november","december"],
}
_LEAD = {"index": "Updated {d} {m} {y}.", "es": "Actualizado el {d} de {m} de {y}.",
         "ca": "Actualitzat el {d} de {m} de {y}.", "fr": "Mis à jour le {d} {m} {y}.",
         "it": "Aggiornato il {d} {m} {y}.", "nl": "Bijgewerkt op {d} {m} {y}."}

_EXISTING = re.compile(r"<p[^>]*>\s*(?:Updated|Actualizado el|Actualitzat el|Mis à jour le|Aggiornato il|Bijgewerkt op)\s+\d", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    y, mo, d = (int(x) for x in args.date.split("-"))

    directory = PUBLIC / args.slug
    if not directory.is_dir():
        raise SystemExit(f"[ERROR] {directory} not found")

    changed = 0
    for path in sorted(directory.glob("*.html")):
        key = "index" if path.name == "index.html" else path.stem
        if key not in _LEAD:
            continue
        text = path.read_text(encoding="utf-8")
        if _EXISTING.search(text):
            print(f"  [skip] {path.name} already carries a visible Updated line")
            continue
        line = _LEAD[key].format(d=d, m=_MONTHS[key][mo - 1], y=y)
        tag = f'  <p style="margin-top: 0.5rem;">{line}</p>\n'
        anchor = '<footer class="footer'
        if anchor not in text:
            print(f"  [warn] {path.name}: no canonical footer, skipped")
            continue
        i = text.index(anchor)
        start = text.rindex("\n", 0, i) + 1
        new = text[:start] + tag + text[start:]
        changed += 1
        print(f"  [add ] {path.name}: {line}")
        if args.apply:
            path.write_text(new, encoding="utf-8")
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
