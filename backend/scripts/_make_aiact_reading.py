"""Generate a clean, line-wrapped reading copy of the AI Act (Reg 2024/1689) from
its 16 Formex files. Strips markup, preserves recital numbers, article numbers and
titles, paragraph numbering and the 13 annexes, then wraps long lines so the Read
tool can ingest it (raw Formex flattens articles into >25k-token mega-lines).

Output: data/canon/2024-1689_aiact.reading.txt
"""
import re
import html
import textwrap
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).parent.parent.parent
DIR = ROOT / "docs/LEG_2025-11/dc8116a1-3fe6-11ef-865a-01aa75ed71a1/fmx4"
MAIN = DIR / "L_202401689EN.000101.fmx.xml"
ANNEX_FILES = [
    "L_202401689EN.012401.fmx.xml", "L_202401689EN.012601.fmx.xml",
    "L_202401689EN.012701.fmx.xml", "L_202401689EN.013001.fmx.xml",
    "L_202401689EN.013201.fmx.xml", "L_202401689EN.013301.fmx.xml",
    "L_202401689EN.013401.fmx.xml", "L_202401689EN.013601.fmx.xml",
    "L_202401689EN.013801.fmx.xml", "L_202401689EN.013901.fmx.xml",
    "L_202401689EN.014101.fmx.xml", "L_202401689EN.014301.fmx.xml",
    "L_202401689EN.014401.fmx.xml",
]
OUT = ROOT / "data/canon/2024-1689_aiact.reading.txt"

WRAP = textwrap.TextWrapper(width=110, break_long_words=False, break_on_hyphens=False)


def text_of(el):
    """All text within an element, tags stripped, whitespace collapsed."""
    s = ET.tostring(el, encoding="unicode", method="xml")
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def emit(out, text, indent=""):
    if not text:
        return
    # split into sentences / numbered sub-points for readability
    for chunk in re.split(r"(?<=[.;:])\s+(?=\([a-z0-9ivx]+\)|\d+\.)", text):
        for line in WRAP.wrap(chunk):
            out.append(indent + line)


def walk_recitals(root, out):
    out.append("\n" + "=" * 70)
    out.append("PREAMBLE / RECITALS")
    out.append("=" * 70)
    # recitals: <CONSID> with <NP><NO.P>(1)</NO.P>...
    for consid in root.iter("CONSID"):
        for np in consid.iter("NP"):
            nop = np.find("NO.P")
            num = text_of(nop) if nop is not None else ""
            # text excluding the number element
            full = text_of(np)
            if num and full.startswith(num):
                full = full[len(num):].strip()
            out.append("")
            emit(out, f"Recital {num} {full}")
        if not list(consid.iter("NP")):
            emit(out, text_of(consid))


def walk_articles(root, out):
    out.append("\n" + "=" * 70)
    out.append("ENACTING TERMS / ARTICLES")
    out.append("=" * 70)
    seen = set()
    for art in root.iter("ARTICLE"):
        ti = art.find("TI.ART")
        sti = art.find("STI.ART")
        ti_t = text_of(ti) if ti is not None else ""
        if ti_t in seen:
            continue
        seen.add(ti_t)
        sti_t = text_of(sti) if sti is not None else ""
        out.append("\n" + "-" * 60)
        out.append((ti_t + (" - " + sti_t if sti_t else "")).strip())
        out.append("-" * 60)
        # paragraphs
        for par in art.iter("PARAG"):
            nop = par.find("NO.PARAG")
            num = text_of(nop) if nop is not None else ""
            full = text_of(par)
            if num and full.startswith(num):
                full = full[len(num):].strip()
            out.append("")
            emit(out, (f"{num} " if num else "") + full)
        if not list(art.iter("PARAG")):
            # article with alineas only
            emit(out, _article_body_excl_titles(art, ti_t, sti_t))


def _article_body_excl_titles(art, ti_t, sti_t):
    full = text_of(art)
    for t in (ti_t, sti_t):
        if t and full.startswith(t):
            full = full[len(t):].strip()
    return full


def walk_divisions(root, out):
    """Emit Title/Chapter/Section headers inline by reading the structure order."""
    # We do a flat pass for titles to give the reader the skeleton up front.
    out.append("\n" + "=" * 70)
    out.append("STRUCTURE (Titles / Chapters / Sections)")
    out.append("=" * 70)
    for div in root.iter("DIVISION"):
        ti = div.find("TITLE")
        if ti is None:
            continue
        label = text_of(ti)
        if label:
            out.append("  " + label[:140])


def annex(out, path):
    root = ET.parse(path).getroot()
    out.append("\n" + "=" * 70)
    # annex title
    titles = [text_of(t) for t in root.iter("TITLE")][:2]
    out.append("ANNEX: " + " | ".join(t for t in titles if t)[:160])
    out.append("=" * 70)
    body = text_of(root)
    emit(out, body)


def main():
    out = []
    root = ET.parse(MAIN).getroot()
    out.append("READING COPY: Regulation (EU) 2024/1689 (Artificial Intelligence Act)")
    out.append("Source Formex: L_202401689EN.000101 + 13 annex files (OJ L, 12.7.2024)")
    walk_divisions(root, out)
    walk_recitals(root, out)
    walk_articles(root, out)
    for af in ANNEX_FILES:
        annex(out, DIR / af)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] wrote {OUT} ({OUT.stat().st_size} bytes, {len(out)} lines)")
    # quick sanity counts
    txt = OUT.read_text(encoding="utf-8")
    print("  recitals matched:", len(re.findall(r'^Recital \(\d+\)', txt, re.M)))
    print("  article headers:", len(re.findall(r'^Article \d+', txt, re.M)))
    print("  annex headers:", txt.count("ANNEX:"))


if __name__ == "__main__":
    main()
