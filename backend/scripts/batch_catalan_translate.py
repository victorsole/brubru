#!/usr/bin/env python3.12
"""
Batch Catalan Translation Pipeline

Processes the translation queue file, translating acts one by one,
auditing each, importing to DB, and deploying to SiteGround.

Usage:
    cd backend

    # Translate next N acts from queue (default: 10)
    python3.12 scripts/batch_catalan_translate.py --count 10

    # Translate only small files (<10KB, fast)
    python3.12 scripts/batch_catalan_translate.py --max-size 10 --count 50

    # Translate medium files (10-50KB)
    python3.12 scripts/batch_catalan_translate.py --min-size 10 --max-size 50 --count 20

    # Dry run (show what would be translated)
    python3.12 scripts/batch_catalan_translate.py --count 20 --dry-run

    # Resume from a specific CELEX
    python3.12 scripts/batch_catalan_translate.py --start-from 32020R0001 --count 10

Created: 8 April 2026
"""

import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


QUEUE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'legislacio-ue-catala', 'translation_queue.txt'
)

TRANSLATE_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'catalan_translate.py'
)

TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'legislacio-ue-catala'
)

# Category auto-classification based on keywords in title
CATEGORY_RULES = [
    # (keywords_in_title, category_ca, category_en)
    (['antidumping', 'countervailing', 'anti-dumping', 'safeguard measure'], 'Comerc i politica exterior', 'Trade and External Policy'),
    (['customs', 'tariff', 'import', 'export', 'trade'], 'Comerc i politica exterior', 'Trade and External Policy'),
    (['fisheries', 'fishing', 'aquaculture', 'fish'], 'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['agriculture', 'CAP', 'agri', 'farm', 'crop', 'wine', 'olive', 'sugar', 'milk', 'beef', 'poultry', 'cereal'], 'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['animal', 'veterinary', 'plant health', 'phytosanitary', 'food safety', 'feed'], 'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['environment', 'emission', 'climate', 'carbon', 'waste', 'water', 'pollution', 'biodiversity', 'natura 2000', 'habitat'], 'Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies'),
    (['energy', 'renewable', 'electricity', 'gas', 'nuclear', 'petroleum', 'fuel'], 'Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies'),
    (['digital', 'data', 'cyber', 'electronic', 'telecom', 'AI', 'artificial intelligence', 'platform', 'online'], 'Transformacio digital', 'Digital Transformation'),
    (['bank', 'credit', 'financial', 'insurance', 'securities', 'investment', 'capital', 'payment', 'money laundering', 'prudential'], 'Politiques economiques i de mercat', 'Core Economic and Market Policies'),
    (['competition', 'state aid', 'merger', 'antitrust', 'subsid'], 'Politiques economiques i de mercat', 'Core Economic and Market Policies'),
    (['transport', 'aviation', 'railway', 'maritime', 'road', 'shipping', 'port'], 'Politiques economiques i de mercat', 'Core Economic and Market Policies'),
    (['health', 'medicinal', 'pharmaceutical', 'medical device', 'patient'], 'Politiques socials', 'Social Policies'),
    (['worker', 'employment', 'labour', 'social', 'pension', 'equality', 'discrimination'], 'Politiques socials', 'Social Policies'),
    (['migration', 'asylum', 'border', 'visa', 'Schengen', 'police', 'criminal', 'judicial', 'Europol', 'Eurojust'], 'Justicia i afers d interior', 'Justice and Home Affairs'),
    (['foreign', 'CFSP', 'sanctions', 'restrictive measures', 'third countr'], 'Comerc i politica exterior', 'Trade and External Policy'),
]


def classify_act(title: str) -> tuple:
    """Auto-classify an act by title keywords. Returns (category_ca, category_en)."""
    title_lower = title.lower()
    for keywords, cat_ca, cat_en in CATEGORY_RULES:
        if any(kw.lower() in title_lower for kw in keywords):
            return cat_ca, cat_en
    return 'Altres', 'Other'


def detect_doc_type(title: str) -> str:
    """Detect document type from title."""
    t = title.lower()
    if 'implementing regulation' in t or "reglament d'execucio" in t.lower():
        return 'implementing'
    if 'delegated regulation' in t or 'reglament delegat' in t.lower():
        return 'delegated'
    if 'directive' in t or 'directiva' in t.lower():
        return 'directive'
    if 'decision' in t or 'decisio' in t.lower():
        return 'decision'
    return 'regulation'


def audit_translation(celex: str) -> list:
    """Run audit checks on a translation. Returns list of issues."""
    f = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    if not os.path.isfile(f):
        return ['File not found']

    with open(f, 'r') as fh:
        content = fh.read()

    problems = []

    if re.findall(r'Having regard', content, re.IGNORECASE):
        problems.append('Having regard')
    if re.findall(r'Whereas:', content):
        problems.append('Whereas:')
    if re.findall(r'd.implementaci', content, re.IGNORECASE):
        problems.append('d implementacio')

    titles = re.findall(r'<h3 class="article-title">(.*?)</h3>', content)
    bad_t = [t for t in titles if '{' not in t and not re.match(r'Article\s+\d', t)]
    if bad_t:
        problems.append(f'Bad titles: {len(bad_t)}')

    recitals = re.findall(r'class="recital">(.*?)(?:</p>|$)', content, re.DOTALL)
    has_recitals = len(recitals) > 0
    has_atenent = 'Atenent que' in content
    if has_recitals and not has_atenent:
        problems.append('Missing Atenent que')

    if re.findall(r'Please provide|I need the complete text', content):
        problems.append('Sonnet leak')

    return problems


def auto_fix(celex: str) -> int:
    """Apply auto-fixes to a translation. Returns number of fixes applied."""
    f = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    with open(f, 'r') as fh:
        content = fh.read()

    original = content
    fixes = 0

    # Fix leading quotes in article titles
    new = re.sub(r'<h3 class="article-title">["\u0027]+\s*(Article)', r'<h3 class="article-title">\1', content)
    if new != content:
        fixes += 1
        content = new

    # Fix lowercase article titles
    def fix_lowercase(m):
        text = m.group(1).strip()
        text = re.sub(r"^[lL]'?\s*", '', text)
        text = text.replace('article', 'Article', 1)
        return f'<h3 class="article-title">{text}</h3>'

    new = re.sub(
        r'<h3 class="article-title">((?:l\'?\s*)?article\s+\d+[a-z ]*)</h3>',
        fix_lowercase, content, flags=re.IGNORECASE
    )
    if new != content:
        fixes += 1
        content = new

    # Add missing Atenent que header
    if '<p class="recitals-init">' not in content and '<p class="recital">' in content:
        content = content.replace(
            '<p class="recital">', '<p class="recitals-init">Atenent que:</p>\n<p class="recital">', 1
        )
        fixes += 1

    if content != original:
        with open(f, 'w') as fh:
            fh.write(content)

    return fixes


def import_to_db(celex: str, title_ca: str, articles: int, recitals: int, size: int, engine: str):
    """Import translation metadata to database."""
    from core.database import SessionLocal
    from models.catalan_translation import CatalanTranslation

    cat_ca, cat_en = classify_act(title_ca)
    doc_type = detect_doc_type(title_ca)

    db = SessionLocal()
    try:
        existing = db.query(CatalanTranslation).filter_by(celex=celex).first()
        if existing:
            existing.title_ca = title_ca
            existing.articles_count = articles
            existing.recitals_count = recitals
            existing.html_size_bytes = size
            existing.category = cat_ca
            existing.category_en = cat_en
        else:
            db.add(CatalanTranslation(
                celex=celex, title_en=title_ca, title_ca=title_ca,
                short_name=celex, doc_type=doc_type,
                category=cat_ca, category_en=cat_en,
                articles_count=articles, recitals_count=recitals,
                html_size_bytes=size, engine=engine, source_format='formex',
                siteground_url=f'https://brubru.beresol.eu/legislacio-ue-catala/{celex}/',
            ))
        db.commit()
    finally:
        db.close()


def translate_one(xml_path: str, celex: str) -> bool:
    """Translate a single act (no deploy). Returns True if successful."""
    cmd = [
        'python3.12', TRANSLATE_SCRIPT,
        '--translate', xml_path,
        '--celex', celex,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f'    [ERROR] Translation failed: {result.stderr[-200:] if result.stderr else "unknown"}')
        return False
    return True


def get_ftp_connection():
    """Open a persistent FTP connection for batch deploy."""
    import ftplib
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)

    host = os.environ['SITEGROUND_FTP_HOST']
    user = os.environ['SITEGROUND_FTP_USER']
    password = os.environ['SITEGROUND_FTP_PASS']
    port = int(os.environ.get('SITEGROUND_FTP_PORT', '21'))

    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, password)
    ftp.cwd('brubru.beresol.eu/public_html/legislacio-ue-catala')
    return ftp


