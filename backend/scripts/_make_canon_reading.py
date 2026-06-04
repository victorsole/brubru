"""Generic reading-copy generator for a single Formex act file.

Usage: python _make_canon_reading.py <path/to/act.xml> <output.reading.txt>

Strips markup, preserves recital numbers, article numbers and titles, paragraph
numbering and tables (rendered row by row), then wraps long lines so the Read tool
can ingest the text (raw Formex flattens articles into >25k-token mega-lines).
"""
import re
import sys
import html
import textwrap
from xml.etree import ElementTree as ET

WRAP = textwrap.TextWrapper(width=110, break_long_words=False, break_on_hyphens=False)


def text_of(el):
    s = ET.tostring(el, encoding="unicode", method="xml")
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def emit(out, text, indent=""):
    if not text:
        return
    for chunk in re.split(r"(?<=[.;:])\s+(?=\([a-z0-9ivx]+\)|\d+\.)", text):
        for line in WRAP.wrap(chunk):
            out.append(indent + line)


def render_tables(root, out):
    for tbl in root.iter("TBL"):
        out.append("\n[TABLE]")
        for row in tbl.iter("ROW"):
            cells = [text_of(c) for c in row.findall("CELL")]
            line = " | ".join(c for c in cells if c)
            if line:
                for w in WRAP.wrap(line):
                    out.append("  " + w)
        out.append("[/TABLE]")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    root = ET.parse(src).getroot()
    out = [f"READING COPY: {src}", "=" * 70]

    # structure skeleton
    titles = [text_of(t) for t in root.iter("TITLE")]
    if titles:
        out.append("STRUCTURE / TITLES (first lines):")
        for t in titles[:12]:
            if t:
                out.append("  " + t[:140])

    # recitals
    out.append("\n" + "=" * 70 + "\nPREAMBLE / RECITALS\n" + "=" * 70)
    for consid in root.iter("CONSID"):
        for np in consid.iter("NP"):
            nop = np.find("NO.P")
            num = text_of(nop) if nop is not None else ""
            full = text_of(np)
            if num and full.startswith(num):
                full = full[len(num):].strip()
            out.append("")
            emit(out, f"Recital {num} {full}" if num else full)
        if not list(consid.iter("NP")):
            emit(out, text_of(consid))

    # articles
    out.append("\n" + "=" * 70 + "\nENACTING TERMS / ARTICLES\n" + "=" * 70)
    seen = set()
    for art in root.iter("ARTICLE"):
        ti = art.find("TI.ART"); sti = art.find("STI.ART")
        ti_t = text_of(ti) if ti is not None else ""
        if ti_t in seen:
            continue
        seen.add(ti_t)
        sti_t = text_of(sti) if sti is not None else ""
        out.append("\n" + "-" * 60)
        out.append((ti_t + (" - " + sti_t if sti_t else "")).strip())
        out.append("-" * 60)
        for par in art.iter("PARAG"):
            nop = par.find("NO.PARAG")
            num = text_of(nop) if nop is not None else ""
            full = text_of(par)
            if num and full.startswith(num):
                full = full[len(num):].strip()
            out.append("")
            emit(out, (f"{num} " if num else "") + full)
        if not list(art.iter("PARAG")):
            full = text_of(art)
            for t in (ti_t, sti_t):
                if t and full.startswith(t):
                    full = full[len(t):].strip()
            emit(out, full)

    render_tables(root, out)

    open(dst, "w", encoding="utf-8").write("\n".join(out))
    txt = open(dst, encoding="utf-8").read()
    print(f"[OK] wrote {dst} ({len(txt)} bytes, {txt.count(chr(10))} lines)")
    print("  recitals:", len(re.findall(r'^Recital \(\d+\)', txt, re.M)))
    print("  article headers:", len(re.findall(r'^Article \d+', txt, re.M)))
    print("  tables:", txt.count("[TABLE]"))


if __name__ == "__main__":
    main()
