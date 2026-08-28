#!/usr/bin/env python3.12
"""Ensure the Contentsquare (Hotjar) tag is present on every Brubru page.

WHY
---
Contentsquare can only analyse behaviour on pages that carry its tag. Brubru's
public surface is not just the React SPA: the EU Canon deep-dives, the EU Inc
explainer, the API docs, the guides index and the per-law pages are all static
HTML served directly by SiteGround. Until 21 July 2026 only the SPA shell
carried the tag, so every public landing page, which is where most first-touch
traffic arrives, was invisible to analytics.

This script is idempotent and re-runnable. `/hotjar` runs it with --check to
verify coverage before any behaviour review, because a missing tag silently
produces "no sessions" rather than an error.

TAG
---
Current property: f2e32d332b6a1. Replaces 83b75f68fc18e, which was a separate
Contentsquare property; running two tags would split sessions across projects
and double every page's analytics payload. If the property ever changes again,
update CURRENT_TAG_ID and add the old value to SUPERSEDED_TAG_IDS, then re-run
without --check to migrate every page in one pass.

CONSENT (changed 28 Aug 2026)
-----------------------------
Consent-gating is now IMPLEMENTED, and this script enforces it. Pages no longer
carry a tracker `<script src>` directly. They carry the shared consent-gated
loader `/analytics.js`, which reads `brubru_cookie_consent` and only then loads
Contentsquare and Microsoft Clarity.

So the thing this script keeps in sync is the LOADER, not the tag. A raw
`t.contentsquare.net` script found on a page is now a REGRESSION, not the goal:
it would collect before consent. This script migrates any such tag to the
loader. Do not reintroduce the raw tag here; changing the tracker means editing
`frontend/public/analytics.js`, which is the one place both trackers live.

USAGE
-----
    python3.12 scripts/ensure_analytics_tag.py --check   # report only, exit 1 if gaps
    python3.12 scripts/ensure_analytics_tag.py           # apply
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

CURRENT_TAG_ID = "f2e32d332b6a1"
SUPERSEDED_TAG_IDS = ["83b75f68fc18e"]

# The consent-gated loader every page must carry. Both trackers (Contentsquare
# and Clarity) are loaded from inside it, only after the visitor accepts.
LOADER_SRC = "/analytics.js"
TAG = f'<script src="{LOADER_SRC}" defer></script>'

# The loader itself is allowed to name the tracker hosts; it is not a page.
LOADER_FILE = "frontend/public/analytics.js"

REPO = pathlib.Path(__file__).resolve().parents[2]
SPA_SHELL = REPO / "frontend" / "index.html"
PUBLIC_DIR = REPO / "frontend" / "public"

# Fragments and partials that are injected into an already-tagged page. Adding
# a second tag to these would double-count the pageview.
EXCLUDE_SUFFIXES = ("_assets/nav.html",)

# Any direct tracker script, in any attribute order, Contentsquare or Clarity.
ANY_TAG_RE = re.compile(
    r'\s*<script[^>]*(?:t\.contentsquare\.net/uxa/[a-z0-9]+\.js|clarity\.ms/tag/[A-Za-z0-9]+)[^>]*>\s*</script>'
)


def targets() -> list[pathlib.Path]:
    files = [SPA_SHELL] if SPA_SHELL.exists() else []
    for path in sorted(PUBLIC_DIR.rglob("*.html")):
        rel = path.relative_to(REPO).as_posix()
        if any(rel.endswith(s) for s in EXCLUDE_SUFFIXES):
            continue
        if rel == LOADER_FILE:
            continue
        # Stale Finder-style duplicates ("es 2.html"). Left untouched by
        # explicit decision on 21 July 2026: they are not canonical pages.
        if re.search(r" \d+\.html$", path.name):
            continue
        files.append(path)
    return files


def classify(text: str) -> str:
    """A page is 'current' when it carries the consent-gated loader.

    Any direct tracker script is 'superseded' regardless of which property it
    names, because loading a tracker straight from the page defeats the gate.
    """
    has_loader = f'src="{LOADER_SRC}"' in text
    has_raw = "t.contentsquare.net" in text or "clarity.ms/tag/" in text

    if has_loader and not has_raw:
        return "current"
    if has_loader and has_raw:
        return "double"  # loader plus a raw tag: would double-count and pre-consent
    if has_raw:
        return "superseded"
    return "missing"


def apply_tag(text: str) -> tuple[str, str]:
    """Return (new_text, action). Never inserts a second tag."""
    state = classify(text)
    if state == "current":
        return text, "ok"

    if state in ("superseded", "double"):
        cleaned = ANY_TAG_RE.sub("", text)
        if "t.contentsquare.net" in cleaned or "clarity.ms/tag/" in cleaned:
            return text, "manual"  # unrecognised form; do not guess
        text = cleaned
        if state == "double":
            # Loader was already there; removing the raw tag is the whole fix.
            return text, "migrated"

    if "</head>" not in text:
        return text, "no-head"

    # Insert as the last element of <head>, matching the SPA shell.
    idx = text.index("</head>")
    indent = "    " if "\n    " in text[max(0, idx - 200):idx] else "  "
    return text[:idx] + f"{indent}{TAG}\n" + text[idx:], (
        "migrated" if state in ("superseded", "double") else "added"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Report coverage without writing; exit 1 if gaps")
    args = parser.parse_args()

    counts: dict[str, int] = {}
    problems: list[str] = []

    for path in targets():
        text = path.read_text(encoding="utf-8", errors="ignore")
        new_text, action = apply_tag(text)
        counts[action] = counts.get(action, 0) + 1

        rel = path.relative_to(REPO).as_posix()
        if action in ("no-head", "manual"):
            problems.append(f"  {action:9} {rel}")
            continue
        if action == "ok":
            continue
        if not args.check:
            path.write_text(new_text, encoding="utf-8")
        else:
            problems.append(f"  {action:9} {rel}")

    total = sum(counts.values())
    print(f"[{'CHECK' if args.check else 'APPLY'}] consent-gated loader {LOADER_SRC} over {total} page(s)")
    for action in sorted(counts):
        print(f"    {action:10} {counts[action]}")

    if problems:
        label = "pages needing action" if args.check else "pages needing manual review"
        print(f"\n  {label}:")
        for line in problems[:40]:
            print(line)
        if len(problems) > 40:
            print(f"    ... and {len(problems) - 40} more")

    gaps = counts.get("added", 0) + counts.get("migrated", 0) + \
        counts.get("no-head", 0) + counts.get("manual", 0)
    if args.check and gaps:
        return 1
    if counts.get("no-head") or counts.get("manual"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
