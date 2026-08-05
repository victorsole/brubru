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


# Model refusals / clarifying questions that must never be written into a page.
#
# The previous detector matched only three literal substrings and missed the
# most common phrasing ("I need the actual HTML content to translate. You've
# only provided the opening `<body>` tag..."). Eighteen EU Canon language pages
# shipped to production with that sentence spliced mid-CSS, which left <style>
# unclosed and made the browser swallow the rest of the document, so each page
# served HTTP 200 and rendered blank. Repaired 21 July 2026.
REFUSAL_RE = re.compile(
    r"I need (the|to see|more)"
    r"|You'?ve only (provided|sent|given)"
    r"|Please (share|provide|send) the (full|actual|complete)"
    r"|fragment you('d| would)? (like|want)"
    r"|message was cut off"
    r"|I'?d be happy to (translate|help)"
    r"|Could you (please )?(share|provide|clarify|send)"
    r"|As an AI"
    r"|I'?m sorry, (but )?I can'?t",
    re.IGNORECASE,
)


def validate_document(html, source_html, lang):
    """Return a list of structural problems with an assembled translation.

    Per-chunk guards are not enough: chunks are validated in isolation but the
    file is written as their concatenation, so a head truncated mid-<style>
    only becomes visible once the pieces are joined. Nothing reaches disk
    without passing this.
    """
    problems = []
    for tag in ("</style>", "</head>", "</body>", "</html>"):
        if source_html.count(tag) and not html.count(tag):
            problems.append(f"missing {tag}")
    if html.count("<body") != source_html.count("<body"):
        problems.append(
            f"<body count {html.count('<body')} != source {source_html.count('<body')}"
        )
    if REFUSAL_RE.search(html):
        problems.append("model refusal text present in output")
    if len(html) < len(source_html) * 0.6:
        problems.append(f"suspiciously short: {len(html)} vs source {len(source_html)}")
    if f'<html lang="{lang}"' not in html:
        problems.append(f'missing <html lang="{lang}">')
    return problems


def _translatable_chars(text):
    """Count letters outside HTML tags/comments, to decide if a chunk is worth sending."""
    stripped = re.sub(r'<[^>]+>', ' ', text)
    stripped = re.sub(r'<!--.*?-->', ' ', stripped, flags=re.S)
    return sum(c.isalpha() for c in stripped)


def translate_chunk(text, lang):
    if not text.strip():
        return text
    # Structural chunks with almost no human text (e.g. "<body>" + a comment) make the model
    # refuse ("your message was cut off"). Keep them verbatim; there is nothing to translate.
    if _translatable_chars(text) < 25:
        return text
    cfg = LANGS[lang]
    sysmsg = SYSTEM.format(name=cfg["name"], note=cfg["note"])
    # max_tokens must comfortably exceed the chunk size; verbose languages (FR) expand ~20%
    # and a head chunk near the old 8000 cap was silently truncated mid-CSS. Scale generously.
    out_cap = max(8000, min(32000, int(len(text) / 2) + 4000))
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=out_cap,
                system=sysmsg,
                messages=[{"role": "user", "content": text}],
            )
            out = resp.content[0].text
            # Guard against truncation and refusals: output must look like HTML and not be a
            # refusal sentence. If it fails, fall back to the original chunk (English structure
            # preserved) rather than corrupting the file.
            looks_html = ("<" in out) if ("<" in text) else True
            truncated = getattr(resp, "stop_reason", None) == "max_tokens"
            refusal = bool(REFUSAL_RE.search(out))
            if truncated and attempt < 3:
                out_cap = min(32000, out_cap + 8000)
                print(f"    [chunk truncated, raising cap to {out_cap}, retry]")
                continue
            if refusal or not looks_html:
                print("    [refusal/non-HTML output -> keeping original chunk]")
                return text
            return out
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"    [retry {attempt+1}] {e} -> sleep {wait}s")
            time.sleep(wait)
    print(f"    [translation failed for a chunk in {lang} -> keeping original]")
    return text


def split_blocks(html):
    """Split into (head_and_doctype, [body blocks])."""
    body_idx = html.index("<body>")
    head = html[:body_idx]                      # <!DOCTYPE> + <html ...> + <head>...</head>\n
    body = html[body_idx:]                       # <body> ... </html>
    # Split body at column-0 top-level block starts.
    markers = re.compile(r'(?=^<header|^<section|^<div class="cta-strip"|^<footer|^<a href="#top")', re.M)
    parts = markers.split(body)
    return head, parts


def patch_head(head, lang, slug):
    cfg = LANGS[lang]
    head = head.replace('<html lang="en">', f'<html lang="{lang}">', 1)
    head = head.replace('content="en_GB"', f'content="{cfg["locale"]}"', 1)
    # canonical + og:url: index.html -> {lang}.html (only the two self-referential ones,
    # NOT the hreflang alternates which must keep listing every language). Slug derived
    # from the source path so this works for any canon entry.
    base = f"https://brubru.beresol.eu/eucanon/{slug}"
    head = head.replace(
        f'property="og:url" content="{base}/index.html"',
        f'property="og:url" content="{base}/{lang}.html"')
    head = head.replace(
        f'rel="canonical" href="{base}/index.html"',
        f'rel="canonical" href="{base}/{lang}.html"')
    return head


def patch_selector(text, lang):
    # move `selected` from index.html option to {lang}.html option
    text = text.replace('<option value="index.html" selected>', '<option value="index.html">')
    text = text.replace(f'<option value="{lang}.html">', f'<option value="{lang}.html" selected>')
    return text


def main():
    src_path = Path(sys.argv[1])
    langs = sys.argv[2:] if len(sys.argv) > 2 else list(LANGS.keys())
    slug = src_path.parent.name  # eucanon/<slug>/index.html
    html = src_path.read_text(encoding="utf-8")
    head, blocks = split_blocks(html)
    print(f"source: {src_path}  | slug {slug} | head {len(head)} chars | {len(blocks)} body blocks")

    for lang in langs:
        print(f"\n=== {lang} ===")
        out_head = translate_chunk(head, lang)
        out_head = patch_head(out_head, lang, slug)
        out_parts = []
        for i, b in enumerate(blocks):
            print(f"  block {i+1}/{len(blocks)} ({len(b)} chars)")
            out_parts.append(translate_chunk(b, lang))
        out = out_head + "".join(out_parts)
        out = patch_selector(out, lang)
        dest = src_path.parent / f"{lang}.html"

        problems = validate_document(out, html, lang)
        if problems:
            # Refuse to write. A broken page is worse than a missing one: it
            # serves HTTP 200, renders blank, and nothing alerts on it.
            print(f"  [ERROR] NOT written -- {dest} failed validation:")
            for p in problems:
                print(f"          - {p}")
            print("          Re-run this language; the source file is untouched.")
            continue

        dest.write_text(out, encoding="utf-8")
        print(f"  [OK] wrote {dest} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
