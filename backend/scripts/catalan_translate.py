#!/usr/bin/env python3.12
"""
Catalan EU Legislation Translation Pipeline

Primary engine: Softcatala NMT (CTranslate2, local, free)
Fallback: Claude Sonnet (API, paid, higher quality)

Usage:
    # Parse and show structure
    python3.12 scripts/catalan_translate.py --parse path/to/file.xml

    # Translate to Catalan (Softcatala, default)
    python3.12 scripts/catalan_translate.py --translate path/to/file.xml

    # Translate with Claude Sonnet instead
    python3.12 scripts/catalan_translate.py --translate path/to/file.xml --engine sonnet

    # Find a regulation by OJ reference
    python3.12 scripts/catalan_translate.py --find "L_2016119"
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# Step 1: Formex V4 XML Parser
# ============================================================

def extract_text(element) -> str:
    """Extract all text content from an XML element, preserving inline structure."""
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        # Skip footnotes for now (they'll be handled separately)
        if child.tag == 'NOTE':
            # Keep footnote reference marker
            note_id = child.get('NOTE.ID', '')
            parts.append(f' [{note_id}]')
        elif child.tag == 'REF.DOC.OJ':
            # Preserve OJ references as-is
            parts.append(ET.tostring(child, encoding='unicode', method='text').strip())
        elif child.tag == 'HT':
            # Preserve formatting hints
            ht_type = child.get('TYPE', '')
            text = extract_text(child)
            if ht_type == 'UC':
                parts.append(text.upper() if len(text) < 50 else text)
            elif ht_type == 'ITALIC':
                parts.append(text)
            else:
                parts.append(text)
        elif child.tag == 'DATE':
            parts.append(extract_text(child))
        elif child.tag in ('QUOT.START', 'QUOT.END'):
            parts.append('"')
        elif child.tag == 'NP':
            # Numbered paragraph within a recital or article
            no_p = child.find('NO.P')
            txt = child.find('TXT')
            num = extract_text(no_p) if no_p is not None else ''
            text = extract_text(txt) if txt is not None else extract_text(child)
            parts.append(f'{num} {text}'.strip())
        else:
            parts.append(extract_text(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts).strip()


def parse_formex(xml_path: str) -> dict:
    """
    Parse a Formex V4 XML file and extract structured segments.

    Returns a dict with:
    - metadata: CELEX, date, OJ ref, document number
    - title: full title text
    - preamble_init: opening ("THE EUROPEAN PARLIAMENT AND THE COUNCIL...")
    - visas: list of "having regard to" clauses
    - recitals_init: "Whereas:" or similar
    - recitals: list of numbered recitals
    - preamble_final: "HAVE ADOPTED THIS REGULATION:" etc
    - articles: list of {number, title, paragraphs: [text]}
    - final: signature block
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    result = {
        'source_file': xml_path,
        'metadata': {},
        'title': '',
        'preamble_init': '',
        'visas': [],
        'recitals_init': '',
        'recitals': [],
        'preamble_final': '',
        'chapters': [],
        'articles': [],
        'final': '',
    }

    # Metadata from BIB.INSTANCE
    bib = root.find('.//BIB.INSTANCE')
    if bib is not None:
        doc_ref = bib.find('.//DOCUMENT.REF')
        if doc_ref is not None:
            coll = doc_ref.findtext('COLL', '')
            no_oj = doc_ref.findtext('NO.OJ', '')
            year = doc_ref.findtext('YEAR', '')
            result['metadata']['oj_ref'] = f'{coll} {no_oj}/{year}'

        no_doc = bib.find('.//NO.DOC')
        if no_doc is not None:
            no_current = no_doc.findtext('NO.CURRENT', '')
            doc_year = no_doc.findtext('YEAR', '')
            com = no_doc.findtext('COM', '')
            result['metadata']['doc_number'] = f'{no_current}/{doc_year}'
            result['metadata']['doc_type_suffix'] = com

        date_el = bib.find('DATE')
        if date_el is not None:
            result['metadata']['date'] = date_el.get('ISO', '')

        result['metadata']['language'] = bib.findtext('LG.DOC', 'EN')

    # Title
    title_el = root.find('.//TITLE')
    if title_el is not None:
        title_parts = []
        for p in title_el.iter('P'):
            text = extract_text(p)
            if text:
                title_parts.append(text)
        result['title'] = ' '.join(title_parts)

    # Preamble
    preamble = root.find('.//PREAMBLE')
    if preamble is not None:
        # Init
        init = preamble.find('PREAMBLE.INIT')
        if init is not None:
            result['preamble_init'] = extract_text(init)

        # Visas
        for visa in preamble.iter('VISA'):
            text = extract_text(visa)
            if text:
                result['visas'].append(text)

        # Recitals
        consid_init = preamble.find('.//GR.CONSID.INIT')
        if consid_init is not None:
            result['recitals_init'] = extract_text(consid_init)

        for consid in preamble.iter('CONSID'):
            text = extract_text(consid)
            if text:
                result['recitals'].append(text)

        # Final
        final = preamble.find('PREAMBLE.FINAL')
        if final is not None:
            result['preamble_final'] = extract_text(final)

    # Chapters (if any)
    for chapter in root.iter('CHAPTER'):
        ch_title = chapter.find('TITLE')
        if ch_title is not None:
            result['chapters'].append(extract_text(ch_title))

    # Articles
    for article in root.iter('ARTICLE'):
        art_data = {
            'identifier': article.get('IDENTIFIER', ''),
            'title': '',
            'paragraphs': [],
        }

        ti_art = article.find('TI.ART')
        if ti_art is not None:
            art_data['title'] = extract_text(ti_art)

        # Get article content: ALINEA, PARAG, or direct NP
        for alinea in article.iter('ALINEA'):
            text = extract_text(alinea)
            if text:
                art_data['paragraphs'].append(text)

        for parag in article.findall('PARAG'):
            no_parag = parag.find('NO.PARAG')
            alinea = parag.find('ALINEA')
            num = extract_text(no_parag) if no_parag is not None else ''
            text = extract_text(alinea) if alinea is not None else extract_text(parag)
            if text:
                art_data['paragraphs'].append(f'{num} {text}'.strip())

        # If no ALINEA or PARAG found, get direct text
        if not art_data['paragraphs']:
            for np_el in article.findall('NP'):
                text = extract_text(np_el)
                if text:
                    art_data['paragraphs'].append(text)

        if art_data['title'] or art_data['paragraphs']:
            result['articles'].append(art_data)

    # Final/Signature
    final_el = root.find('.//FINAL')
    if final_el is not None:
        result['final'] = extract_text(final_el)

    return result


