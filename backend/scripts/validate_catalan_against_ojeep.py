#!/usr/bin/env python3
"""
Phase 9 of docs/applications/euvoc.md — OJEEP-style structural validator
for Brubru's Catalan EU-legislation translations.

OJEEP ("OJ European Edition Profiles") describes the structural shape an
Official Journal publication must follow: language declaration, title
block, preamble (visas + recitals), numbered articles, final block.

Provenance honesty (May 2026): the official OJEEP XSDs are not publicly
downloadable via the EU Vocabularies hub at the URLs we tried. This
validator therefore checks the universal OJ-style **structural
pattern** rather than schema-validating against the real XSD. When the
OJEEP XSDs land (Publications Office email or institutional contact),
swap the structural checks for `lxml.etree.XMLSchema(...)` validation
without changing the CLI.

Run:
    python3.12 backend/scripts/validate_catalan_against_ojeep.py
    python3.12 backend/scripts/validate_catalan_against_ojeep.py --celex 32016R0679
    python3.12 backend/scripts/validate_catalan_against_ojeep.py --emit-xml

Exit code 0 if all acts pass; 1 if any structural gap is found.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
CATALAN_DIR = ROOT / "frontend" / "public" / "legislacio-ue-catala"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ojeep-validate")


# ----------------------------------------------------------------------
# Structural checks — universal OJ-style pattern
# ----------------------------------------------------------------------

@dataclass
class Check:
    """One structural assertion against the rendered HTML."""

    key: str
    description: str
    pattern: str
    required: bool = True
    multiplicity_min: int = 1


_CHECKS: List[Check] = [
    Check("lang_declared", "<html lang=\"ca\"> root element", r'<html\s+lang=["\']ca["\']'),
    Check("title_present", "<title> element with non-empty content", r"<title>[^<]+</title>"),
    Check("meta_description", "Meta description for SEO", r'<meta\s+name="description"'),
    Check("disclaimer_banner", "Brubru disclaimer banner (translation-not-official notice)",
          r'class="disclaimer-banner"', required=False),
    Check("doc_header", "Document header block with the act's official title",
          r'class="doc-header"'),
    Check("preamble_init", "Preamble opening line (\"THE COUNCIL ...\" / \"EL CONSELL ...\")",
          r'class="preamble-init"', required=False),
    Check("visa_block", "At least one visa (\"vist el ...\")",
          r'class="visa"', multiplicity_min=1, required=False),
    Check("recital_block", "At least one recital (\"considerant que ...\")",
          r'class="recital"', multiplicity_min=1, required=False),
    Check("preamble_final", "Preamble closing line (\"HAS ADOPTED THIS REGULATION\")",
          r'class="preamble-final"', required=False),
    Check("articles_present", "At least one numbered article",
          r'class="article(?:[ "])', multiplicity_min=1),
    Check("article_title_present", "Each article has a title", r'class="article-title"',
          multiplicity_min=1),
    Check("final_block", "Closing block (signature / date / place)",
          r'class="final-block"', required=False),
    Check("footer", "Footer with Brubru attribution", r'class="footer"', required=False),
]


@dataclass
class Result:
    celex: str
    path: str
    passes: int = 0
    fails: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fails

    def to_dict(self) -> dict:
        return {
            "celex": self.celex,
            "path": self.path,
            "ok": self.ok,
            "passes": self.passes,
            "fails": self.fails,
            "warnings": self.warnings,
        }


def _validate_html(html: str, *, celex: str, path: str) -> Result:
    res = Result(celex=celex, path=path)
    for check in _CHECKS:
        matches = list(re.finditer(check.pattern, html, flags=re.IGNORECASE))
        if len(matches) >= check.multiplicity_min:
            res.passes += 1
        else:
            msg = (
                f"[{check.key}] {check.description} — "
                f"found {len(matches)}, required >= {check.multiplicity_min}"
            )
            if check.required:
                res.fails.append(msg)
            else:
                res.warnings.append(msg)
    return res


# ----------------------------------------------------------------------
# Optional: emit a structural OJEEP-style XML alongside the HTML
# ----------------------------------------------------------------------

def emit_xml_for_act(html: str, celex: str) -> str:
    """Produce an OJEEP-style XML projection of the rendered HTML.

    Captures the same OJ-shape (preamble / visas / recitals / articles)
    that the structural validator checks. Drop-in replacement target for
    when the real OJEEP XSDs land — until then, this is a Brubru-internal
    representation rooted at https://brubru.beresol.eu/ns/ojeep-stub.
    """
    title_match = re.search(r"<title>([^<]+)</title>", html)
    title = title_match.group(1).split(" | ")[0].strip() if title_match else celex

    visas = re.findall(r'<[^>]*class="visa"[^>]*>(.*?)</[^>]*>', html, flags=re.DOTALL | re.IGNORECASE)
    recitals = re.findall(r'<[^>]*class="recital"[^>]*>(.*?)</[^>]*>', html, flags=re.DOTALL | re.IGNORECASE)
    articles = re.findall(
        r'<div[^>]*class="article(?:[^"]*)"[^>]*>(.*?)</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    def _strip(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s).strip()

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<ojeepAct xmlns="https://brubru.beresol.eu/ns/ojeep-stub">',
        f'  <meta>',
        f'    <celex>{celex}</celex>',
        f'    <language>ca</language>',
        f'    <title>{_xml_escape(title)}</title>',
        f'    <generator>brubru.validate_catalan_against_ojeep.emit_xml_for_act</generator>',
        f'  </meta>',
        '  <preamble>',
    ]
    for v in visas:
        parts.append(f"    <visa>{_xml_escape(_strip(v))}</visa>")
    for i, r in enumerate(recitals, 1):
        parts.append(f'    <recital n="{i}">{_xml_escape(_strip(r))}</recital>')
    parts.append('  </preamble>')
    parts.append('  <articles>')
    for i, a in enumerate(articles, 1):
        parts.append(f'    <article n="{i}">{_xml_escape(_strip(a))}</article>')
    parts.append('  </articles>')
    parts.append('</ojeepAct>')
    return "\n".join(parts)


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

# CELEX-shape: sector-digit + 4-year + type-letter(s) + serial. Suffix
# variants ("-softcatala", "-gpt") are tolerated by stripping after "-".
_CELEX_RE = re.compile(r"^\d[A-Z\d]{0,1}\d{4}[A-Z]+\d+")


def _list_acts(celex_filter: Optional[str], *, all_dirs: bool = False) -> Iterable[Path]:
    if not CATALAN_DIR.exists():
        return
    for sub in sorted(CATALAN_DIR.iterdir()):
        if not sub.is_dir():
            continue
        # Strip variant suffix (e.g. "32019D1194-softcatala" -> "32019D1194")
        celex_candidate = sub.name.split("-", 1)[0]
        if not all_dirs and not _CELEX_RE.match(celex_candidate):
            log.info(f"  skipping non-act dir: {sub.name}")
            continue
        if celex_filter and sub.name != celex_filter:
            continue
        index = sub / "index.html"
        if index.exists():
            yield index


def main() -> int:
    parser = argparse.ArgumentParser(description="OJEEP-style structural validator for Brubru Catalan acts")
    parser.add_argument("--celex", default=None, help="Restrict to a single CELEX directory (e.g. 32016R0679)")
    parser.add_argument("--emit-xml", action="store_true", help="Also emit ojeep.xml beside each index.html")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    results: List[Result] = []
    for path in _list_acts(args.celex):
        celex = path.parent.name
        html = path.read_text(encoding="utf-8", errors="replace")
        res = _validate_html(html, celex=celex, path=str(path.relative_to(ROOT)))
        results.append(res)

        if args.emit_xml:
            xml_out = emit_xml_for_act(html, celex)
            xml_path = path.parent / "ojeep.xml"
            xml_path.write_text(xml_out, encoding="utf-8")
            log.info(f"  emitted {xml_path.relative_to(ROOT)}")

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        log.info("=" * 70)
        for r in results:
            status = "OK " if r.ok else "FAIL"
            log.info(f"  [{status}] {r.celex}  passes={r.passes}  fails={len(r.fails)}  warnings={len(r.warnings)}")
            for f in r.fails:
                log.warning(f"      FAIL  {f}")
            for w in r.warnings:
                log.info(f"      WARN  {w}")
        log.info("=" * 70)
        ok_n = sum(1 for r in results if r.ok)
        log.info(f"OVERALL: {ok_n}/{len(results)} acts pass structural validation")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
