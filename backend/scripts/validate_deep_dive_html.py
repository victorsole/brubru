#!/usr/bin/env python3.12
"""Structural and rendered checks for deep-dive pages.

WHY (22 September 2026)
----------------------
Adding one section to two deep-dives introduced three layout defects that the
markup looked fine for, and only a screenshot caught:

  1. A bare `<h2 class="section__title">` instead of the page's own
     `section > section__header(icon + h2) > card` structure. The heading was
     absorbed into the flex row and the section rendered as unreadable narrow
     columns.
  2. The block inserted INSIDE the following section's `section__header`,
     splitting it and pushing that heading to x=573. That produced 198px of
     horizontal overflow at 375px, which violates the responsive hard rule.
  3. Two `timeline__item active` entries at once, so the page claimed to be at
     two stages of the procedure simultaneously.

Defect 2 repeated on the second page, because the anchor string
`'<div class="section'` also matches `'section__header'`. A person will make
that mistake again; a check will not.

CHECKS
------
Static (no browser, all pages, fast):
  * every `section__title` sits inside a `section__header`
  * `<div>` open and close counts balance
  * at most ONE `timeline__item active`
  * section numbers run 1..N with no gap or repeat
  * zero em-dashes (house style)
  * a `brubru:last-reviewed` meta is present

Rendered (Chromium, opt-in with --render, or automatic with --slug):
  * zero horizontal overflow at 375, 393, 768, 1024, 1440 and 2560px
    -- the six widths CLAUDE.md mandates

USAGE
    python3.12 backend/scripts/validate_deep_dive_html.py              # static, all
    python3.12 backend/scripts/validate_deep_dive_html.py --render     # + browser, all
    python3.12 backend/scripts/validate_deep_dive_html.py --slug /chips-act-2
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Dict, List

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from services.comparator.deep_dives import DEEP_DIVES  # noqa: E402

PUBLIC = _REPO_ROOT / "frontend" / "public"
BREAKPOINTS = (375, 393, 768, 1024, 1440, 2560)

_TITLE_RE = re.compile(r'<h2[^>]*class="section__title"[^>]*>\s*(\d+)?')
# Deep-dives use TWO naming conventions for the current timeline stage, and a
# check that knows only one cannot fail on the other. On 22 September 2026 this
# regex matched `timeline__item active` only, so the rule was dead on 6 of the
# 10 deep-dives -- including EU Inc., the reference page -- which all write the
# BEM modifier `timeline__item--active`. Match both.
_ACTIVE_RE = re.compile(r'timeline__item(?:\s+active\b|--active\b)')
_STYLE_RE = re.compile(r'<style\b.*?</style>', re.S | re.I)
_META_RE = re.compile(r'<meta\s+name="brubru:last-reviewed"\s+content="\d{4}-\d{2}-\d{2}"')


def static_checks(path: pathlib.Path) -> List[str]:
    html = path.read_text(encoding="utf-8", errors="replace")
    fails: List[str] = []

    if html.count("<div") != html.count("</div>"):
        fails.append(f"unbalanced divs: {html.count('<div')} open vs {html.count('</div>')} close")

    # Every section title must sit inside a section__header. A bare h2 is the
    # defect that rendered as narrow columns.
    for m in re.finditer(r'<h2[^>]*class="section__title"', html):
        window = html[max(0, m.start() - 400):m.start()]
        if "section__header" not in window:
            snippet = html[m.start():m.start() + 90].replace("\n", " ")
            fails.append(f"section title NOT inside a section__header: {snippet}")

    # Count in the BODY only. The stylesheet declares rules for the active
    # modifier (`.timeline__item--active::before`, `.timeline__item--active
    # .timeline__date`), and counting those reports three "active items" on a
    # page that has exactly one.
    body = _STYLE_RE.sub("", html)
    n_active = len(_ACTIVE_RE.findall(body))
    if n_active > 1:
        fails.append(f"{n_active} timeline items marked active; exactly one stage can be current")
    if "timeline__item" in body and n_active == 0:
        fails.append("a timeline with no active item; the page names no current stage")

    nums = [int(n) for n in _TITLE_RE.findall(html) if n]
    if nums and nums != list(range(1, len(nums) + 1)):
        fails.append(f"section numbers are not 1..N in order: {nums}")

    if "—" in html:
        fails.append(f"{html.count(chr(0x2014))} em-dash(es); house style is zero")

    if not _META_RE.search(html):
        fails.append("no brubru:last-reviewed meta")

    return fails


def render_checks(paths: List[pathlib.Path]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] playwright missing: overflow NOT measured, this run proves nothing")
        sys.exit(2)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage",
                                    "--no-zygote", "--disable-gpu"])
        for path in paths:
            fails: List[str] = []
            for w in BREAKPOINTS:
                pg = b.new_page(viewport={"width": w, "height": 900})
                pg.goto(path.as_uri())
                pg.wait_for_timeout(450)
                ov = pg.evaluate(
                    "document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if ov > 0:
                    # Name the element, or the report is unactionable.
                    # Ignore anything inside a horizontal SCROLL container.
                    # Deep-dive tables are deliberately `overflow-x:auto` at small
                    # widths, so their cells legitimately extend past the viewport
                    # and dominate a naive "widest element" sort. On nl.html that
                    # pointed at a table header while the real cause was a 4px-wide
                    # language <select>, and it cost a wrong diagnosis.
                    worst = pg.evaluate("""() => {
                        const bad=[];
                        document.querySelectorAll('*').forEach(e=>{
                          const b=e.getBoundingClientRect();
                          if(b.right<=window.innerWidth+2) return;
                          let p=e.parentElement, inScroll=false;
                          while(p){const cs=getComputedStyle(p);
                            if(cs.overflowX==='auto'||cs.overflowX==='scroll'){inScroll=true;break;}
                            p=p.parentElement;}
                          if(!inScroll) bad.push({t:e.tagName,
                            c:(e.className||'').toString().slice(0,26), x:Math.round(b.right)});});
                        return bad.sort((a,b)=>b.x-a.x)[0]||null;}""")
                    fails.append(f"{w}px: {ov}px horizontal overflow (worst: {worst})")
                pg.close()
            if fails:
                out[str(path)] = fails
        b.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", help="only this base_path, e.g. /chips-act-2")
    ap.add_argument("--render", action="store_true", help="also measure overflow in Chromium")
    a = ap.parse_args()

    dds = [d for d in DEEP_DIVES if not a.slug or d["base_path"] == a.slug]
    paths: List[pathlib.Path] = []
    for d in dds:
        paths.extend(sorted((PUBLIC / d["base_path"].lstrip("/")).glob("*.html")))

    print(f"DEEP-DIVE HTML VALIDATION  {len(dds)} deep-dive(s), {len(paths)} page(s)")
    print("=" * 78)

    bad = 0
    for path in paths:
        fails = static_checks(path)
        if fails:
            bad += 1
            rel = path.relative_to(PUBLIC)
            print(f"[FAIL] {rel}")
            for f in fails:
                print(f"        {f}")
    if not bad:
        print(f"[OK] static checks pass on all {len(paths)} page(s)")

    if a.render or a.slug:
        print()
        rendered = render_checks(paths)
        for page, fails in rendered.items():
            bad += 1
            print(f"[FAIL] {pathlib.Path(page).relative_to(PUBLIC)}")
            for f in fails:
                print(f"        {f}")
        if not rendered:
            print(f"[OK] zero horizontal overflow at {', '.join(str(w) for w in BREAKPOINTS)}px "
                  f"on all {len(paths)} page(s)")

    print()
    print(f"{bad} page(s) failed." if bad else "All pages pass.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