def _parse_consolidated_html(soup, html_path: str, celex: str = '') -> dict:
    """
    Parse consolidated EUR-Lex HTML format (e.g. from 'Consolidated TEXT' pages).
    These use classes: title-doc-first, title-article-norm, stitle-article-norm,
    norm, eli-subdivision, eli-title, etc. Consolidated texts typically have no
    preamble (no visas or recitals).
    """
    result = {
        'source_file': html_path,
        'metadata': {'celex': celex, 'language': 'EN'},
        'title': '',
        'preamble_init': '',
        'visas': [],
        'recitals_init': '',
        'recitals': [],
        'preamble_final': '',
        'chapters': [],
        'articles': [],
        'final': '',
    }

    # Title: <p class="title-doc-first"> elements
    title_els = soup.select('p.title-doc-first')
    if title_els:
        result['title'] = ' '.join(el.get_text(strip=True) for el in title_els)

    # Articles: <div class="eli-subdivision" id="art_N">
    art_divs = soup.select('div.eli-subdivision[id^="art_"]')
    for art_div in art_divs:
        # Article number from title
        art_title_el = art_div.select_one('p.title-article-norm')
        art_text = art_title_el.get_text(strip=True) if art_title_el else ''
        art_num_match = re.search(r'Article\s+(\d+[a-z]?)', art_text)
        art_num = art_num_match.group(1) if art_num_match else art_text

        # Subtitle (e.g. "Aim and scope")
        subtitle_el = art_div.select_one('div.eli-title, p.stitle-article-norm')
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ''
        full_title = f'{art_text} - {subtitle}' if subtitle else art_text

        art_data = {
            'identifier': f'ART_{art_num}',
            'title': full_title,
            'paragraphs': [],
        }

        # Paragraphs: <div class="norm"> elements inside the article
        norm_divs = art_div.select('div.norm')
        raw_texts = []
        for norm in norm_divs:
            # Clean amendment markers (consolidated text artefacts)
            text = norm.get_text(strip=True)
            # Remove consolidation markers like ►M3 ◄ ►C1 ◄ ▼B ▼M3 etc.
            text = re.sub(r'[►▼][A-Z]\d*\s*', '', text)
            text = re.sub(r'◄\s*', '', text)
            if text:
                raw_texts.append(text)

        # Merge standalone point labels like "(a)", "(1)" with next text
        merged = []
        i = 0
        while i < len(raw_texts):
            text = raw_texts[i]
            if re.match(r'^\([a-z]+\)$', text) or re.match(r'^\([ivxlcdm]+\)$', text) or re.match(r'^\(\d+\)$', text):
                if i + 1 < len(raw_texts):
                    merged.append(f'{text} {raw_texts[i + 1]}')
                    i += 2
                    continue
            merged.append(text)
            i += 1
        art_data['paragraphs'] = merged

        if art_data['title'] or art_data['paragraphs']:
            result['articles'].append(art_data)

    # Final/signature block
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and text.startswith('Done at'):
            result['final'] = text
            break

    return result


def parse_oj_html(html_path: str, celex: str = '') -> dict:
    """
    Parse an OJ-format HTML file (from EUR-Lex or Cellar XHTML) and extract
    the same structure as parse_formex(). This enables translating legislation
    fetched from the Cellar API when Formex XML is not available.
    Also supports consolidated EUR-Lex HTML (class: title-article-norm, norm, etc.)
    """
    from bs4 import BeautifulSoup

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    result = {
        'source_file': html_path,
        'metadata': {'celex': celex, 'language': 'EN'},
        'title': '',
        'preamble_init': '',
        'visas': [],
        'recitals_init': '',
        'recitals': [],
        'preamble_final': '',
        'chapters': [],
        'articles': [],
        'final': '',
    }

    # Detect consolidated EUR-Lex format
    is_consolidated = bool(soup.select('p.title-article-norm'))
    if is_consolidated:
        return _parse_consolidated_html(soup, html_path, celex)

    # Title: <p class="oj-doc-ti"> elements
    title_els = soup.select('p.oj-doc-ti')
    if title_els:
        result['title'] = ' '.join(el.get_text(strip=True) for el in title_els)

    # Preamble init: text before visas (usually "THE EUROPEAN PARLIAMENT AND THE COUNCIL...")
    # Look for the institutional formula
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and ('EUROPEAN PARLIAMENT' in text.upper() or 'THE COUNCIL' in text.upper()):
            if 'Having regard' not in text and 'Whereas' not in text:
                result['preamble_init'] = text
                break

    # Visas: "Having regard to..." paragraphs
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and text.startswith('Having regard to'):
            result['visas'].append(text)

    # Recitals: within <div class="eli-subdivision" id="rct_NNN">
    recital_divs = soup.select('div.eli-subdivision[id^="rct_"]')
    if recital_divs:
        for div in recital_divs:
            # Get the text (skip the number cell in tables)
            tds = div.find_all('td')
            if len(tds) >= 2:
                text = tds[-1].get_text(strip=True)
            else:
                text = div.get_text(strip=True)
            if text:
                result['recitals'].append(text)
    else:
        # Fallback: look for numbered paragraphs (1), (2), etc. after "Whereas:"
        in_recitals = False
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if 'Whereas:' in text or 'Whereas' == text.strip(':'):
                in_recitals = True
                result['recitals_init'] = 'Whereas:'
                continue
            if in_recitals:
                if text and (text[0] == '(' and text[1:3].strip(')').isdigit()):
                    result['recitals'].append(text)
                elif 'HAS ADOPTED' in text.upper() or 'HAVE ADOPTED' in text.upper():
                    in_recitals = False
                    result['preamble_final'] = text

    # Preamble final: "HAS ADOPTED THIS REGULATION:" etc.
    if not result['preamble_final']:
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text and ('HAS ADOPTED' in text.upper() or 'HAVE ADOPTED' in text.upper()):
                result['preamble_final'] = text
                break

    # Articles: <p class="oj-ti-art"> within <div class="eli-subdivision">
    article_headers = soup.select('p.oj-ti-art')
    for art_header in article_headers:
        art_text = art_header.get_text(strip=True)
        # Extract article number
        art_num_match = re.search(r'Article\s+(\d+[a-z]?)', art_text)
        art_num = art_num_match.group(1) if art_num_match else art_text

        art_data = {
            'identifier': f'ART_{art_num}',
            'title': art_text,
            'paragraphs': [],
        }

        # Get the parent container and extract paragraphs
        container = art_header.find_parent('div', class_='eli-subdivision')
        if container:
            raw_texts = []
            for p in container.find_all('p'):
                if p == art_header:
                    continue
                # Skip article title class
                if 'oj-ti-art' in (p.get('class') or []):
                    continue
                text = p.get_text(strip=True)
                if text and text != art_text:
                    raw_texts.append(text)

            # Merge standalone point labels like "(a)", "(b)", "(i)" with the next text
            merged = []
            i = 0
            while i < len(raw_texts):
                text = raw_texts[i]
                if re.match(r'^\([a-z]+\)$', text) or re.match(r'^\([ivxlcdm]+\)$', text) or re.match(r'^\(\d+\)$', text):
                    # This is a standalone label -- merge with next
                    if i + 1 < len(raw_texts):
                        merged.append(f'{text} {raw_texts[i + 1]}')
                        i += 2
                        continue
                merged.append(text)
                i += 1
            art_data['paragraphs'] = merged

        if art_data['title'] or art_data['paragraphs']:
            result['articles'].append(art_data)

    # Final/signature block: look for "Done at" pattern
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and text.startswith('Done at'):
            result['final'] = text
            break

    return result


