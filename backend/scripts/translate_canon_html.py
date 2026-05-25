"""Translate an EU Canon deep-dive HTML page into the 5 sibling languages.

Why this exists (canon lesson, May 2026): Haiku sub-agents leave large HTML files
partly untranslated and mislabel domain terms; Sonnet sub-agents that try to Write a
~90KB file in one call hit the 32000 output-token cap and fail. The reliable path is
to chunk the raw HTML at top-level block boundaries (column-0 <header>/<section>/
<div class="cta-strip">/<footer>) and translate each chunk via the Anthropic SDK,
then reassemble byte-for-byte and apply deterministic per-language head patches.

Usage:
  /opt/anaconda3/bin/python3 backend/scripts/translate_canon_html.py \
      frontend/public/eucanon/<slug>/index.html [es fr it nl ca]

Output: es.html / fr.html / it.html / nl.html / ca.html as siblings of index.html.
"""
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import os
import anthropic

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

LANGS = {
    "es": {"locale": "es_ES", "name": "Spanish",
           "note": "Use the official EUR-Lex Spanish terminology. 'Reglamento de Ejecucion (UE)', 'derechos compensatorios' (countervailing duties), 'subvenciones' (subsidies). Preserve all accents (a e i o u, n)."},
    "fr": {"locale": "fr_FR", "name": "French",
           "note": "Use the official EUR-Lex French terminology. 'reglement d'execution (UE)', 'droits compensateurs' (countervailing duties), 'subventions'. Preserve all accents."},
    "it": {"locale": "it_IT", "name": "Italian",
           "note": "Use the official EUR-Lex Italian terminology. 'regolamento di esecuzione (UE)', 'dazi compensativi' (countervailing duties), 'sovvenzioni'. Preserve all accents."},
    "nl": {"locale": "nl_NL", "name": "Dutch",
           "note": "Use the official EUR-Lex Dutch terminology. 'uitvoeringsverordening (EU)', 'compenserende rechten' (countervailing duties), 'subsidies'."},
    "ca": {"locale": "ca_ES", "name": "Catalan",
           "note": "Use Brubru's Catalan legal glossary. 'Reglament d'execucio (UE)', 'drets compensatoris' (countervailing duties), 'subvencions', 'Brussel.les' with the middle dot (l flsmiddot l), accents on capitals (Victor Sole). Catalan is not an official EU language so there is no EUR-Lex reference; translate idiomatically and formally."},
}

SYSTEM = (
    "You are a professional EU legal-policy translator. You translate HTML fragments from "
    "British English into {name}. ABSOLUTE RULES:\n"
    "1. Translate ONLY human-readable text (the words a reader sees): visible page text, the "
    "<title>, meta description / og / twitter 'content' attribute text, aria-label values, "
    "alt text, button labels, and JSON-LD 'name'/'description'/'headline' string VALUES.\n"
    "2. Do NOT change any HTML tag, attribute name, CSS class, id, inline style, URL, asset path "
    "(../../...), href, src, hreflang code, JSON-LD key, or schema.org type. Keep them byte-identical.\n"
    "3. Do NOT translate: proper nouns (Brubru, Beresol, EUROFER, Jindal, Chromeni, IRNC, Tsingshan, "
    "Morowali, IMIP, EUR-Lex, von der Leyen, TARIC, CN, CELEX), regulation numbers, company names, "
    "country names that are proper nouns, numbers, percentages, dates, recital references, TARIC codes.\n"
    "4. NEVER use em-dashes or en-dashes in the output. Use commas, colons, or the word for 'to' in "
    "ranges. {note}\n"
    "5. Output ONLY the translated HTML fragment. No preface, no code fences, no commentary. The "
    "fragment must have exactly the same tag structure as the input."
)


def translate_chunk(text, lang):
    if not text.strip():
        return text
    cfg = LANGS[lang]
    sysmsg = SYSTEM.format(name=cfg["name"], note=cfg["note"])
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=8000,
                system=sysmsg,
                messages=[{"role": "user", "content": text}],
            )
            return resp.content[0].text
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"    [retry {attempt+1}] {e} -> sleep {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"translation failed for a chunk in {lang}")


def split_blocks(html):
    """Split into (head_and_doctype, [body blocks])."""
    body_idx = html.index("<body>")
    head = html[:body_idx]                      # <!DOCTYPE> + <html ...> + <head>...</head>\n
    body = html[body_idx:]                       # <body> ... </html>
    # Split body at column-0 top-level block starts.
    markers = re.compile(r'(?=^<header|^<section|^<div class="cta-strip"|^<footer|^<a href="#top")', re.M)
    parts = markers.split(body)
    return head, parts


def patch_head(head, lang):
    cfg = LANGS[lang]
    head = head.replace('<html lang="en">', f'<html lang="{lang}">', 1)
    head = head.replace('content="en_GB"', f'content="{cfg["locale"]}"', 1)
    # canonical + og:url: index.html -> {lang}.html (only the two self-referential ones,
    # NOT the hreflang alternates which must keep listing every language).
    head = head.replace(
        'property="og:url" content="https://brubru.beresol.eu/eucanon/2022-433_india_indonesia_stainless_steel/index.html"',
        f'property="og:url" content="https://brubru.beresol.eu/eucanon/2022-433_india_indonesia_stainless_steel/{lang}.html"')
    head = head.replace(
        'rel="canonical" href="https://brubru.beresol.eu/eucanon/2022-433_india_indonesia_stainless_steel/index.html"',
        f'rel="canonical" href="https://brubru.beresol.eu/eucanon/2022-433_india_indonesia_stainless_steel/{lang}.html"')
    return head


def patch_selector(text, lang):
    # move `selected` from index.html option to {lang}.html option
    text = text.replace('<option value="index.html" selected>', '<option value="index.html">')
    text = text.replace(f'<option value="{lang}.html">', f'<option value="{lang}.html" selected>')
    return text


def main():
    src_path = Path(sys.argv[1])
    langs = sys.argv[2:] if len(sys.argv) > 2 else list(LANGS.keys())
    html = src_path.read_text(encoding="utf-8")
    head, blocks = split_blocks(html)
    print(f"source: {src_path}  | head {len(head)} chars | {len(blocks)} body blocks")

    for lang in langs:
        print(f"\n=== {lang} ===")
        out_head = translate_chunk(head, lang)
        out_head = patch_head(out_head, lang)
        out_parts = []
        for i, b in enumerate(blocks):
            print(f"  block {i+1}/{len(blocks)} ({len(b)} chars)")
            out_parts.append(translate_chunk(b, lang))
        out = out_head + "".join(out_parts)
        out = patch_selector(out, lang)
        dest = src_path.parent / f"{lang}.html"
        dest.write_text(out, encoding="utf-8")
        print(f"  wrote {dest} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