def deploy_with_verification(ftp, celex: str, max_retries: int = 3) -> bool:
    """Deploy a single CELEX with verification and retry. Returns True if confirmed on server."""
    local_file = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    if not os.path.isfile(local_file):
        print(f'    [FTP ERROR] No local file for {celex}')
        return False

    local_size = os.path.getsize(local_file)

    for attempt in range(max_retries):
        try:
            # Create dir if needed
            remote_dirs = set(ftp.nlst())
            if celex not in remote_dirs:
                try:
                    ftp.mkd(celex)
                except Exception:
                    pass  # Dir may already exist

            ftp.cwd(celex)
            with open(local_file, 'rb') as f:
                ftp.storbinary('STOR index.html', f)

            # Verify: check remote size
            remote_size = ftp.size('index.html')
            ftp.cwd('..')

            if remote_size == local_size:
                return True
            else:
                print(f'    [FTP WARN] Size mismatch for {celex} (local={local_size}, remote={remote_size}), retry {attempt+1}')
        except Exception as e:
            print(f'    [FTP RETRY {attempt+1}/{max_retries}] {celex}: {e}')
            try:
                ftp.cwd('/brubru.beresol.eu/public_html/legislacio-ue-catala')
            except Exception:
                # Connection lost -- caller must reconnect
                raise

            import time
            time.sleep(1)

    print(f'    [FTP FAILED] {celex} after {max_retries} attempts')
    return False