def fetch_from_cellar(celex: str) -> str:
    """
    Fetch OJ HTML from the Publications Office Cellar API.
    Returns path to saved HTML file, or raises if not found.
    Bypasses EUR-Lex WAF by using publications.europa.eu.
    """
    import httpx

    url = f'https://publications.europa.eu/resource/celex/{celex}'
    headers = {
        'User-Agent': 'Brubru/1.0 (EU Policy Assistant; +https://brubru.eu)',
        'Accept': 'application/xhtml+xml, text/html',
        'Accept-Language': 'eng',
    }

    print(f'[INFO] Fetching {celex} from Cellar API...')
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=60)

    if r.status_code != 200:
        raise RuntimeError(f'Cellar returned HTTP {r.status_code} for {celex}')

    if 'Article' not in r.text and 'oj-ti-art' not in r.text:
        raise RuntimeError(f'Cellar response for {celex} has no article content ({len(r.text)} bytes)')

    path = f'/tmp/{celex}_cellar.html'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(r.text)

    print(f'[OK] Fetched {len(r.text)} bytes -> {path}')
    return path


def find_xml(search_term: str, base_dir: str = 'docs/LEG_2025-11') -> list:
    """Find XML files matching an OJ reference pattern."""
    results = []
    for dirpath, dirnames, filenames in os.walk(base_dir):
        for f in filenames:
            if f.endswith('.xml') and not f.endswith('.doc.xml'):
                if search_term in f:
                    results.append(os.path.join(dirpath, f))
    return sorted(results)


# ============================================================
# Step 2: Translation Engine
# ============================================================

# Brubru Catalan EU Legal Glossary
# Post-processing corrections applied after any engine.
# When in doubt, check Spanish EUR-Lex and assess Catalan equivalent.
GLOSSARY_CORRECTIONS = [
    # Wrong AINA outputs (Brubru Catalan standard, 24 March 2026)
    ("HA ACONSEGUIT", "HA ADOPTAT"),
    ("ha aconseguit", "ha adoptat"),
    ("d'implementació", "d'execució"),
    ("D'IMPLEMENTACIÓ", "D'EXECUCIÓ"),
    ("d'Implementació", "d'Execució"),
    ("Implementació", "Execució"),
    ("Comitè Estatal Membre", "Comitè dels Estats membres"),
    ("Comitè de l'Agència de l'Estat membre", "Comitè dels Estats membres"),
    # EU legal context corrections (25 March 2026, feedback from Catalan legal expert)
    # "Whereas" in EU recitals = "Atenent que" (not "Mentre que" which is literal/colloquial)
    ("Mentre que:", "Atenent que:"),
    ("mentre que:", "atenent que:"),
    ("MENTRE QUE:", "ATENENT QUE:"),
]

SOFTCATALA_MODEL_URL = "https://www.softcatala.org/pub/softcatala/opennmt/models/2022-11-22/eng-cat-2024-09-24.zip"
SOFTCATALA_MODEL_DIR = os.path.expanduser("~/.cache/brubru/softcatala-en-ca")


