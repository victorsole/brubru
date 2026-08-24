#!/usr/bin/env python3.12
"""
Backfill Brussels-lobby news: language detection, foreign->6 translation, og:image.

Runs LOCALLY against the prod DB (like the Catalan pipeline) — free OSS, no HF
credits. ~16% of items are non-canonical-language (de/sv/no/fi/da/pt/tr/uk/cs/...);
for those we translate title+summary into all 6 Brubru languages up front with
facebook/m2m100_418M (lighter/faster CPU MT). Items already in en/es/ca/fr/it/nl
are left as-is. Images are best-effort og:image, fetched in the same pass.

Resumable: detection skips rows with detected_lang set; translation skips
(item,lang) pairs already cached; image fetch skips rows with image_url set
(empty string = "checked, none found").

Usage (from backend/):
    python3.12 scripts/backfill_lobby_translations.py --limit 200            # detect+translate
    python3.12 scripts/backfill_lobby_translations.py --limit 200 --images   # + og:image
    python3.12 scripts/backfill_lobby_translations.py --images-only --limit 500
"""
from __future__ import annotations

import argparse
import re
import sys
import time

import psycopg2
import psycopg2.extras

SIX = ["en", "es", "ca", "fr", "it", "nl"]
SIX_SET = set(SIX)
ENGINE = "m2m100_418M"

# langdetect codes -> m2m100 source codes (only the divergent ones).
_SRC_MAP = {"zh-cn": "zh", "zh-tw": "zh", "he": "iw"}

_OG = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)', re.I)
_TW = re.compile(r'<meta[^>]+(?:property|name)=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', re.I)


