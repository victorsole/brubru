"""
Propagate the canonical nav fragment from `_assets/nav.html` into every
`/api/docs/*.html`, marking the active link per page.

Run after editing _assets/nav.html.
"""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "public" / "api" / "docs"
NAV_PATH = DOCS / "_assets" / "nav.html"

# Each docs HTML page → the data-nav value of its own sidebar link
PAGE_NAV = {
    "index.html": "home",
    "authentication.html": "authentication",
    "envelope.html": "envelope",
    "errors.html": "errors",
    "rate-limits.html": "rate-limits",
    "endpoints.html": None,  # endpoints page uses sub-anchors, no single active
    "institutions.html": "institutions",
    "glossary.html": "glossary",
    "use-cases.html": "use-cases",
    "changelog.html": "changelog",
}


def extract_nav(nav_html: str) -> str:
    """Extract the <aside class="sidebar">...</aside> block."""
    m = re.search(r'<aside class="sidebar">.*?</aside>', nav_html, flags=re.DOTALL)
    if not m:
        raise SystemExit("Could not extract <aside> from _assets/nav.html")
    return m.group(0)


def mark_active(nav: str, data_nav: str | None) -> str:
    """Add class="active" to the matching <a data-nav="X">."""
    if not data_nav:
        return nav
    return re.sub(
        rf'<a (href="[^"]+") data-nav="{re.escape(data_nav)}"',
        rf'<a \1 data-nav="{data_nav}" class="active"',
        nav,
    )


def main():
    nav_template = extract_nav(NAV_PATH.read_text(encoding="utf-8"))
    pages_updated = 0
    for filename, active in PAGE_NAV.items():
        path = DOCS / filename
        if not path.exists():
            print(f"  [SKIP] missing: {filename}")
            continue
        html = path.read_text(encoding="utf-8")
        new_nav = mark_active(nav_template, active)
        replaced, n = re.subn(
            r'<aside class="sidebar">.*?</aside>',
            lambda m: new_nav,
            html, count=1, flags=re.DOTALL,
        )
        if n != 1:
            print(f"  [WARN] {filename}: no <aside> block found (n={n})")
            continue
        path.write_text(replaced, encoding="utf-8")
        pages_updated += 1
        print(f"  [OK] {filename}  active={active}")
    print(f"\n{pages_updated}/{len(PAGE_NAV)} pages updated")


if __name__ == "__main__":
    main()