def _ensure_softcatala_model() -> str:
    """Download and extract Softcatala model if not cached. Returns model dir."""
    ct2_dir = os.path.join(SOFTCATALA_MODEL_DIR, "eng-cat", "ctranslate2")
    if os.path.exists(ct2_dir) and os.path.exists(os.path.join(ct2_dir, "model.bin")):
        return SOFTCATALA_MODEL_DIR

    # Check /tmp first (from earlier download)
    tmp_dir = "/tmp/softcatala-en-ca/eng-cat/eng-cat"
    if os.path.exists(os.path.join(tmp_dir, "ctranslate2", "model.bin")):
        os.makedirs(SOFTCATALA_MODEL_DIR, exist_ok=True)
        import shutil
        for item in os.listdir(tmp_dir):
            src = os.path.join(tmp_dir, item)
            dst = os.path.join(SOFTCATALA_MODEL_DIR, item)
            if not os.path.exists(dst):
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        return SOFTCATALA_MODEL_DIR

    # Download fresh
    import urllib.request
    import zipfile
    print('[INFO] Downloading Softcatala en-ca model (469 MB)...')
    os.makedirs(SOFTCATALA_MODEL_DIR, exist_ok=True)
    zip_path = os.path.join(SOFTCATALA_MODEL_DIR, "eng-cat.zip")
    urllib.request.urlretrieve(SOFTCATALA_MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(SOFTCATALA_MODEL_DIR)
    os.remove(zip_path)
    # Flatten: eng-cat/eng-cat/* -> model_dir/*
    nested = os.path.join(SOFTCATALA_MODEL_DIR, "eng-cat", "eng-cat")
    if os.path.exists(nested):
        import shutil
        for item in os.listdir(nested):
            shutil.move(os.path.join(nested, item), os.path.join(SOFTCATALA_MODEL_DIR, item))
        shutil.rmtree(os.path.join(SOFTCATALA_MODEL_DIR, "eng-cat"))
    print(f'[OK] Softcatala model cached at {SOFTCATALA_MODEL_DIR}')
    return SOFTCATALA_MODEL_DIR


def _apply_glossary(text: str) -> str:
    """Apply Brubru Catalan legal glossary corrections."""
    for wrong, correct in GLOSSARY_CORRECTIONS:
        text = text.replace(wrong, correct)
    return text


def translate_segments_softcatala(parsed: dict, output_dir: str = '', celex: str = '') -> dict:
    """
    Translate all segments using Softcatala NMT (CTranslate2, local, free).
    Primary engine for the Catalan acquis library.
    """
    import ctranslate2
    import sentencepiece as spm

    model_dir = _ensure_softcatala_model()
    ct2_dir = os.path.join(model_dir, "ctranslate2")
    sp_path = os.path.join(model_dir, "tokenizer", "sp_m.model")

    # Fallback: check nested structure
    if not os.path.exists(sp_path):
        sp_path = os.path.join(model_dir, "eng-cat", "tokenizer", "sp_m.model")
        ct2_dir = os.path.join(model_dir, "eng-cat", "ctranslate2")

    sp = spm.SentencePieceProcessor(model_file=sp_path)
    translator = ctranslate2.Translator(ct2_dir)

    def translate_text(text: str) -> str:
        if not text.strip():
            return text
        tokens = sp.encode(text, out_type=str)
        result = translator.translate_batch([tokens], beam_size=5, max_decoding_length=1024)
        translated = sp.decode(result[0].hypotheses[0])
        return _apply_glossary(translated)

    def translate_batch(texts: list, label: str) -> list:
        if not texts:
            return []
        all_tokens = [sp.encode(t, out_type=str) for t in texts]
        results = translator.translate_batch(all_tokens, beam_size=5, max_decoding_length=1024)
        translated = [_apply_glossary(sp.decode(r.hypotheses[0])) for r in results]
        print(f'  [{label}] Translated {len(translated)}/{len(texts)}')
        return translated

    return _do_translate(parsed, translate_text, translate_batch, output_dir, celex)


def translate_segments_sonnet(parsed: dict, output_dir: str = '', celex: str = '') -> dict:
    """
    Translate all segments using Claude Sonnet (API, paid).
    Fallback engine for high-quality review or complex texts.
    """
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

    client = anthropic.Anthropic()

    system_prompt = """You are a professional legal translator for EU legislation from English to Catalan.

BRUBRU CATALAN STANDARD:
- "Reglament" for Regulation, "Directiva" for Directive, "Decisió" for Decision
- "D'execució" for Implementing (never "d'implementació")
- "Ha adoptat" for has adopted
- "Tenint en compte" for Having regard to
- "Atenent que:" for Whereas: (in recital preamble, NEVER "Mentre que:")
- "Dictamen" for opinion (legal)
- "Paràgraf" for paragraph
- "Comitè dels Estats membres" for Member State Committee
- "article" (lowercase) within same act, "l'article X" with elision
- "Parlament Europeu", "Comissió Europea", "Consell"
- "Diari Oficial de la Unió Europea" for Official Journal
- "ha de" for shall, "pot" for may, "considerant" for recital
- Preserve ALL article numbers, cross-references, dates, CELEX numbers exactly
- Use proper Catalan: elisions (l', d', n'), apostrophes, accent marks (à, è, é, í, ó, ú, ï, ü)

Return ONLY the translation, no explanations."""

    def translate_text(text: str) -> str:
        if not text.strip():
            return text
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        return _apply_glossary(response.content[0].text)

    def translate_batch(texts: list, label: str) -> list:
        if not texts:
            return []
        chunk_size = 20
        results = []
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i+chunk_size]
            numbered = '\n'.join(f'[{j+1}] {t}' for j, t in enumerate(chunk))
            prompt = f"Translate each numbered item to Catalan. Keep the [N] numbering. Return ONLY the translations.\n\n{numbered}"

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            for line in response_text.split('\n'):
                line = line.strip()
                match = re.match(r'\[(\d+)\]\s*(.*)', line)
                if match:
                    results.append(_apply_glossary(match.group(2)))
                elif line and not line.startswith('['):
                    if results:
                        results[-1] += ' ' + line

            print(f'  [{label}] Translated {min(i+chunk_size, len(texts))}/{len(texts)}')

        if len(results) != len(texts):
            print(f'  [{label}] Batch parse mismatch ({len(results)} vs {len(texts)}), falling back to individual')
            results = [translate_text(t) for t in texts]

        return results

    return _do_translate(parsed, translate_text, translate_batch, output_dir, celex)