def main():
    parser = argparse.ArgumentParser(description='Batch Catalan Translation Pipeline')
    parser.add_argument('--count', type=int, default=10, help='Number of acts to translate (default: 10)')
    parser.add_argument('--min-size', type=int, default=0, help='Minimum file size in KB')
    parser.add_argument('--max-size', type=int, default=999999, help='Maximum file size in KB')
    parser.add_argument('--start-from', type=str, default='', help='Start from this CELEX')
    parser.add_argument('--dry-run', action='store_true', help='Show queue without translating')
    parser.add_argument('--no-deploy', action='store_true', help='Skip FTP deploy')
    args = parser.parse_args()

    if not os.path.exists(QUEUE_FILE):
        print(f'[ERROR] Queue file not found: {QUEUE_FILE}')
        print('Run the queue builder first (see catalan-implementation.md)')
        sys.exit(1)

    # Load queue
    with open(QUEUE_FILE, 'r') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    # Get already translated
    already = set()
    if os.path.isdir(TRANSLATIONS_DIR):
        already = {d for d in os.listdir(TRANSLATIONS_DIR)
                   if os.path.isdir(os.path.join(TRANSLATIONS_DIR, d)) and not d.endswith('-softcatala')}

    # Filter queue
    queue = []
    started = not args.start_from
    for line in lines:
        parts = line.split('|')
        if len(parts) < 3:
            continue
        xml_path, celex, size_kb = parts[0], parts[1], int(parts[2])

        if args.start_from and celex == args.start_from:
            started = True
        if not started:
            continue

        if celex in already:
            continue
        if size_kb < args.min_size or size_kb > args.max_size:
            continue

        queue.append((xml_path, celex, size_kb))

    print(f'[INFO] Queue: {len(queue)} acts (filtered from {len(lines)} total, {len(already)} already done)')
    print(f'[INFO] Translating up to {args.count} acts, size {args.min_size}-{args.max_size}KB')
    print()

    if args.dry_run:
        for i, (path, celex, size_kb) in enumerate(queue[:args.count]):
            print(f'  [{i+1:>3}] {celex:16s} | {size_kb:>5}KB | {os.path.basename(path)}')
        print(f'\n[DRY RUN] Would translate {min(args.count, len(queue))} acts')
        return

    # Open persistent FTP connection for the whole batch
    ftp = None
    if not args.no_deploy:
        try:
            ftp = get_ftp_connection()
            print(f'[INFO] FTP connection opened')
        except Exception as e:
            print(f'[ERROR] FTP connection failed: {e}')
            sys.exit(1)

    # Translate
    translated = 0
    failed = 0
    deploy_failed = []
    start_time = time.time()

    for i, (xml_path, celex, size_kb) in enumerate(queue[:args.count]):
        print(f'\n{"="*60}')
        print(f'[{i+1}/{min(args.count, len(queue))}] {celex} ({size_kb}KB)')
        print(f'{"="*60}')

        # Translate (no deploy)
        success = translate_one(xml_path, celex)
        if not success:
            failed += 1
            continue

        # Audit (runs BEFORE deploy so fixes are uploaded)
        issues = audit_translation(celex)
        if issues:
            print(f'  [AUDIT] Issues found: {", ".join(issues)}')
            fixes = auto_fix(celex)
            if fixes:
                print(f'  [FIX] Applied {fixes} auto-fixes')
                issues = audit_translation(celex)
                if issues:
                    print(f'  [WARN] Remaining issues after fix: {", ".join(issues)}')

        # Deploy with verification (AFTER audit/fix)
        if ftp is not None:
            deploy_ok = False
            try:
                deploy_ok = deploy_with_verification(ftp, celex)
            except Exception as e:
                # Connection lost, reconnect and retry
                print(f'  [FTP RECONNECT] {e}')
                try:
                    ftp.quit()
                except Exception:
                    pass
                ftp = get_ftp_connection()
                try:
                    deploy_ok = deploy_with_verification(ftp, celex)
                except Exception as e2:
                    print(f'  [FTP FATAL] {celex}: {e2}')

            if not deploy_ok:
                deploy_failed.append(celex)
                print(f'  [DEPLOY FAILED] {celex} -- NOT proceeding to DB import')
                failed += 1
                continue
            else:
                print(f'  [DEPLOY] {celex} verified on SiteGround')

        # Get metadata from HTML
        html_path = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
        with open(html_path, 'r') as fh:
            content = fh.read()

        title_match = re.search(r'<title>(.*?)</title>', content)
        title_ca = title_match.group(1) if title_match else celex
        articles = len(re.findall(r'class="article-title"', content)) - 1
        recitals = len(re.findall(r'class="recital"', content))
        html_size = os.path.getsize(html_path)

        # Import to DB
        try:
            import_to_db(celex, title_ca, max(articles, 0), recitals, html_size, 'softcatala')
            print(f'  [DB] Imported {celex}')
        except Exception as e:
            print(f'  [DB ERROR] {e}')

        translated += 1
        elapsed = time.time() - start_time
        rate = elapsed / translated if translated else 0
        remaining = (min(args.count, len(queue)) - i - 1) * rate
        print(f'  [OK] {celex} | {articles} arts | {recitals} recs | {html_size//1024}KB | {rate:.0f}s/act | ~{remaining/60:.0f}min left')

    # Close FTP connection
    if ftp is not None:
        try:
            ftp.quit()
        except Exception:
            pass

    elapsed = time.time() - start_time
    print(f'\n{"="*60}')
    print(f'[DONE] Translated: {translated}, Failed: {failed}, Time: {elapsed/60:.1f}min')
    print(f'[STATS] Rate: {elapsed/max(translated,1):.0f}s/act')

    if deploy_failed:
        print(f'\n[WARN] {len(deploy_failed)} deploy failures: {deploy_failed[:10]}')
        sys.exit(1)


if __name__ == '__main__':
    main()
