"""
Definition Extractor

Extracts "'term' means definition" entries from the Definitions article
(commonly Article 2, 3, or 4) of an EU legal act.

Re-implements the hover-definition pattern from Maastricht's LegalViz.EU
(GPLv3, not linked) in pure Python.

Use cases
---------
- Amendator: tooltip on any defined term across the entire law text.
- Catalan landing pages: render definitions as `<abbr title="..."/>`.
- Chatbot context builder: when a query uses a term that is defined in a
  cited law, surface the precise statutory definition.

Output
------
`dict[str, DefinitionEntry]` keyed by lowercase term. Each entry has:
- term: canonical casing as written in the law
- definition: the "means ..." text, trimmed and terminator-stripped
- article: the article key the term was defined in (e.g. "Article 3")
- point: the numbered point within that article (e.g. "5") if present

Design
------
- Robust to common quote styles: `' '`, `" "`, `‘ ’`, `“ ”`, `« »`
- Tolerates both "means" and (multilingual) "signifie"/"significa"/"betekent"
  so the same code can process non-English Formex acts. Expand as needed.
- Matches EU drafting style: `(N) 'term' means ...` and `'term' means ...`.
- Returns the point number when present so the frontend can link to
  Article 3(5) directly.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re

# "means" in the languages Brubru serves plus Latin-ish coverage for fallback.
# If we hit a language not here, the pattern still matches "means"/"signifie" etc.
# in the English version of the act (EUR-Lex ships all-EN versions too).
_MEANS = r"(?:means|signifie|significa|designa|betekent|bedeutet|vuol\s+dire|vol\s+dir|mitjan[cç]ant)"

# Character-class contents (no outer brackets -- inserted where needed)
_QOPEN_CHARS = r"\"'‘“«"
_QCLOSE_CHARS = r"\"'’”»"

# Full "(N) 'term' means text;" pattern. N is optional (some acts omit numbering).
_POINT_DEF_RE = re.compile(
    rf"(?:\((?P<point>[\da-z]{{1,4}})\)\s*)?"   # optional (N) or (a)
    rf"[{_QOPEN_CHARS}]"
    rf"(?P<term>[^{_QCLOSE_CHARS}\n]{{1,100}}?)"
    rf"[{_QCLOSE_CHARS}]"
    rf"\s*{_MEANS}\s+"
    rf"(?P<body>[^;]{{5,2000}}?);",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class DefinitionEntry:
    term: str
    definition: str
    article: str
    point: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DEFINITION_ARTICLE_KEYWORDS = ("definitions", "définitions", "definicions", "definiciones", "definizioni", "definities", "begriffsbestimmungen")


def _article_key(article: Any) -> str:
    number = getattr(article, "number", None)
    if number:
        return f"Article {number}" if not str(number).lower().startswith("article") else str(number)
    return (getattr(article, "title", None) or "Article ?")[:80]


def _article_text(article: Any) -> str:
    parts = []
    t = getattr(article, "title", None)
    if t:
        parts.append(str(t))
    for p in getattr(article, "paragraphs", None) or []:
        pt = getattr(p, "text", None)
        if pt:
            parts.append(str(pt))
        for s in getattr(p, "subparagraphs", None) or []:
            st = getattr(s, "text", None)
            if st:
                parts.append(str(st))
    flat = getattr(article, "text", None)
    if flat and not parts:
        parts.append(str(flat))
    # Definitions often live inside <LIST><ITEM> elements that FormexParser
    # does not extract into paragraphs. Fall back to stripping the raw Article
    # HTML (kept on the Article via `html` attribute) when the structured path
    # yielded little content.
    combined = "\n".join(parts).strip()
    raw_html = getattr(article, "html", None)
    if raw_html and len(combined) < 200:
        combined = _html_to_text(raw_html)
    return combined


def _html_to_text(html: str) -> str:
    """Turn Formex XML into something our regex can hit.

    Formex wraps quoted terms in <QUOT.START>term-text<QUOT.END>. We replace
    those with `'term-text'` so the definition regex matches the same way it
    would on Cellar XHTML or plain quoted text. Other tags are stripped.
    """
    s = re.sub(r"<QUOT\.START[^>]*>", "'", html, flags=re.IGNORECASE)
    s = re.sub(r"<QUOT\.END[^>]*>", "'", s, flags=re.IGNORECASE)
    # Replace closing tags of block items with a space so adjacent tokens don't
    # glue together when tags are stripped.
    s = re.sub(r"</(ITEM|P|LI|NP|TXT)>", " ", s, flags=re.IGNORECASE)
    # Strip everything else
    s = re.sub(r"<[^>]+>", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _is_definition_article(article: Any) -> bool:
    title = (getattr(article, "title", None) or "").lower()
    number = str(getattr(article, "number", "") or "").strip().lower()
    if number in ("2", "3", "4", "02", "03", "04", "002", "003", "004"):
        if any(kw in title for kw in _DEFINITION_ARTICLE_KEYWORDS):
            return True
        # Article numbered 2/3/4 but title empty: probe body for "means"
        body = _article_text(article).lower()
        if "means" in body or "signifie" in body or "significa" in body:
            return True
    # Title explicitly says Definitions regardless of number
    return any(kw in title for kw in _DEFINITION_ARTICLE_KEYWORDS)


def extract_definitions(parsed_law: Any) -> list[DefinitionEntry]:
    """
    Return all (term, definition) entries from any article whose title contains
    'definitions' (or localised equivalent), or from Articles 2/3/4 that carry
    'means' language.
    """
    out: list[DefinitionEntry] = []
    for article in getattr(parsed_law, "articles", []) or []:
        if not _is_definition_article(article):
            continue
        body = _article_text(article)
        akey = _article_key(article)
        for m in _POINT_DEF_RE.finditer(body):
            term = m.group("term").strip().strip(",")
            body_text = m.group("body").strip().rstrip(";,.")
            body_text = re.sub(r"\s+", " ", body_text)
            if not term or len(body_text) < 5:
                continue
            out.append(
                DefinitionEntry(
                    term=term,
                    definition=body_text,
                    article=akey,
                    point=(m.group("point") or None),
                )
            )
    return out


def extract_definitions_map(parsed_law: Any) -> dict[str, dict[str, Any]]:
    """JSON-serialisable term -> definition map keyed by lowercase term."""
    entries = extract_definitions(parsed_law)
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        key = e.term.lower()
        # If duplicated, keep the first occurrence (usually the canonical one)
        if key not in out:
            out[key] = e.to_dict()
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> int:
    import argparse
    import json
    import sys
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Extract Article 3/4 definitions")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--formex", type=Path)
    src.add_argument("--celex", type=str)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.formex:
        from .formex_parser import parse_formex_file
        parsed = parse_formex_file(args.formex)
    else:
        from .eurlex_parser import EurlexParser
        import httpx
        url = f"https://publications.europa.eu/resource/celex/{args.celex}"
        resp = httpx.get(
            url,
            headers={"Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"},
            follow_redirects=True,
            timeout=30,
        )
        if resp.status_code != 200 or not resp.text:
            print(f"[ERROR] could not fetch CELEX {args.celex} (status {resp.status_code})", file=sys.stderr)
            return 1
        parsed = EurlexParser(resp.text).parse()

    entries = extract_definitions(parsed)
    if args.json:
        print(json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False))
        return 0

    print(f"Definitions found: {len(entries)}")
    for e in entries:
        point = f"({e.point})" if e.point else ""
        print(f"  {e.article}{point}  '{e.term}': {e.definition[:100]}{'…' if len(e.definition) > 100 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
