"""Generic HTML / OJ-XML -> clean reading copy for the EU Canon pipeline.

Cellar serves EU acts as either EUR-Lex HTML (Accept: text/html) or the
original OJ document XML (Accept: application/xhtml+xml). Both flatten badly
when read raw. This converter strips markup, decodes entities, and re-inserts
line breaks before structural markers (recitals, Article N, Chapter, Annex,
numbered points) so the law can be read top to bottom in the Read tool.

Usage:
    python3.12 backend/scripts/_make_html_reading.py <src.html> <out.reading.txt>
"""
import re
import sys
import html
import textwrap


def to_reading(src_path: str, out_path: str) -> None:
    raw = open(src_path, encoding="utf-8", errors="replace").read()

    # Drop script/style blocks entirely.
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)

    # Treat block-level closings as paragraph breaks before stripping tags.
    raw = re.sub(r"</(p|div|tr|li|h[1-6]|table|td|th|br)\s*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)

    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)

    # Normalise whitespace per line.
    lines = []
    for ln in text.split("\n"):
        ln = re.sub(r"[ \t ]+", " ", ln).strip()
        if ln:
            lines.append(ln)
    text = "\n".join(lines)

    # Force a blank line before key structural markers so the spine is visible.
    markers = [
        r"Article\s+\d+[a-z]?",
        r"CHAPTER\s+[IVXLCDM0-9]+",
        r"Chapter\s+[IVXLCDM0-9]+",
        r"TITLE\s+[IVXLCDM0-9]+",
        r"SECTION\s+\d+",
        r"ANNEX\s+[IVXLCDM0-9]*",
        r"Annex\s+[IVXLCDM0-9]*",
    ]
    for m in markers:
        text = re.sub(r"(?<!\n)\n?(" + m + r")\b", r"\n\n\1", text)

    # Recital markers like "(1)" / "(12)" at line start get their own line.
    text = re.sub(r"\n(\(\d{1,3}\)\s)", r"\n\n\1", text)

    # Wrap long lines for readability.
    wrapped = []
    for para in text.split("\n"):
        if len(para) <= 110:
            wrapped.append(para)
        else:
            wrapped.extend(textwrap.wrap(para, width=110, break_long_words=False,
                                         break_on_hyphens=False))
    out = "\n".join(wrapped)
    out = re.sub(r"\n{3,}", "\n\n", out)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(out)

    n_art = len(re.findall(r"\n\nArticle\s+\d+", out))
    n_rec = len(re.findall(r"\n\n\(\d{1,3}\)\s", out))
    print(f"[OK] {out_path}: {len(out):,} chars | ~{n_art} article markers | ~{n_rec} recital markers")


if __name__ == "__main__":
    to_reading(sys.argv[1], sys.argv[2])