def _save_progress(progress_file: str, translated: dict, phase: str, pct: int):
    """Save incremental progress to JSON file."""
    progress = {
        'phase': phase,
        'percent': pct,
        'title': translated.get('title', '')[:100],
        'visas_done': len(translated.get('visas', [])),
        'recitals_done': len(translated.get('recitals', [])),
        'articles_done': len(translated.get('articles', [])),
        'timestamp': datetime.now().isoformat(),
    }
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def _save_partial_html(output_dir: str, translated: dict, celex: str):
    """Save partial HTML so progress can be inspected at any time."""
    os.makedirs(output_dir, exist_ok=True)
    partial_path = os.path.join(output_dir, 'index.partial.html')
    try:
        html = generate_html(translated, celex)
        with open(partial_path, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass  # Don't fail the translation if partial save fails


def _do_translate(parsed: dict, translate_text, translate_batch,
                  output_dir: str = '', celex: str = '') -> dict:
    """Shared translation orchestration for any engine."""
    translated = {
        'metadata': parsed['metadata'],
        'source_file': parsed['source_file'],
        'title': '',
        'preamble_init': '',
        'visas': [],
        'recitals_init': '',
        'recitals': [],
        'preamble_final': '',
        'articles': [],
        'final': '',
    }

    total_articles = len(parsed['articles'])
    total_recitals = len(parsed['recitals'])
    total_segments = total_articles + total_recitals + len(parsed['visas']) + 4
    done_segments = 0
    progress_file = os.path.join(output_dir, '.progress.json') if output_dir else ''

    def _pct():
        return int(done_segments / total_segments * 100) if total_segments > 0 else 0

    print('[START] Translating title...')
    translated['title'] = translate_text(parsed['title'])
    done_segments += 1

    print('[START] Translating preamble...')
    translated['preamble_init'] = translate_text(parsed['preamble_init'])
    translated['preamble_final'] = translate_text(parsed['preamble_final'])
    translated['recitals_init'] = translate_text(parsed['recitals_init']) if parsed['recitals_init'] else ''
    done_segments += 2
    print(f'  [{_pct()}%] Preamble done')

    print(f'[START] Translating {len(parsed["visas"])} visas...')
    translated['visas'] = translate_batch(parsed['visas'], 'Visas')
    done_segments += len(parsed['visas'])
    print(f'  [{_pct()}%] Visas done')

    print(f'[START] Translating {total_recitals} recitals...')
    translated['recitals'] = translate_batch(parsed['recitals'], 'Recitals')
    done_segments += total_recitals
    print(f'  [{_pct()}%] Recitals done')
    if progress_file:
        _save_progress(progress_file, translated, 'recitals', _pct())
    if output_dir:
        _save_partial_html(output_dir, translated, celex)

    print(f'[START] Translating {total_articles} articles...')
    for i, art in enumerate(parsed['articles']):
        translated_art = {
            'identifier': art['identifier'],
            'title': translate_text(art['title']) if art['title'] else '',
            'paragraphs': [],
        }
        if art['paragraphs']:
            translated_art['paragraphs'] = translate_batch(
                art['paragraphs'], f'Art {art.get("identifier", i+1)}'
            )
        translated['articles'].append(translated_art)
        done_segments += 1
        if (i+1) % 10 == 0:
            print(f'  [{_pct()}%] Articles {i+1}/{total_articles} done')
            if progress_file:
                _save_progress(progress_file, translated, f'article {i+1}/{total_articles}', _pct())
            if output_dir:
                _save_partial_html(output_dir, translated, celex)

    if parsed['final']:
        print('[START] Translating final block...')
        translated['final'] = translate_text(parsed['final'])
        done_segments += 1

    # Clean up progress file and partial HTML
    if progress_file and os.path.exists(progress_file):
        os.remove(progress_file)
    partial_path = os.path.join(output_dir, 'index.partial.html') if output_dir else ''
    if partial_path and os.path.exists(partial_path):
        os.remove(partial_path)

    print(f'[100%] Translation complete')
    return translated


# ============================================================
# Step 3: HTML Generator
# ============================================================

def generate_html(translated: dict, celex: str) -> str:
    """Generate a Brubru-styled HTML page from translated segments."""

    title = translated['title']
    metadata = translated['metadata']
    oj_ref = metadata.get('oj_ref', '')
    doc_date = metadata.get('date', '')

    # Format date
    if doc_date and len(doc_date) == 8:
        formatted_date = f'{doc_date[6:8]}/{doc_date[4:6]}/{doc_date[:4]}'
    else:
        formatted_date = doc_date

    # Build visas HTML
    visas_html = ''
    for visa in translated['visas']:
        visas_html += f'<p class="visa">{visa},</p>\n'

    # Build recitals HTML (with explicit numbering)
    recitals_html = ''
    if translated['recitals_init']:
        recitals_html += f'<p class="recitals-init">{translated["recitals_init"]}</p>\n'
    for i, recital in enumerate(translated['recitals'], 1):
        # Strip any existing number like (3) at the start to avoid double-numbering
        clean = re.sub(r'^\s*\(\d+\)\s*', '', recital)
        recitals_html += f'<p class="recital">({i}) {clean}</p>\n'

    # Build articles HTML
    articles_html = ''
    for art in translated['articles']:
        art_title = art['title'] if art['title'] else ''
        articles_html += f'<div class="article" id="art-{art["identifier"]}">\n'
        if art_title:
            articles_html += f'  <h3 class="article-title">{art_title}</h3>\n'
        for para in art['paragraphs']:
            articles_html += f'  <p class="article-text">{para}</p>\n'
        articles_html += '</div>\n'

    eurlex_url = f'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}'

    return f'''<!DOCTYPE html>
<html lang="ca">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | Brubru</title>
  <meta name="description" content="Traducci&oacute; al catal&agrave; de {title}. Traducci&oacute; no oficial preparada per Brubru amb intel&middot;lig&egrave;ncia artificial.">
  <link href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css" rel="stylesheet">
  <style>
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../../New-Yorker-Font/ACaslonPro-Regular.otf') format('opentype'); font-weight: 400; font-style: normal; font-display: swap; }}
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../../New-Yorker-Font/ACaslonPro-Semibold.otf') format('opentype'); font-weight: 600; font-style: normal; font-display: swap; }}
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../../New-Yorker-Font/ACaslonPro-Bold.otf') format('opentype'); font-weight: 700; font-style: normal; font-display: swap; }}

    :root {{
      --color-blue: #0693e3; --color-green: #059669; --color-purple: #9b51e0;
      --color-amber: #d97706; --color-red: #dc2626; --color-text: #111827;
      --color-secondary: #6b7280; --color-border: #e5e7eb;
      --color-bg-alt: #f3f4f6; --color-bg: #ffffff;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Adobe Caslon Pro', Georgia, serif; background: var(--color-bg); color: var(--color-text); line-height: 1.8; font-size: 1.05rem; }}

    .disclaimer-banner {{ background: #fef3c7; border-bottom: 2px solid #d97706; padding: 0.75rem 2rem; font-size: 0.85rem; color: #92400e; text-align: center; }}
    .header {{ background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: 1rem 2rem; display: flex; align-items: center; gap: 1.5rem; position: sticky; top: 0; z-index: 100; }}
    .header__logo {{ height: 40px; }}
    .header__text {{ flex: 1; }}
    .header__title {{ font-size: 1rem; font-weight: 700; }}
    .header__subtitle {{ font-size: 0.8rem; color: var(--color-secondary); }}
    .header__cta {{ display: inline-block; padding: 0.5rem 1.25rem; border-radius: 8px; font-weight: 700; font-size: 0.85rem; color: white; background-size: 300% 100%; background-image: linear-gradient(90deg, var(--color-blue), var(--color-green), var(--color-purple), var(--color-amber), var(--color-blue)); animation: rainbowShift 4s ease infinite; text-decoration: none; }}
    @keyframes rainbowShift {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}

    .container {{ max-width: 900px; margin: 0 auto; padding: 2rem; }}
    .doc-header {{ text-align: center; padding: 2rem 0 1.5rem; border-bottom: 2px solid var(--color-blue); margin-bottom: 2rem; }}
    .doc-header h1 {{ font-size: 1.6rem; font-weight: 700; line-height: 1.3; margin-bottom: 0.75rem; }}
    .doc-header .meta {{ font-size: 0.85rem; color: var(--color-secondary); }}
    .doc-header .meta a {{ color: var(--color-blue); text-decoration: none; }}

    .preamble-init {{ font-weight: 700; font-size: 1.1rem; margin: 1.5rem 0 1rem; }}
    .visa {{ margin-bottom: 0.5rem; padding-left: 1rem; text-indent: -1rem; }}
    .recitals-init {{ font-weight: 600; margin: 1.5rem 0 0.5rem; }}
    .recital {{ margin-bottom: 0.75rem; text-align: justify; }}
    .preamble-final {{ font-weight: 700; font-size: 1.1rem; margin: 1.5rem 0; text-transform: uppercase; }}

    .article {{ margin-bottom: 1.5rem; padding: 1rem 0; border-top: 1px solid var(--color-border); }}
    .article-title {{ font-size: 1.1rem; font-weight: 700; color: var(--color-blue); margin-bottom: 0.5rem; }}
    .article-text {{ margin-bottom: 0.5rem; text-align: justify; }}

    .final-block {{ margin-top: 2rem; padding-top: 1rem; border-top: 2px solid var(--color-border); font-style: italic; color: var(--color-secondary); }}

    .footer {{ background: var(--color-bg-alt); border-top: 1px solid var(--color-border); padding: 2rem; text-align: center; font-size: 0.85rem; color: var(--color-secondary); margin-top: 3rem; }}
    .footer a {{ color: var(--color-blue); text-decoration: none; }}

    .back-to-top {{ position: fixed; bottom: 2rem; right: 2rem; width: 44px; height: 44px; border-radius: 50%; background: var(--color-blue); color: white; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); opacity: 0; transition: all 0.3s; z-index: 50; }}
    .back-to-top.visible {{ opacity: 1; }}

    @media (max-width: 767px) {{ .container {{ padding: 1.25rem; }} .header {{ padding: 0.75rem 1rem; }} .header__cta {{ display: none; }} .doc-header h1 {{ font-size: 1.3rem; }} }}
    html {{ scroll-behavior: smooth; }}
  </style>
</head>
<body>

<div class="disclaimer-banner">
  El catal&agrave; no &eacute;s una llengua oficial de la Uni&oacute; Europea. No existeix cap versi&oacute; oficial en catal&agrave; d'aquest text a EUR-Lex. Aquesta traducci&oacute; ha estat preparada per Brubru amb models d'intel&middot;lig&egrave;ncia artificial.
</div>

<header class="header" id="top">
  <img src="../../assets/brubru_mainlogo.png" alt="Brubru" class="header__logo">
  <div class="header__text">
    <div class="header__title">Legislaci&oacute; de la UE en catal&agrave;</div>
    <div class="header__subtitle">Traducci&oacute; no oficial</div>
  </div>
  <a href="https://brubru.beresol.eu" class="header__cta">Try Brubru Free</a>
</header>

<div class="container">

<div class="doc-header">
  <h1>{title}</h1>
  <div class="meta">
    CELEX: {celex} | <a href="{eurlex_url}" target="_blank" rel="noopener">Text original a EUR-Lex</a> | Data: {formatted_date}
  </div>
</div>

<p class="preamble-init">{translated['preamble_init']}</p>

{visas_html}

{recitals_html}

<p class="preamble-final">{translated['preamble_final']}</p>

{articles_html}

<div class="final-block">{translated['final']}</div>

</div>

<footer class="footer">
  <p>
    Traducci&oacute; al catal&agrave; per <a href="https://brubru.beresol.eu">Brubru</a>, l'assistent d'IA per a pol&iacute;tiques europees de <a href="https://beresol.eu">Beresol</a>.
    <br>Aquesta no &eacute;s una traducci&oacute; oficial. El text jur&iacute;dicament vinculant &eacute;s la versi&oacute; en les lleng&uuml;es oficials de la UE disponible a <a href="https://eur-lex.europa.eu" target="_blank" rel="noopener">EUR-Lex</a>.
  </p>
</footer>

<a href="#top" class="back-to-top" id="backToTop"><span class="mdi mdi-chevron-up"></span></a>
<script>
  window.addEventListener('scroll', function() {{
    var btn = document.getElementById('backToTop');
    if (window.scrollY > 400) {{ btn.classList.add('visible'); }} else {{ btn.classList.remove('visible'); }}
  }});
  document.getElementById('backToTop').addEventListener('click', function(e) {{
    e.preventDefault(); window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }});
</script>
</body>
</html>'''


# ============================================================
def _translate_one_html(html_path: str, celex: str, engine: str, output: str):
    """Translate an OJ HTML file (from Cellar or EUR-Lex) to Catalan."""
    import subprocess

    caffeinate_proc = None
    try:
        caffeinate_proc = subprocess.Popen(
            ['caffeinate', '-i', '-w', str(os.getpid())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print('[INFO] caffeinate active (Mac will stay awake)')
    except Exception:
        pass

    try:
        print(f'[START] Parsing OJ HTML: {html_path}...')
        parsed = parse_oj_html(html_path, celex=celex)
        print(f'  Title: {parsed["title"][:100]}')
        print(f'  {len(parsed["visas"])} visas, {len(parsed["recitals"])} recitals, {len(parsed["articles"])} articles')

        if not parsed['articles'] and not parsed['recitals']:
            print('[WARN] No articles or recitals found. The HTML structure may not be OJ format.')
            return

        output_dir = output or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'data', 'legislacio-ue-catala', celex
        )
        os.makedirs(output_dir, exist_ok=True)

        print(f'[START] Translating to Catalan (engine: {engine})...')
        if engine == 'sonnet':
            translated = translate_segments_sonnet(parsed, output_dir=output_dir, celex=celex)
        else:
            translated = translate_segments_softcatala(parsed, output_dir=output_dir, celex=celex)

        output_path = os.path.join(output_dir, 'index.html')
        html_output = generate_html(translated, celex)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_output)

        size_kb = os.path.getsize(output_path) / 1024
        print(f'[OK] Translation complete: {output_path} ({size_kb:.0f}KB)')
        print(f'  {len(translated["articles"])} articles, {len(translated["recitals"])} recitals')
    finally:
        if caffeinate_proc:
            caffeinate_proc.terminate()


# ============================================================
# Step 5: FTP Deploy to SiteGround
# ============================================================

SITEGROUND_REMOTE_DIR = 'brubru.beresol.eu/public_html/legislacio-ue-catala'


def _get_ftp_credentials() -> tuple:
    """Get FTP credentials from environment variables or .env file."""
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)

    host = os.environ.get('SITEGROUND_FTP_HOST')
    user = os.environ.get('SITEGROUND_FTP_USER')
    password = os.environ.get('SITEGROUND_FTP_PASS')
    port = int(os.environ.get('SITEGROUND_FTP_PORT', '21'))

    if not all([host, user, password]):
        raise RuntimeError(
            'FTP credentials not set. Add SITEGROUND_FTP_HOST, SITEGROUND_FTP_USER, '
            'SITEGROUND_FTP_PASS to backend/.env'
        )
    return host, user, password, port


