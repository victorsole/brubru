"""Resolve the video stream for committee meetings whose page link we hold.

Why this exists (28 Sep 2026)
-----------------------------
`committee_meeting_transcripts` had 256 rows in PENDING, none with a `video_url`, and
nothing had been transcribed since 8 June while the `transcripts` job recorded success
217 times. The enrichment step could not resolve a page into a video:

  * plain HTTP to multimedia.europarl.europa.eu answers 301 then 202 (the EP WAF);
  * a HEADLESS browser is fingerprinted and served a 3,630-character decoy titled
    "Tags - Multimedia Centre", with or without anti-automation flags;
  * Scrape.do, the documented escalation, is out of quota (0 of 1,000 this month);
  * EP Open Data has no committee meetings at all: /meetings carries MTG-PL (plenary)
    only, checked across 200 records, and /speeches is plenary too.

A HEADED browser gets the real page (77,433 characters), and the player then requests an
HLS archive playlist from live.media.eup.glcloud.eu. That playlist IS fetchable over plain
HTTP with no browser, so only this one step needs a display: everything downstream of a
stored video_url works anywhere.

EP has also moved format. Rows completed before June hold an mp4 on
vod.prd.commavservices.eu; new meetings are HLS, so whatever consumes video_url must
handle a .m3u8 (ffmpeg reads it directly).

Railway note: the container has no display, so this is a LOCAL job. Running it under
xvfb-run would let it move into the tier later.

Run:
    python3.12 scripts/resolve_committee_video_urls.py --limit 3
    python3.12 scripts/resolve_committee_video_urls.py --apply --limit 50
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")


def _resolve(page, url: str, settle_ms: int) -> str | None:
    """Return the meeting's HLS archive playlist, or None."""
    found: list[str] = []

    def on_response(r):
        u = r.url
        # index-archive is the whole recording. The per-rendition playlists
        # (input/1/256/...) and the live index are not what we want to store.
        if "index-archive.m3u8" in u:
            found.append(u)

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(settle_ms)
    except Exception as exc:  # noqa: BLE001
        print(f"    navigation failed: {type(exc).__name__}", flush=True)
    finally:
        page.remove_listener("response", on_response)
    return found[0] if found else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=3, help="0 = every pending meeting")
    ap.add_argument("--settle-ms", type=int, default=11000,
                    help="How long to let the player start before giving up on it")
    ap.add_argument("--max-seconds", type=int, default=1800)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright is not installed: python -m playwright install chromium")
        return 1

    db = SessionLocal()
    started = time.time()
    resolved = no_stream = 0
    try:
        sql = ("SELECT id, committee_code, meeting_date, multimedia_url "
               "FROM committee_meeting_transcripts "
               "WHERE status = 'PENDING' AND video_url IS NULL "
               "  AND multimedia_url IS NOT NULL "
               "ORDER BY meeting_date DESC")
        if args.limit:
            sql += f" LIMIT {args.limit}"
        rows = db.execute(text(sql)).fetchall()
        due = db.execute(text(
            "SELECT count(*) FROM committee_meeting_transcripts "
            "WHERE status = 'PENDING' AND video_url IS NULL AND multimedia_url IS NOT NULL"
        )).scalar()
        print(f"[INFO] {len(rows)} of {due} pending meeting(s) this run (apply={args.apply})")
        if not rows:
            print("[INFO] nothing to resolve")
            return 0

        with sync_playwright() as p:
            # HEADED on purpose: headless is fingerprinted and served a decoy.
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context(locale="en-US", user_agent=_UA,
                                      viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            try:
                for i, row in enumerate(rows, 1):
                    if time.time() - started > args.max_seconds:
                        print(f"[INFO] budget reached after {i - 1} meeting(s)")
                        break
                    stream = _resolve(page, row.multimedia_url, args.settle_ms)
                    label = f"{row.committee_code} {row.meeting_date:%Y-%m-%d}"
                    if not stream:
                        no_stream += 1
                        print(f"  [{i:4}] {label}: no stream published yet", flush=True)
                        continue
                    resolved += 1
                    print(f"  [{i:4}] {label}: {stream[:96]}", flush=True)
                    if args.apply:
                        db.execute(text(
                            "UPDATE committee_meeting_transcripts SET video_url = :v "
                            "WHERE id = :id AND video_url IS NULL"),
                            {"v": stream, "id": row.id})
                        db.commit()
            finally:
                browser.close()

        print(f"[DONE] resolved={resolved}  no stream published={no_stream}"
              f"{'' if args.apply else '  (DRY-RUN)'}")
        # A meeting with no recording yet is a real answer, not a failure. Every single
        # one failing is not: that is the WAF serving a decoy again, or the player
        # changing, and it must not read as "these meetings have no video".
        if rows and resolved == 0:
            print("[ERROR] not one meeting resolved to a stream: the page is being "
                  "blocked or the player has changed, NOT proof that the videos are absent")
            return 1
        left = max(0, (due or 0) - resolved) if args.apply else 0
        if left:
            print(f"[SYNC_STATUS] degraded: {left} pending meeting(s) still unresolved")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
