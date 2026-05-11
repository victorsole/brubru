#!/usr/bin/env python3.12
"""
Reconcile Catalan translations: disk -> DB -> SiteGround FTP.

Three reconciliation modes (run all of them in /catalan and /morning):

1. Disk -> DB.  Find CELEX dirs on disk missing from `catalan_translations`,
   extract metadata + classify + insert.

2. DB -> FTP (--deploy-pending).  Walk DB rows where `deployed_at IS NULL`,
   FTP-upload, mark `deployed_at` on success.

3. Combined (--deploy).  Insert + deploy any disk-only CELEX in one pass.

Usage:
    cd backend
    python3.12 scripts/sync_catalan_disk_to_db.py                  # DB-only sync
    python3.12 scripts/sync_catalan_disk_to_db.py --deploy-pending # FTP rows where deployed_at is NULL
    python3.12 scripts/sync_catalan_disk_to_db.py --deploy         # both: insert + deploy disk-only
    python3.12 scripts/sync_catalan_disk_to_db.py --dry-run        # report only
"""

import argparse
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.catalan_translation import CatalanTranslation
from scripts.batch_catalan_translate import (
    classify_act,
    detect_doc_type,
    detect_subcategory,
)

TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'legislacio-ue-catala'
)


def extract_html_meta(html_path: str) -> dict:
    with open(html_path, 'r') as fh:
        content = fh.read()
    title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
    title_ca = (
        title_match.group(1).replace(' | Brubru', '').strip()
        if title_match else os.path.basename(os.path.dirname(html_path))
    )
    articles = max(0, len(re.findall(r'class="article-title"', content)) - 1)
    recitals = len(re.findall(r'class="recital"', content))
    return {
        'title_ca': title_ca,
        'articles': articles,
        'recitals': recitals,
        'size': os.path.getsize(html_path),
    }


def get_ftp():
    import ftplib
    from dotenv import load_dotenv
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
    )
    load_dotenv(env_path)
    host = os.environ['SITEGROUND_FTP_HOST']
    user = os.environ['SITEGROUND_FTP_USER']
    pw = os.environ['SITEGROUND_FTP_PASS']
    port = int(os.environ.get('SITEGROUND_FTP_PORT', '21'))
    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, pw)
    ftp.cwd('brubru.beresol.eu/public_html/legislacio-ue-catala')
    return ftp


def deploy_one(ftp, celex: str, local_size: int) -> bool:
    """Upload disk index.html for celex if missing/smaller on server. Returns True if confirmed."""
    local_file = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    if not os.path.isfile(local_file):
        return False

    cwd_root = '/brubru.beresol.eu/public_html/legislacio-ue-catala'
    try:
        ftp.cwd(cwd_root)
        try:
            ftp.cwd(celex)
        except Exception:
            try:
                ftp.mkd(celex)
            except Exception:
                pass
            ftp.cwd(celex)

        # Quick check: size on server
        try:
            server_size = ftp.size('index.html')
        except Exception:
            server_size = -1

        if server_size == local_size:
            return True

        with open(local_file, 'rb') as f:
            ftp.storbinary('STOR index.html', f)

        try:
            new_size = ftp.size('index.html')
        except Exception:
            new_size = -1
        return new_size == local_size
    except Exception as e:
        print(f'    [FTP ERROR] {celex}: {e}')
        return False