def deploy_to_siteground(celex: str) -> bool:
    """Deploy a single translation to SiteGround via FTP."""
    import ftplib

    local_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '..', 'data', 'legislacio-ue-catala', celex
    )
    local_file = os.path.join(local_dir, 'index.html')

    if not os.path.isfile(local_file):
        print(f'[ERROR] No translation found at {local_file}')
        return False

    host, user, password, port = _get_ftp_credentials()

    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        ftp.cwd(SITEGROUND_REMOTE_DIR)

        # Create directory if needed
        remote_dirs = ftp.nlst()
        if celex not in remote_dirs:
            ftp.mkd(celex)
            print(f'  [FTP] Created directory {celex}/')

        ftp.cwd(celex)

        # Upload index.html
        size = os.path.getsize(local_file)
        with open(local_file, 'rb') as f:
            ftp.storbinary('STOR index.html', f)

        print(f'  [FTP] Uploaded {celex}/index.html ({size // 1024}KB)')
        ftp.quit()
        return True

    except Exception as e:
        print(f'[ERROR] FTP deploy failed for {celex}: {e}')
        return False


def deploy_all_to_siteground():
    """Deploy all local translations to SiteGround."""
    import ftplib

    translations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '..', 'data', 'legislacio-ue-catala'
    )

    host, user, password, port = _get_ftp_credentials()

    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=30)
    ftp.login(user, password)
    ftp.cwd(SITEGROUND_REMOTE_DIR)

    remote_dirs = set(ftp.nlst())
    deployed = 0
    skipped = 0

    for entry in sorted(os.listdir(translations_dir)):
        local_file = os.path.join(translations_dir, entry, 'index.html')
        if not os.path.isfile(local_file):
            continue
        if entry.endswith('-softcatala'):
            continue

        celex = entry

        # Create directory if needed
        if celex not in remote_dirs:
            ftp.mkd(celex)

        ftp.cwd(celex)

        size = os.path.getsize(local_file)
        with open(local_file, 'rb') as f:
            ftp.storbinary('STOR index.html', f)

        ftp.cwd('..')
        deployed += 1
        print(f'  [FTP] {celex}/index.html ({size // 1024}KB)')

    # Also upload the landing page
    landing = os.path.join(translations_dir, 'index.html')
    if os.path.isfile(landing):
        with open(landing, 'rb') as f:
            ftp.storbinary('STOR index.html', f)
        print(f'  [FTP] index.html (landing page)')

    ftp.quit()
    print(f'[OK] Deployed {deployed} translations to SiteGround')


# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Catalan EU Legislation Translation Pipeline')
    parser.add_argument('--parse', type=str, help='Parse a Formex XML file and show structure')
    parser.add_argument('--translate', type=str, help='Translate a Formex XML or OJ HTML file to Catalan')
    parser.add_argument('--html', type=str, help='Translate an OJ HTML file (from Cellar or EUR-Lex) to Catalan')
    parser.add_argument('--cellar', type=str, help='Fetch from Cellar API by CELEX and translate to Catalan')
    parser.add_argument('--engine', type=str, default='softcatala', choices=['softcatala', 'sonnet'],
                        help='Translation engine (default: softcatala)')
    parser.add_argument('--find', type=str, help='Find XML files matching an OJ reference pattern')
    parser.add_argument('--celex', type=str, default='', help='CELEX number for the output')
    parser.add_argument('--output', type=str, default='', help='Output HTML path (default: auto)')
    parser.add_argument('--batch', type=str, default='',
                        help='Batch file with one "xml_path|celex" per line for overnight translation')
    parser.add_argument('--deploy', action='store_true',
                        help='Deploy a translated CELEX to SiteGround via FTP after translation')
    parser.add_argument('--deploy-all', action='store_true',
                        help='Deploy ALL local translations to SiteGround via FTP')
    parser.add_argument('--deploy-only', type=str, default='',
                        help='Deploy a specific CELEX to SiteGround without translating (e.g. --deploy-only 32024R1689)')
    args = parser.parse_args()

    if args.find:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'docs', 'LEG_2025-11')
        results = find_xml(args.find, base_dir)
        if results:
            print(f'Found {len(results)} files:')
            for r in results:
                print(f'  {r}')
        else:
            print(f'No files found matching "{args.find}"')
        return

    if args.parse:
        parsed = parse_formex(args.parse)
        print(f'Title: {parsed["title"][:120]}')
        print(f'Metadata: {json.dumps(parsed["metadata"], indent=2)}')
        print(f'Visas: {len(parsed["visas"])}')
        print(f'Recitals: {len(parsed["recitals"])}')
        print(f'Articles: {len(parsed["articles"])}')
        print(f'Preamble init: {parsed["preamble_init"][:80]}...')
        print(f'Preamble final: {parsed["preamble_final"]}')
        print()
        for art in parsed['articles'][:5]:
            print(f'  Article {art["identifier"]}: {art["title"]} ({len(art["paragraphs"])} paragraphs)')
        if len(parsed['articles']) > 5:
            print(f'  ... and {len(parsed["articles"]) - 5} more articles')
        return

    if args.cellar:
        celex = args.cellar
        html_path = fetch_from_cellar(celex)
        _translate_one_html(html_path, celex, args.engine, args.output)
        if args.deploy:
            deploy_to_siteground(celex)
        return

    if args.html:
        if not args.celex:
            print('[ERROR] --celex is required with --html (e.g. --html file.html --celex 32026R0129)')
            return
        _translate_one_html(args.html, args.celex, args.engine, args.output)
        if args.deploy:
            deploy_to_siteground(args.celex)
        return

    # Deploy-only commands (no translation)
    if args.deploy_all:
        deploy_all_to_siteground()
        return

    if args.deploy_only:
        deploy_to_siteground(args.deploy_only)
        return

    if args.translate:
        _translate_one(args.translate, args.celex, args.engine, args.output)
        if args.deploy and args.celex:
            deploy_to_siteground(args.celex)
        return

    if args.batch:
        # Batch mode: translate multiple files. Format: "path|celex" per line
        if not os.path.exists(args.batch):
            print(f'[ERROR] Batch file not found: {args.batch}')
            return
        with open(args.batch, 'r') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        print(f'[BATCH] {len(lines)} acts to translate')
        for i, line in enumerate(lines):
            parts = line.split('|')
            xml_path = parts[0].strip()
            celex = parts[1].strip() if len(parts) > 1 else ''
            print(f'\n{"="*60}')
            print(f'[BATCH] Act {i+1}/{len(lines)}: {celex or xml_path}')
            print(f'{"="*60}')
            try:
                _translate_one(xml_path, celex, args.engine, '')
            except Exception as e:
                print(f'[ERROR] Failed: {e}')
                continue
        print(f'\n[BATCH] Done. {len(lines)} acts processed.')
        return

    parser.print_help()


