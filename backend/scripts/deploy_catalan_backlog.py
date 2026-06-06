#!/usr/bin/env python3.12
"""One-off: deploy the Catalan translations that were produced with --no-deploy
(deployed_at IS NULL) to SiteGround, then stamp deployed_at in the DB.

Created 06 Jun 2026 after SiteGround FTP degraded mid-run and batches #62+ were
translated with --no-deploy. Resilient: per-act reconnect + retry, continues on
failure, only stamps deployed_at on a verified upload (remote size == local size).
Softcatala-only pipeline; this script does NOT translate, it only deploys.
"""
import os
import sys
import time
import ftplib
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT, '.env'))
TRANSLATIONS_DIR = os.path.join(ROOT, 'data', 'legislacio-ue-catala')
REMOTE_BASE = 'brubru.beresol.eu/public_html/legislacio-ue-catala'


def connect():
    ftp = ftplib.FTP()
    ftp.connect(os.environ['SITEGROUND_FTP_HOST'],
                int(os.environ.get('SITEGROUND_FTP_PORT', '21')), timeout=60)
    ftp.login(os.environ['SITEGROUND_FTP_USER'], os.environ['SITEGROUND_FTP_PASS'])
    ftp.cwd('/' + REMOTE_BASE)
    return ftp


def deploy_one(ftp, celex, local_file):
    """Returns (ok, ftp). Reconnects ftp on socket error.

    Dir handling does NOT use nlst() -- the server caps listings at 10k entries,
    so a missing-from-listing dir may still exist. Instead: try to cwd into the
    act dir; only mkd if that fails; tolerate 'File exists' on mkd.
    """
    for attempt in range(3):
        try:
            target = '/' + REMOTE_BASE + '/' + celex
            try:
                ftp.cwd(target)
            except ftplib.error_perm:
                ftp.cwd('/' + REMOTE_BASE)
                try:
                    ftp.mkd(celex)
                except ftplib.error_perm as e:
                    if '550' not in str(e):  # anything but already-exists is real
                        raise
                ftp.cwd(target)
            with open(local_file, 'rb') as fh:
                ftp.storbinary('STOR index.html', fh)
            remote = ftp.size('index.html')
            local = os.path.getsize(local_file)
            ftp.cwd('/' + REMOTE_BASE)
            if remote == local:
                return True, ftp
            print(f"  [SIZE MISMATCH] {celex} remote={remote} local={local}")
        except (ftplib.error_temp, OSError, EOFError) as e:
            print(f"  [RETRY {attempt+1}/3] {celex}: {type(e).__name__}: {e}")
            try:
                ftp.close()
            except Exception:
                pass
            time.sleep(2)
            try:
                ftp = connect()
            except Exception as e2:
                print(f"  [RECONNECT FAIL] {e2}")
                time.sleep(5)
    return False, ftp


def main():
    e = create_engine(os.environ['DATABASE_URL'])
    with e.connect() as c:
        rows = c.execute(text(
            "select celex from catalan_translations "
            "where deployed_at is null order by celex")).fetchall()
    pending = [r[0] for r in rows]
    print(f"[INFO] {len(pending)} acts pending deploy")
    if not pending:
        return

    ftp = connect()
    ok = fail = skip = 0
    t0 = time.time()
    for i, celex in enumerate(pending, 1):
        lf = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
        if not os.path.exists(lf):
            print(f"[{i}/{len(pending)}] {celex} SKIP (no local file)")
            skip += 1
            continue
        good, ftp = deploy_one(ftp, celex, lf)
        if good:
            with e.begin() as c:
                c.execute(text(
                    "update catalan_translations set deployed_at=:now, updated_at=now() "
                    "where celex=:celex and deployed_at is null"),
                    {"now": datetime.utcnow(), "celex": celex})
            ok += 1
            if i % 20 == 0 or i == len(pending):
                rate = (time.time() - t0) / i
                print(f"[{i}/{len(pending)}] {celex} OK | {rate:.1f}s/act avg")
        else:
            print(f"[{i}/{len(pending)}] {celex} FAIL")
            fail += 1
    try:
        ftp.quit()
    except Exception:
        pass
    print(f"[DONE] deployed={ok} failed={fail} skipped={skip} in {(time.time()-t0)/60:.1f}min")


if __name__ == '__main__':
    main()
