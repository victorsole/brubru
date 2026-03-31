#!/usr/bin/env python3.12
"""
Import existing Catalan translations into the database.

Scans data/legislacio-ue-catala/*/index.html, extracts metadata
from the HTML files, and inserts records into catalan_translations.

Usage:
    cd backend
    python3.12 scripts/import_catalan_translations.py
    python3.12 scripts/import_catalan_translations.py --dry-run
"""

import argparse
import os
import re
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal, init_db
from models.catalan_translation import CatalanTranslation


# Category mapping: CELEX -> (category_ca, category_en, short_name, doc_type)
TRANSLATIONS_META = {
    # Transformacio digital
    '32024R1689': ('Transformacio digital', 'Digital Transformation', 'AI Act', 'regulation'),
    '32024R2847': ('Transformacio digital', 'Digital Transformation', 'CRA', 'regulation'),
    '32022L2555': ('Transformacio digital', 'Digital Transformation', 'NIS2', 'directive'),
    '32022R2065': ('Transformacio digital', 'Digital Transformation', 'DSA', 'regulation'),
    '32022R1925': ('Transformacio digital', 'Digital Transformation', 'DMA', 'regulation'),
    '32023R2854': ('Transformacio digital', 'Digital Transformation', 'Data Act', 'regulation'),
    '32024R1781': ('Transformacio digital', 'Digital Transformation', 'ESPR', 'regulation'),
    '32026R0722': ('Transformacio digital', 'Digital Transformation', 'DORA ITS', 'implementing'),
    # Politiques economiques i de mercat
    '32016R0679': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'GDPR', 'regulation'),
    '32009L0138': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'Solvency II', 'directive'),
    '32022R2554': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'DORA', 'regulation'),
    '32023R1114': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'MiCA', 'regulation'),
    '32013R0575': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'CRR', 'regulation'),
    '32014L0065': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'MiFID II', 'directive'),
    '32015L2366': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'PSD2', 'directive'),
    '32011L0061': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'AIFMD', 'directive'),
    '32014R0596': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'MAR', 'regulation'),
    '32022R2560': ('Politiques economiques i de mercat', 'Core Economic and Market Policies', 'FSR', 'regulation'),
    # Sostenibilitat i medi ambient
    '32021R1119': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'Climate Law', 'regulation'),
    '32023R0956': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'CBAM', 'regulation'),
    '32024R1735': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'NZIA', 'regulation'),
    '32019D1194': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'PTBP/REACH', 'decision'),
    '32006R1907': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'REACH', 'regulation'),
    '32023R1115': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'EUDR', 'regulation'),
    '32020R0852': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'Taxonomy', 'regulation'),
    '32022L2464': ('Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies', 'CSRD', 'directive'),
    # Politiques socials
    '32017R0745': ('Politiques socials', 'Social Policies', 'MDR', 'regulation'),
    '32025R0327': ('Politiques socials', 'Social Policies', 'EHDS', 'regulation'),
    '32024L1760': ('Politiques socials', 'Social Policies', 'CS3D', 'directive'),
    '32021R2115': ('Politiques socials', 'Social Policies', 'CAP Strategic Plans', 'regulation'),
    # Agricultura i recursos naturals
    '32026R0174': ('Agricultura i recursos naturals', 'Agriculture and Natural Resources', 'CAP Del. Reg.', 'delegated'),
    '32026R0177': ('Agricultura i recursos naturals', 'Agriculture and Natural Resources', 'CAP Del. Reg.', 'delegated'),
    '32026R0149': ('Agricultura i recursos naturals', 'Agriculture and Natural Resources', 'CAP Del. Reg.', 'delegated'),
    '32026R0129': ('Agricultura i recursos naturals', 'Agriculture and Natural Resources', 'CAP Del. Reg.', 'delegated'),
    # Comerc i politica exterior
    '32026R0734': ('Comerc i politica exterior', 'Trade and External Policy', 'Antidumping', 'implementing'),
    '32026R0709': ('Comerc i politica exterior', 'Trade and External Policy', 'Antidumping', 'implementing'),
    '32026R0702': ('Comerc i politica exterior', 'Trade and External Policy', 'Antidumping', 'implementing'),
    '32026R0701': ('Comerc i politica exterior', 'Trade and External Policy', 'Antidumping', 'implementing'),
    '32026D0728': ('Comerc i politica exterior', 'Trade and External Policy', 'Istanbul Convention', 'decision'),
    '32026D0681': ('Comerc i politica exterior', 'Trade and External Policy', 'OLAF/Waste Shipment', 'decision'),
}