def _translate_one(xml_path: str, celex: str, engine: str, output: str):
    """Translate a single XML file."""
    import subprocess, signal

    # Auto-caffeinate: prevent Mac from sleeping during translation
    caffeinate_proc = None
    try:
        caffeinate_proc = subprocess.Popen(
            ['caffeinate', '-i', '-w', str(os.getpid())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print('[INFO] caffeinate active (Mac will stay awake)')
    except Exception:
        print('[WARN] caffeinate not available, Mac may sleep during translation')

    try:
        print(f'[START] Parsing {xml_path}...')
        parsed = parse_formex(xml_path)
        print(f'  Title: {parsed["title"][:100]}')
        print(f'  {len(parsed["visas"])} visas, {len(parsed["recitals"])} recitals, {len(parsed["articles"])} articles')

        celex = celex or parsed['metadata'].get('doc_number', '').replace('/', '')
        if not celex:
            celex = 'unknown'

        output_dir = output or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'data', 'legislacio-ue-catala', celex
        )
        os.makedirs(output_dir, exist_ok=True)

        print(f'[START] Translating to Catalan (engine: {engine})...')
        if engine == 'sonnet':
            translated = translate_segments_sonnet(parsed, output_dir, celex)
        else:
            translated = translate_segments_softcatala(parsed, output_dir, celex)

        output_path = os.path.join(output_dir, 'index.html')
        html = generate_html(translated, celex)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f'[OK] HTML generated: {output_path}')
        print(f'  Title: {translated["title"][:100]}')
        print(f'  CELEX: {celex}')
        print(f'  Size: {len(html) // 1024}KB')
    finally:
        if caffeinate_proc:
            caffeinate_proc.terminate()
            caffeinate_proc.wait()


if __name__ == '__main__':
    main()