def deploy_pending(args):
    """Walk DB rows where deployed_at IS NULL, FTP-upload, mark deployed_at."""
    db = SessionLocal()
    try:
        q = db.query(CatalanTranslation).filter(CatalanTranslation.deployed_at.is_(None))
        if args.celex:
            q = q.filter(CatalanTranslation.celex == args.celex)
        q = q.order_by(CatalanTranslation.celex)
        if args.limit:
            q = q.limit(args.limit)
        rows = q.all()

        print(f'[INFO] Pending deploy: {len(rows)} rows (deployed_at IS NULL)')

        if args.dry_run or not rows:
            for row in rows[:30]:
                print(f'  [DRY] {row.celex}')
            if len(rows) > 30:
                print(f'  ... ({len(rows) - 30} more)')
            return

        ftp = get_ftp()
        print('[INFO] FTP connection opened')

        deployed = 0
        failed = 0
        for i, row in enumerate(rows, 1):
            local_file = os.path.join(TRANSLATIONS_DIR, row.celex, 'index.html')
            if not os.path.isfile(local_file):
                print(f'  [SKIP] {row.celex}: no local file')
                failed += 1
                continue
            local_size = os.path.getsize(local_file)
            ok = deploy_one(ftp, row.celex, local_size)
            if ok:
                row.deployed_at = datetime.utcnow()
                deployed += 1
            else:
                failed += 1
            if i % 25 == 0:
                db.commit()
                print(f'  [PROGRESS] {i}/{len(rows)} (deployed={deployed}, failed={failed})')
        db.commit()

        print()
        print(f'[OK] Deployed {deployed} files (failed: {failed})')

        try:
            ftp.quit()
        except Exception:
            pass
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Sync Catalan translations: disk -> DB -> FTP')
    parser.add_argument('--dry-run', action='store_true', help='Report gaps only, do nothing')
    parser.add_argument('--deploy', action='store_true', help='Also FTP-upload disk-only files when inserting')
    parser.add_argument('--deploy-pending', action='store_true',
                        help='FTP-upload all DB rows where deployed_at IS NULL, then mark deployed_at')
    parser.add_argument('--limit', type=int, default=0, help='Cap number to process (0 = all)')
    parser.add_argument('--celex', type=str, default='', help='Sync only this CELEX')
    args = parser.parse_args()

    if args.deploy_pending:
        deploy_pending(args)
        return

    if not os.path.isdir(TRANSLATIONS_DIR):
        print(f'[ERROR] Translations dir not found: {TRANSLATIONS_DIR}')
        sys.exit(1)

    # Scan disk
    disk_celex = []
    for d in sorted(os.listdir(TRANSLATIONS_DIR)):
        if d.endswith('-softcatala'):
            continue
        if args.celex and d != args.celex:
            continue
        full = os.path.join(TRANSLATIONS_DIR, d)
        if not os.path.isdir(full):
            continue
        if not os.path.isfile(os.path.join(full, 'index.html')):
            continue
        disk_celex.append(d)

    print(f'[INFO] Disk: {len(disk_celex)} translation directories')

    db = SessionLocal()
    try:
        existing = {row.celex for row in db.query(CatalanTranslation.celex).all()}
        print(f'[INFO] DB:   {len(existing)} rows')

        missing = [c for c in disk_celex if c not in existing]
        print(f'[INFO] Gap:  {len(missing)} disk-only CELEX')

        if args.limit:
            missing = missing[: args.limit]

        if args.dry_run:
            for c in missing[:30]:
                print(f'  [DRY] {c}')
            if len(missing) > 30:
                print(f'  ... ({len(missing) - 30} more)')
            return

        ftp = None
        if args.deploy:
            try:
                ftp = get_ftp()
                print('[INFO] FTP connection opened')
            except Exception as e:
                print(f'[ERROR] FTP failed: {e}')
                sys.exit(1)

        inserted = 0
        deployed = 0
        deploy_failed = 0
        parse_failed = 0

        for i, celex in enumerate(missing, 1):
            html_path = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
            try:
                meta = extract_html_meta(html_path)
            except Exception as e:
                print(f'  [SKIP] {celex}: parse error {e}')
                parse_failed += 1
                continue

            cat_ca, cat_en = classify_act(meta['title_ca'])
            doc_type = detect_doc_type(meta['title_ca'])
            subcat = detect_subcategory(meta['title_ca'])

            row = CatalanTranslation(
                celex=celex,
                title_en=meta['title_ca'],
                title_ca=meta['title_ca'],
                short_name=celex,
                doc_type=doc_type,
                category=cat_ca,
                category_en=cat_en,
                subcategory=subcat,
                articles_count=meta['articles'],
                recitals_count=meta['recitals'],
                html_size_bytes=meta['size'],
                engine='softcatala',
                source_format='formex',
                file_type='main',
                siteground_url=f'https://brubru.beresol.eu/legislacio-ue-catala/{celex}/',
            )
            db.add(row)
            inserted += 1

            if ftp is not None:
                ok = deploy_one(ftp, celex, meta['size'])
                if ok:
                    row.deployed_at = datetime.utcnow()
                    deployed += 1
                else:
                    deploy_failed += 1
                    print(f'  [WARN] Deploy failed for {celex}')

            if i % 50 == 0:
                db.commit()
                print(f'  [PROGRESS] {i}/{len(missing)} (inserted={inserted}, deployed={deployed})')

        db.commit()

        print()
        print(f'[OK] Inserted {inserted} rows')
        if args.deploy:
            print(f'[OK] Deployed {deployed} files (failed: {deploy_failed})')
        if parse_failed:
            print(f'[WARN] Parse failures: {parse_failed}')

        # Final reconciliation report
        cur_count = db.query(CatalanTranslation).count()
        print(f'[STATE] DB now: {cur_count} rows | Disk: {len(disk_celex)} dirs')

        if ftp is not None:
            try:
                ftp.quit()
            except Exception:
                pass
    finally:
        db.close()


if __name__ == '__main__':
    main()