def extract_metadata_from_html(html_path: str) -> dict:
    """Extract title, article count, and recital count from a translated HTML file."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    size = os.path.getsize(html_path)

    # Extract Catalan title from <title> tag
    title_match = re.search(r'<title>(.*?)</title>', content)
    title_ca = title_match.group(1).replace('&amp;', '&') if title_match else ''
    # Clean HTML entities
    title_ca = title_ca.replace('&#39;', "'").replace('&quot;', '"')

    # Extract English title from the first <h2> or meta tag if available
    # Fallback: use the Catalan title
    title_en = title_ca

    # Count articles and recitals
    articles = content.count('class="article-title"') - 1  # Subtract the CSS definition
    if articles < 0:
        articles = 0
    recitals = content.count('class="recital"')

    # Detect source format
    if 'Consolidated' in html_path or 'consolidated' in html_path:
        source_format = 'consolidated_html'
    elif 'cellar' in html_path.lower():
        source_format = 'cellar'
    else:
        source_format = 'formex'

    return {
        'title_ca': title_ca,
        'title_en': title_en,
        'articles_count': articles,
        'recitals_count': recitals,
        'html_size_bytes': size,
        'source_format': source_format,
    }


def main():
    parser = argparse.ArgumentParser(description='Import Catalan translations into database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without inserting')
    args = parser.parse_args()

    # Initialize database (creates table if needed)
    init_db()

    translations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data', 'legislacio-ue-catala'
    )

    if not os.path.exists(translations_dir):
        print(f'[ERROR] Translations directory not found: {translations_dir}')
        sys.exit(1)

    db = SessionLocal()
    imported = 0
    skipped = 0
    errors = 0

    try:
        for entry in sorted(os.listdir(translations_dir)):
            html_path = os.path.join(translations_dir, entry, 'index.html')
            if not os.path.isfile(html_path):
                continue

            celex = entry
            # Skip the softcatala test variant
            if celex.endswith('-softcatala'):
                continue

            meta = TRANSLATIONS_META.get(celex)
            if not meta:
                print(f'[WARN] No metadata for {celex}, skipping')
                skipped += 1
                continue

            category_ca, category_en, short_name, doc_type = meta

            try:
                html_meta = extract_metadata_from_html(html_path)
            except Exception as e:
                print(f'[ERROR] Failed to parse {celex}: {e}')
                errors += 1
                continue

            if args.dry_run:
                print(f'[DRY] {celex:16s} | {short_name:20s} | {category_ca:40s} | '
                      f'arts={html_meta["articles_count"]:4d} recs={html_meta["recitals_count"]:4d} | '
                      f'{html_meta["html_size_bytes"] // 1024:5d}KB')
                imported += 1
                continue

            # Check if already exists
            existing = db.query(CatalanTranslation).filter_by(celex=celex).first()
            if existing:
                # Update
                existing.title_ca = html_meta['title_ca']
                existing.short_name = short_name
                existing.doc_type = doc_type
                existing.category = category_ca
                existing.category_en = category_en
                existing.articles_count = html_meta['articles_count']
                existing.recitals_count = html_meta['recitals_count']
                existing.html_size_bytes = html_meta['html_size_bytes']
                existing.source_format = html_meta['source_format']
                existing.siteground_url = f'https://brubru.beresol.eu/legislacio-ue-catala/{celex}/'
                print(f'[UPD] {celex} ({short_name})')
            else:
                # Insert
                record = CatalanTranslation(
                    celex=celex,
                    title_en=html_meta['title_en'],
                    title_ca=html_meta['title_ca'],
                    short_name=short_name,
                    doc_type=doc_type,
                    category=category_ca,
                    category_en=category_en,
                    articles_count=html_meta['articles_count'],
                    recitals_count=html_meta['recitals_count'],
                    html_size_bytes=html_meta['html_size_bytes'],
                    engine='softcatala',
                    source_format=html_meta['source_format'],
                    siteground_url=f'https://brubru.beresol.eu/legislacio-ue-catala/{celex}/',
                )
                db.add(record)
                print(f'[NEW] {celex} ({short_name})')

            imported += 1

        if not args.dry_run:
            db.commit()
            print(f'\n[OK] Committed {imported} translations to database')
        else:
            print(f'\n[DRY RUN] Would import {imported} translations')

        if skipped:
            print(f'[WARN] Skipped {skipped} (no metadata mapping)')
        if errors:
            print(f'[ERROR] Failed {errors}')

    finally:
        db.close()


if __name__ == '__main__':
    main()
