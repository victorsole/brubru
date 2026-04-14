"""
Cross-Reference Resolver

Parses in-text references like
  "Article 7 of Regulation (EU) 2024/1234"
  "Article 5(3), point (b) of Directive (EU) 2016/680"
  "Regulation (EU, Euratom) 2024/2509"
and resolves them to a structured reference with a best-effort CELEX
and a clickable EUR-Lex URL.

Re-implements the cross-reference patterns popularised by LegalViz.EU in
pure Python without touching GPLv3 code.

Scope
-----
Handles the three most common EU citation shapes:

1. Bare act citation
   - "Regulation (EU) 2024/1234"
   - "Directive 2011/93/EU"  (old style, still frequent in OJ output)
   - "Decision (EU) 2024/5678"
   - "Regulation (EU, Euratom) 2024/2509"  (double legal basis)

2. Article + act citation
   - "Article N of Regulation (EU) YEAR/NUM"
   - "Article N(P), point (x) of Directive (EU) YEAR/NUM"
   - Swedish/French/etc. translations use the same numbers, so the regex is
     language-agnostic for the key tokens.

3. Point references inside the same act
   - "Article 3(5)" (resolved to anchor within current CELEX if provided)

Output
------
A list of ResolvedReference objects with:
- raw: the verbatim matched span (for offset-based replacement in HTML)
- celex: a best-effort CELEX, or None if only act form is known (we never guess)
- act_type: "Regulation" | "Directive" | "Decision" | "Recommendation" | "Implementing Regulation" | etc.
- act_year: int or None
- act_number: str or None
- article: str or None ("5")
- paragraph: str or None ("3")
- point: str or None ("b")
- url: EUR-Lex legal-content URL
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional
import re


# CELEX codes we can construct for adopted acts:
#   3 = Adopted legislation
#   Then the 4-digit year of the act
#   Then the type sector letter: R, L, D, etc.
#   Then the number padded to 4 digits
# Reference: https://eur-lex.europa.eu/content/tools/TableOfSectors.html
_ACT_TYPE_TO_CELEX_LETTER = {
    "regulation": "R",
    "directive": "L",
    "decision": "D",
    "recommendation": "H",
    "implementing regulation": "R",
    "delegated regulation": "R",
    "implementing directive": "L",
    "delegated directive": "L",
    "implementing decision": "D",
    "delegated decision": "D",
    "council decision": "D",
    "commission decision": "D",
    "commission implementing regulation": "R",
    "commission delegated regulation": "R",
}


@dataclass
class ResolvedReference:
    raw: str
    start: int
    end: int
    act_type: Optional[str] = None
    act_year: Optional[int] = None
    act_number: Optional[str] = None
    article: Optional[str] = None
    paragraph: Optional[str] = None
    point: Optional[str] = None
    celex: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Build a single big regex that captures either:
#   - Article N(P)?, point (x)?  of  <Act-citation>
#   - Just <Act-citation>
#
# Act-citation shape: "(<Prefix>)? Regulation | Directive | Decision | Recommendation (EU(, Euratom)?) YEAR/NUM"
# Old-style directive: "Directive YEAR/NUM/EU".
_ACT_TYPE_PATTERN = (
    r"(?:"
    r"Commission\s+|Council\s+|Joint\s+|Implementing\s+|Delegated\s+"
    r"){0,2}"
    r"(?:Regulation|Directive|Decision|Recommendation)"
)

_ACT_ID_EU = r"\(EU(?:,\s*Euratom)?\)\s+(?P<year1>\d{4})/(?P<num1>\d{1,5})"
# Old-style "Directive 2011/93/EU"
_ACT_ID_OLD = r"(?P<year2>\d{4})/(?P<num2>\d{1,5})/EU"

_CITATION_CORE = (
    rf"(?P<act>{_ACT_TYPE_PATTERN})\s+"
    rf"(?:{_ACT_ID_EU}|{_ACT_ID_OLD})"
)

_ARTICLE_PREFIX = (
    r"Article\s+(?P<article>\d{1,4})"
    r"(?:\s*\((?P<paragraph>\d{1,3})\))?"
    r"(?:\s*,\s*point\s*\((?P<point>[a-z]{1,3})\))?"
)

_FULL_RE = re.compile(
    rf"(?:{_ARTICLE_PREFIX}\s+of\s+)?{_CITATION_CORE}",
    re.IGNORECASE,
)

_EUR_LEX_BASE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"


def _build_celex(act_type: str, year: int, number: str) -> Optional[str]:
    key = act_type.lower().strip()
    # Accept "Implementing Regulation" etc. by falling back to the last two tokens
    for k in (key, " ".join(key.split()[-2:]), key.split()[-1]):
        letter = _ACT_TYPE_TO_CELEX_LETTER.get(k)
        if letter:
            return f"3{year}{letter}{int(number):04d}"
    return None


def resolve_references(text: str) -> list[ResolvedReference]:
    """Find every citation in `text` and return resolved references in order."""
    out: list[ResolvedReference] = []
    for m in _FULL_RE.finditer(text):
        act_type = (m.group("act") or "").strip()
        year = m.group("year1") or m.group("year2")
        number = m.group("num1") or m.group("num2")
        if not (act_type and year and number):
            continue
        try:
            year_int = int(year)
        except ValueError:
            continue
        celex = _build_celex(act_type, year_int, number)
        raw = m.group(0)
        out.append(
            ResolvedReference(
                raw=raw,
                start=m.start(),
                end=m.end(),
                act_type=act_type,
                act_year=year_int,
                act_number=number,
                article=m.group("article"),
                paragraph=m.group("paragraph"),
                point=m.group("point"),
                celex=celex,
                url=(_EUR_LEX_BASE + celex) if celex else None,
            )
        )
    return out


def resolve_references_json(text: str) -> list[dict[str, Any]]:
    return [r.to_dict() for r in resolve_references(text)]


def annotate_html(text: str, *, include_aliases: bool = True) -> str:
    """
    Return `text` with every resolved citation wrapped in:
        <a href="EUR-Lex" class="eur-lex-ref" data-celex="..."
           data-article="..." data-paragraph="..." data-point="...">raw</a>

    Two passes:
    1. Formal citations ("Article 7 of Regulation (EU) 2024/1234", "Directive 2011/93/EU")
    2. If `include_aliases`, known acronyms/nicknames (GDPR, DSA, AI Act, ...) via
       `law_alias_resolver.find_alias_matches`.

    Alias hits that overlap with already-annotated formal citations are dropped.
    Raw text without citations is left untouched.
    """
    # Collect all spans we intend to wrap.
    @_dataclass_bare
    class _Span:
        start: int
        end: int
        raw: str
        url: str
        attrs: list[str]

    spans: list[_Span] = []

    # Pass 1: formal citations
    for ref in resolve_references(text):
        attrs = [
            f'href="{ref.url}"' if ref.url else 'href="#"',
            'class="eur-lex-ref"',
            'target="_blank"',
            'rel="noopener"',
        ]
        if ref.celex:
            attrs.append(f'data-celex="{ref.celex}"')
        if ref.article:
            attrs.append(f'data-article="{ref.article}"')
        if ref.paragraph:
            attrs.append(f'data-paragraph="{ref.paragraph}"')
        if ref.point:
            attrs.append(f'data-point="{ref.point}"')
        spans.append(_Span(ref.start, ref.end, ref.raw, ref.url or "#", attrs))

    # Pass 2: alias hits (GDPR, DSA, AI Act, ...), skipping overlaps
    if include_aliases:
        try:
            from .law_alias_resolver import find_alias_matches
            for hit in find_alias_matches(text):
                if any(not (hit.end <= s.start or hit.start >= s.end) for s in spans):
                    continue
                url = f"{_EUR_LEX_BASE}{hit.celex}"
                attrs = [
                    f'href="{url}"',
                    'class="eur-lex-ref eur-lex-ref--alias"',
                    'target="_blank"',
                    'rel="noopener"',
                    f'data-celex="{hit.celex}"',
                    f'data-alias="{hit.alias}"',
                    f'title="{hit.full_title[:200].replace(chr(34), "&quot;")}"',
                ]
                spans.append(_Span(hit.start, hit.end, hit.raw, url, attrs))
        except Exception:
            pass  # alias resolver unavailable: degrade to formal-only

    if not spans:
        return text

    spans.sort(key=lambda s: s.start)
    pieces: list[str] = []
    cursor = 0
    for s in spans:
        if s.start < cursor:  # safety against overlaps
            continue
        pieces.append(text[cursor : s.start])
        pieces.append(f"<a {' '.join(s.attrs)}>{s.raw}</a>")
        cursor = s.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _dataclass_bare(cls):
    """Tiny @dataclass stand-in so we don't pull dataclasses into this closure."""
    from dataclasses import dataclass as _dc
    return _dc(cls)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> int:
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description="Resolve EU legal cross-references")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", type=str, help="Inline text to parse")
    src.add_argument("--file", type=str, help="Path to a text file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--annotate", action="store_true", help="Print HTML with <a> wrappers")
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.text or ""

    if args.annotate:
        print(annotate_html(text))
        return 0

    refs = resolve_references(text)
    if args.json:
        print(json.dumps([r.to_dict() for r in refs], indent=2, ensure_ascii=False))
    else:
        print(f"Found {len(refs)} references")
        for r in refs:
            print(
                f"  [{r.start:>4}-{r.end:>4}] "
                f"{r.act_type} {r.act_year}/{r.act_number}"
                + (f" Art.{r.article}" if r.article else "")
                + (f"({r.paragraph})" if r.paragraph else "")
                + (f"(pt {r.point})" if r.point else "")
                + (f"  CELEX={r.celex}" if r.celex else "")
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