def _db():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    url = get_database_url()
    c = psycopg2.connect(url, connect_timeout=15, keepalives=1,
                         keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    c.autocommit = False
    return c


def _detector():
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0

    def detect_lang(text: str) -> str:
        try:
            return detect(text)
        except Exception:
            return "und"
    return detect_lang


def _translator():
    """Load m2m100_418M once; return translate(text, src, tgt)."""
    print("[load] facebook/m2m100_418M (first run downloads ~1.9GB) ...", flush=True)
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
    tok = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
    model.eval()
    valid = set(tok.lang_code_to_id.keys())
    print(f"[load] ready ({len(valid)} languages)", flush=True)

    def translate(text: str, src: str, tgt: str) -> str:
        if not text or not text.strip():
            return text
        s = _SRC_MAP.get(src, src)
        if s not in valid:
            s = "en"
        tok.src_lang = s
        enc = tok(text[:1000], return_tensors="pt", truncation=True, max_length=400)
        gen = model.generate(**enc, forced_bos_token_id=tok.get_lang_id(tgt),
                             max_length=400, num_beams=1)
        return tok.batch_decode(gen, skip_special_tokens=True)[0].strip()
    return translate


def _fetch_undetected(batch: int):
    """Short read connection: pull the next chunk of undetected items."""
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, title, COALESCE(summary,'') AS summary
              FROM brussels_lobby_news_items
             WHERE title IS NOT NULL AND title NOT LIKE '/%%' AND length(title) >= 12
               AND detected_lang IS NULL
             ORDER BY published_at DESC NULLS LAST
             LIMIT %s
        """, (batch,))
        return cur.fetchall()
    finally:
        conn.close()


def _write_batch(writes):
    """Short write connection: persist a chunk's detection + translations."""
    conn = _db()
    try:
        cur = conn.cursor()
        for item_id, lang, trans_rows in writes:
            cur.execute("UPDATE brussels_lobby_news_items SET detected_lang=%s WHERE id=%s",
                        (lang, item_id))
            for tgt, t_title, t_sum in trans_rows:
                cur.execute("""
                    INSERT INTO brussels_lobby_news_translations
                        (news_item_id, lang, title, summary, engine)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (news_item_id, lang) DO UPDATE
                        SET title=EXCLUDED.title, summary=EXCLUDED.summary,
                            engine=EXCLUDED.engine, translated_at=now()
                """, (item_id, tgt, t_title, t_sum, ENGINE))
        conn.commit()
    finally:
        conn.close()


def run_translate(limit: int, batch: int):
    """Chunked: read -> translate IN MEMORY (no DB held) -> short write. Robust to
    Supabase closing long-lived connections during slow CPU translation."""
    detect_lang = _detector()
    translate = _translator()
    done = foreign = 0
    while done < limit:
        rows = _fetch_undetected(min(batch, limit - done))
        if not rows:
            break
        writes = []
        for r in rows:
            text = (r["title"] + " " + r["summary"]).strip()
            lang = detect_lang(text)
            trans_rows = []
            if lang not in SIX_SET and lang != "und":
                foreign += 1
                for tgt in SIX:
                    try:
                        t_title = translate(r["title"], lang, tgt)
                        t_sum = translate(r["summary"], lang, tgt) if r["summary"] else None
                        trans_rows.append((tgt, t_title, t_sum))
                    except Exception as e:
                        print(f"  [warn] {r['id']} {lang}->{tgt}: {str(e)[:80]}", flush=True)
            writes.append((r["id"], lang, trans_rows))
        # Retry the write once if the pooler dropped us between batches.
        for attempt in (1, 2):
            try:
                _write_batch(writes)
                break
            except psycopg2.OperationalError as e:
                if attempt == 2:
                    raise
                print(f"  [retry] write batch after: {str(e)[:60]}", flush=True)
                time.sleep(3)
        done += len(rows)
        print(f"  .. {done} processed ({foreign} foreign translated)", flush=True)
    print(f"[translate] done: {done} processed, {foreign} foreign -> {foreign*6} translation rows", flush=True)


def _fetch_imageless(batch: int):
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, item_url FROM brussels_lobby_news_items
             WHERE item_url ~ '^https?://' AND image_url IS NULL
               AND title IS NOT NULL AND length(title) >= 12
             ORDER BY published_at DESC NULLS LAST
             LIMIT %s
        """, (batch,))
        return cur.fetchall()
    finally:
        conn.close()


def _write_images(pairs):
    conn = _db()
    try:
        cur = conn.cursor()
        for item_id, img in pairs:
            cur.execute("UPDATE brussels_lobby_news_items SET image_url=%s WHERE id=%s",
                        (img, item_id))
        conn.commit()
    finally:
        conn.close()


def run_images(limit: int, batch: int):
    """Chunked: read -> HTTP-probe og:image IN MEMORY (no DB held) -> short write."""
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)"}
    done = found = 0
    with httpx.Client(timeout=12, follow_redirects=True, headers=headers) as client:
        while done < limit:
            rows = _fetch_imageless(min(batch, limit - done))
            if not rows:
                break
            pairs = []
            for r in rows:
                img = ""  # empty string = "checked, none found" (skipped next run)
                try:
                    resp = client.get(r["item_url"])
                    if resp.status_code == 200 and resp.text:
                        m = _OG.search(resp.text) or _TW.search(resp.text)
                        if m:
                            img = m.group(1).strip()[:1000]
                            found += 1
                except Exception:
                    img = ""
                pairs.append((r["id"], img))
                time.sleep(0.15)
            for attempt in (1, 2):
                try:
                    _write_images(pairs)
                    break
                except psycopg2.OperationalError as e:
                    if attempt == 2:
                        raise
                    print(f"  [retry] image write after: {str(e)[:60]}", flush=True)
                    time.sleep(3)
            done += len(rows)
            print(f"  .. {done} probed ({found} with image)", flush=True)
    print(f"[images] done: {done} probed, {found} got an image", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--images", action="store_true", help="also probe og:image after translating")
    ap.add_argument("--images-only", action="store_true", help="only probe og:image")
    args = ap.parse_args()

    if args.images_only:
        run_images(args.limit, args.batch)
        return
    run_translate(args.limit, args.batch)
    if args.images:
        run_images(args.limit, args.batch)


if __name__ == "__main__":
    sys.exit(main())
