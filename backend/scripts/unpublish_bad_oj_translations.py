#!/usr/bin/env python3.12
"""Remove Catalan act pages that do not actually contain the act.

INCIDENT, 10 September 2026
---------------------------
52 pages were generated for the day's OJ and 44 reached the live site. NONE of
them contained the act. 49 were the EUR-Lex website itself -- cookie notice,
language picker, "Inicia la sessio" -- translated into Catalan and published
under the banner "Aquesta traduccio ha estat preparada per Brubru". 3 were
correct-titled empty shells.

The pipeline said so at the time and was not believed: when Cellar missed, it
fell back to EUR-Lex HTML through the WAF, logged
`Article=False (WAF challenge or empty)`, and then printed `[OK] registered`.

The verification that cleared it was mine and it was wrong: file size and
character count, which a 15KB chrome page passes easily. Only reading the body
could have caught it.

WHAT THIS DOES
--------------
Deletes the local page, the remote page over FTP, and the catalan_translations
row, so `catalan_url` disappears from the My OJ card and the reader falls back to
the EUR-Lex link -- the same honest behaviour the C-series already has.

The content test is the same one that will gate registration from now on:
a real act page has no EUR-Lex furniture, at least 3 paragraphs over 200
characters, and more than 1500 characters of body text.
"""
import argparse
import html
import io
import json
import pathlib
import re
import subprocess
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))
OUT_ROOT = _REPO_ROOT / "data" / "legislacio-ue-catala"

CHROME = ["Inicia la sessió", "Les meves cerques recents", "EUR-Lex home",
          "cookies al nostre lloc web", "característiques experimentals"]


def page_has_act_text(path: pathlib.Path) -> tuple[bool, str]:
    """True when the file really holds the act. Reads the BODY, never the size."""
    try:
        t = io.open(path, encoding="utf-8", errors="ignore").read()
    except OSError as exc:
        return False, f"unreadable: {exc}"
    paras = re.findall(r'<p class="article-text">(.*?)</p>', t, re.S)
    clean = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in paras]
    joined = " ".join(clean)
    if any(m in joined for m in CHROME):
        return False, "EUR-Lex site chrome"
    substantive = [c for c in clean if len(c) > 200]
    chars = sum(len(c) for c in clean)
    if len(substantive) < 3 or chars <= 1500:
        return False, f"thin body ({chars} chars, {len(substantive)} substantive paragraphs)"
    return True, f"ok ({chars} chars, {len(substantive)} substantive paragraphs)"


def _ftp_delete(celexes: list[str]) -> int:
    env = _REPO_ROOT / ".env"
    conf = dict(
        l.split("=", 1) for l in env.read_text().splitlines()
        if l.startswith(("SITEGROUND_FTP_HOST=", "SITEGROUND_FTP_USER=", "SITEGROUND_FTP_PASS="))
    )
    h, u, p = (conf["SITEGROUND_FTP_HOST"], conf["SITEGROUND_FTP_USER"], conf["SITEGROUND_FTP_PASS"])
    cmds = ["set ftp:ssl-allow true", "set ssl:verify-certificate no", f"open -u '{u}','{p}' '{h}'"]
    for c in celexes:
        cmds.append(f"rm -f /brubru.beresol.eu/public_html/legislacio-ue-catala/{c}/index.html")
        cmds.append(f"rmdir /brubru.beresol.eu/public_html/legislacio-ue-catala/{c}")
    r = subprocess.run(["lftp", "-c", "; ".join(cmds)], capture_output=True, text=True, timeout=1800)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-10 11:00")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--skip-ftp", action="store_true")
    args = ap.parse_args()

    found = subprocess.run(
        ["find", str(OUT_ROOT), "-name", "index.html", "-newermt", args.since],
        capture_output=True, text=True).stdout.split()
    bad = []
    for f in found:
        path = pathlib.Path(f)
        ok, why = page_has_act_text(path)
        if not ok:
            bad.append((path.parent.name, why))

    print(f"[INFO] pages written since {args.since}: {len(found)}")
    print(f"[INFO] failing the content check:        {len(bad)}")
    for c, why in bad[:6]:
        print(f"         {c}: {why}")
    if len(bad) > 6:
        print(f"         ... and {len(bad)-6} more")
    if not bad:
        print("[OK] nothing to remove")
        return 0
    if not args.apply:
        print("\n[DRY RUN] nothing deleted")
        return 0

    celexes = [c for c, _ in bad]

    # 1. remote first: a live page serving chrome is the user-facing harm
    if not args.skip_ftp:
        rc = _ftp_delete(celexes)
        print(f"[INFO] FTP delete rc={rc}")

    # 2. database row, so catalan_url stops being served
    from core.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        n = db.execute(text("DELETE FROM catalan_translations WHERE celex = ANY(:c)"),
                       {"c": celexes}).rowcount
        db.commit()
        print(f"[INFO] catalan_translations rows deleted: {n}")
    finally:
        db.close()

    # 3. local files
    removed = 0
    for c in celexes:
        d = OUT_ROOT / c
        for f in d.glob("*"):
            f.unlink()
        if d.exists():
            d.rmdir()
            removed += 1
    print(f"[INFO] local directories removed: {removed}")

    # Count PERSISTED state, never attempts.
    db = SessionLocal()
    try:
        left = db.execute(text("SELECT count(*) FROM catalan_translations WHERE celex = ANY(:c)"),
                          {"c": celexes}).scalar()
    finally:
        db.close()
    still = [c for c in celexes if (OUT_ROOT / c / "index.html").exists()]
    print(f"\n[VERIFY] rows remaining: {left}   files remaining: {len(still)}")
    return 0 if (left == 0 and not still) else 1


if __name__ == "__main__":
    raise SystemExit(main())
