"""
Recital-Article Linker

Inspired by the Maastricht LegalViz.EU project (GPLv3, not linked in Brubru).
Re-implements the TF-IDF cosine-similarity approach in Python to associate each
Article of an EU legal act with the Recitals that most plausibly explain its
intent.

Use cases
---------
- Amendator sidebar: when a user drafts an amendment to Article 12, surface the
  2-3 recitals that motivate it so the amendment's "Justification" can cite
  them.
- Catalan landing pages (`data/legislacio-ue-catala/[celex]/index.html`): render
  small "See recital N, M" links next to each article.
- Chatbot context builder: when answering "what is the intent of Article X of
  Regulation Y?", inject the linked recitals.

Input
-----
Accepts either:
- `ParsedEurlexDocument` from `eurlex_parser.py` (Cellar XHTML path)
- `ParsedLaw` from `formex_parser.py` (Formex V4 XML path)

Both expose `articles: list` and `recitals: list` with `.text` and `.number`.

Output
------
`dict[str, list[RecitalLink]]` keyed by article key (the article's identifier,
e.g. "Article 3" or "3" or whatever `_article_key()` returns for the input).
Each `RecitalLink` has:
- recital_number: str
- score: float in [0, 1]
- snippet: first ~160 chars of the recital text

Design notes
------------
- TF-IDF is intentionally simple and language-agnostic enough for English text.
  For Catalan/Spanish/French acts we use the same vectorizer because EU legal
  vocabulary overlaps heavily across languages and TF-IDF does not know
  grammar; it matters that term weighting is consistent within the act.
- Stop-words: English stoplist dropped because many Formex/Cellar acts are
  non-English. Instead we rely on `min_df=1, max_df=0.9` to drop act-wide
  noise words.
- Runs in milliseconds even for 100+ recitals x 50+ articles (matrix multiply).
- No external dependency beyond scikit-learn which is already a dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class RecitalLink:
    recital_number: str
    score: float
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _article_key(article: Any) -> str:
    """Return a stable key for an Article, tolerating both parser shapes."""
    # EurlexParser.Article and FormexParser.Article both expose .number
    number = getattr(article, "number", None)
    if number:
        return f"Article {number}" if not str(number).lower().startswith("article") else str(number)
    title = getattr(article, "title", None) or ""
    return title[:80] or "Article ?"


def _article_text(article: Any) -> str:
    """Concatenate title + all paragraph text for an Article."""
    parts: list[str] = []
    title = getattr(article, "title", None)
    if title:
        parts.append(str(title))
    # FormexParser.Article.paragraphs = list[Paragraph(text=...)]
    # EurlexParser.Article.paragraphs = list[Paragraph(text=..., subparagraphs=...)]
    paragraphs = getattr(article, "paragraphs", None) or []
    for p in paragraphs:
        p_text = getattr(p, "text", None)
        if p_text:
            parts.append(str(p_text))
        subs = getattr(p, "subparagraphs", None) or []
        for s in subs:
            s_text = getattr(s, "text", None)
            if s_text:
                parts.append(str(s_text))
    # Some EurlexParser shapes also carry a flat .text
    flat = getattr(article, "text", None)
    if flat and not parts:
        parts.append(str(flat))
    return "\n".join(parts).strip()


def _recital_text(recital: Any) -> str:
    return str(getattr(recital, "text", "") or "").strip()


def _snippet(text: str, max_chars: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def link_recitals_to_articles(
    parsed_law: Any,
    top_n: int = 3,
    min_score: float = 0.05,
) -> dict[str, list[RecitalLink]]:
    """
    Compute the top-N most relevant recitals for each article.

    Parameters
    ----------
    parsed_law : ParsedEurlexDocument | ParsedLaw | any object with `articles` and `recitals`
    top_n : keep up to this many recital links per article (default 3)
    min_score : drop links below this cosine score (default 0.05)

    Returns
    -------
    dict keyed by article key, each value a list of RecitalLink ordered by score desc.
    Articles with no matching recitals get an empty list.
    """
    articles = list(getattr(parsed_law, "articles", []) or [])
    recitals = list(getattr(parsed_law, "recitals", []) or [])
    if not articles or not recitals:
        return {_article_key(a): [] for a in articles}

    article_texts = [_article_text(a) for a in articles]
    recital_texts = [_recital_text(r) for r in recitals]

    corpus = article_texts + recital_texts
    vec = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
        sublinear_tf=True,
    )
    matrix = vec.fit_transform(corpus)
    art_matrix = matrix[: len(articles)]
    rec_matrix = matrix[len(articles) :]

    sim = cosine_similarity(art_matrix, rec_matrix)  # shape (n_art, n_rec)

    out: dict[str, list[RecitalLink]] = {}
    for i, article in enumerate(articles):
        ranked = sorted(enumerate(sim[i]), key=lambda x: -x[1])
        links: list[RecitalLink] = []
        for j, score in ranked[: top_n * 2]:  # oversample then filter
            if float(score) < min_score:
                break
            rec = recitals[j]
            links.append(
                RecitalLink(
                    recital_number=str(getattr(rec, "number", j + 1)),
                    score=round(float(score), 4),
                    snippet=_snippet(_recital_text(rec)),
                )
            )
            if len(links) >= top_n:
                break
        out[_article_key(article)] = links
    return out


def link_recitals_to_articles_json(parsed_law: Any, top_n: int = 3) -> dict[str, list[dict[str, Any]]]:
    """JSON-serialisable variant: returns plain dicts for storage in `eu_laws.extra_metadata.recital_article_map`."""
    links = link_recitals_to_articles(parsed_law, top_n=top_n)
    return {k: [link.to_dict() for link in v] for k, v in links.items()}


# ---------------------------------------------------------------------------
# CLI for quick manual testing against a Formex XML file or a CELEX via Cellar.
# Example:
#   python3.12 -m services.parsers.recital_article_linker --formex docs/LEG_2025-11/.../file.xml
#   python3.12 -m services.parsers.recital_article_linker --celex 32016R0679
# ---------------------------------------------------------------------------
def _main() -> int:
    import argparse
    import json
    import sys
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Link recitals to articles (TF-IDF cosine)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--formex", type=Path, help="Path to a Formex V4 XML file")
    src.add_argument("--celex", type=str, help="CELEX number to fetch from Cellar (e.g. 32016R0679)")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", action="store_true", help="Print JSON instead of table")
    args = ap.parse_args()

    if args.formex:
        from .formex_parser import parse_formex_file

        parsed = parse_formex_file(args.formex)
    else:
        from .eurlex_fetcher import fetch_eurlex_document
        from .eurlex_parser import EurlexParser

        html = fetch_eurlex_document(args.celex)
        if not html:
            print(f"[ERROR] could not fetch CELEX {args.celex}", file=sys.stderr)
            return 1
        parsed = EurlexParser(html).parse()

    links = link_recitals_to_articles(parsed, top_n=args.top)

    if args.json:
        print(json.dumps({k: [l.to_dict() for l in v] for k, v in links.items()}, indent=2))
        return 0

    # Table output
    art_count = len(links)
    linked = sum(1 for v in links.values() if v)
    total_links = sum(len(v) for v in links.values())
    print(f"Articles: {art_count}, with recital links: {linked}, total links: {total_links}")
    print()
    for art, recs in links.items():
        if not recs:
            continue
        print(f"  {art}")
        for r in recs:
            print(f"      recital {r.recital_number:>3}  score={r.score:.3f}  {r.snippet[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
