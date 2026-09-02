"""Repair YouTube directory rows whose channel id collided with another account's.

Root cause (found 2 Sep 2026): `resolve_youtube_channel_id` used to accept ANY
`youtube.com/channel/UC...` link on the page as the account's own id, so 19 EU
handles resolved to the European Commission's channel and 8 EP liaison offices to
Parliament's. Every EC video was then stored 19 times, each row an "original"
statement by a different institution (is_repost=false).

What this does, per account in a collision group (same platform_account_id, >1 row):
  * raw-id duplicate of a verified handle row (handle == channel id, same entity):
      -> content_fetch_enabled=false, extra.duplicate_of=<verified row id>
  * handle/user/c URL: re-resolve with the fixed, handle-verifying resolver
      -> same id: keep (legitimately shared channel)
      -> different id: set it
      -> None: platform_account_id=NULL, content_fetch_enabled=false,
               extra.resolver_cleared={date, old_id, reason}
  * every post fetched under a cleared/changed id is marked is_repost=true with
    original_author=<name of the channel it really came from>. Nothing is deleted.

Dry-run by default; --apply writes. Prints counts of PERSISTED changes.
"""
import argparse, json, re, sys, time, urllib.request
from datetime import date
sys.path.insert(0, ".")
from sqlalchemy import text
from core.database import SessionLocal
from services.social.post_fetcher import resolve_youtube_channel_id, _BROWSER_UA

def channel_name(cid):
    try:
        req = urllib.request.Request(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                                     headers={"User-Agent": _BROWSER_UA})
        xml = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        m = re.search(r"<name>([^<]*)</name>", xml)
        return m.group(1) if m else cid
    except Exception:
        return cid

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--pace", type=float, default=1.0)
    ap.add_argument("--all", action="store_true",
                    help="verify EVERY fetch-enabled youtube row, not only collision groups. "
                         "A singleton can be wrong too: European Commission in Poland sat alone "
                         "on Parliament-in-Poland's channel id and only surfaced once the "
                         "Parliament row was corrected (2 Sep 2026).")
    a = ap.parse_args()
    db = SessionLocal()
    if a.all:
        groups = db.execute(text("""
            SELECT DISTINCT platform_account_id FROM social_accounts
            WHERE platform='youtube' AND platform_account_id IS NOT NULL AND content_fetch_enabled""")).scalars().all()
    else:
        groups = db.execute(text("""
            SELECT platform_account_id FROM social_accounts
            WHERE platform='youtube' AND platform_account_id IS NOT NULL
            GROUP BY 1 HAVING count(*)>1""")).scalars().all()
    rows = db.execute(text("""
        SELECT id, handle, entity_name, entity_type, platform_account_id, account_url, verified, extra
        FROM social_accounts WHERE platform='youtube' AND platform_account_id = ANY(:g)
        ORDER BY platform_account_id, verified DESC, id"""), {"g": groups}).mappings().all()
    print(f"collision groups: {len(groups)}  rows: {len(rows)}  mode: {'APPLY' if a.apply else 'DRY-RUN'}")
    names = {}
    stats = {"kept": 0, "dup_disabled": 0, "reassigned": 0, "cleared": 0, "posts_marked": 0}
    by_group = {}
    for r in rows:
        by_group.setdefault(r["platform_account_id"], []).append(r)
    today = date.today().isoformat()
    for cid, members in by_group.items():
        names[cid] = channel_name(cid)
        verified_handle_rows = [m for m in members if m["handle"] != cid]
        for m in members:
            is_raw_id_row = (m["handle"] == cid) or ("/channel/" in (m["account_url"] or ""))
            if is_raw_id_row:
                twin = next((v for v in verified_handle_rows if v["entity_name"].split()[0].lower() == m["entity_name"].split()[0].lower()), None)
                if twin:
                    stats["dup_disabled"] += 1
                    print(f"  DUP   {m['id']:>6} {m['entity_name'][:40]:40} raw-id twin of {twin['id']} -> fetch off")
                    if a.apply:
                        extra = dict(m["extra"] or {}); extra["duplicate_of"] = twin["id"]; extra["duplicate_marked"] = today
                        db.execute(text("UPDATE social_accounts SET content_fetch_enabled=false, extra=:e WHERE id=:i"),
                                   {"e": json.dumps(extra), "i": m["id"]})
                else:
                    stats["kept"] += 1
                    print(f"  KEEP  {m['id']:>6} {m['entity_name'][:40]:40} raw /channel/ url, no twin")
                continue
            time.sleep(a.pace)
            new = resolve_youtube_channel_id(m["account_url"])
            if new == cid:
                stats["kept"] += 1
                print(f"  KEEP  {m['id']:>6} {m['entity_name'][:40]:40} {m['handle']:28} verified -> {cid}")
                continue
            posts = db.execute(text("SELECT count(*) FROM social_posts WHERE account_id=:i AND NOT is_repost"), {"i": m["id"]}).scalar()
            if new:
                stats["reassigned"] += 1
                print(f"  MOVE  {m['id']:>6} {m['entity_name'][:40]:40} {m['handle']:28} {cid} -> {new}  ({posts} posts to mark)")
                if a.apply:
                    db.execute(text("UPDATE social_accounts SET platform_account_id=:c WHERE id=:i"), {"c": new, "i": m["id"]})
            else:
                stats["cleared"] += 1
                print(f"  CLEAR {m['id']:>6} {m['entity_name'][:40]:40} {m['handle']:28} {cid} -> NULL, fetch off  ({posts} posts to mark)")
                if a.apply:
                    extra = dict(m["extra"] or {})
                    extra["resolver_cleared"] = {"date": today, "old_id": cid, "reason": "collision; handle did not verify against channel"}
                    db.execute(text("UPDATE social_accounts SET platform_account_id=NULL, content_fetch_enabled=false, extra=:e WHERE id=:i"),
                               {"e": json.dumps(extra), "i": m["id"]})
            stats["posts_marked"] += posts
            if a.apply:
                db.execute(text("""UPDATE social_posts SET is_repost=true, original_author=:n
                                   WHERE account_id=:i AND platform='youtube' AND NOT is_repost"""),
                           {"n": names[cid], "i": m["id"]})
    if a.all:
        # Second pass: rows an earlier, stricter run cleared. If they resolve now,
        # restore them -- a cleared row is a coverage hole, not a safe default.
        cleared = db.execute(text("""
            SELECT id, handle, entity_name, account_url, extra FROM social_accounts
            WHERE platform='youtube' AND platform_account_id IS NULL AND extra ? 'resolver_cleared'
            ORDER BY id""")).mappings().all()
        print(f"\ncleared rows to revisit: {len(cleared)}")
        stats["restored"] = 0
        for m in cleared:
            time.sleep(a.pace)
            new = resolve_youtube_channel_id(m["account_url"])
            if not new:
                print(f"  STILL  {m['id']:>6} {m['entity_name'][:40]:40} {m['handle']:28} unresolvable")
                continue
            stats["restored"] += 1
            print(f"  RESTORE{m['id']:>6} {m['entity_name'][:40]:40} {m['handle']:28} -> {new}  ({channel_name(new)})")
            if a.apply:
                extra = dict(m["extra"] or {}); extra["resolver_restored"] = {"date": today, "id": new}; extra.pop("resolver_cleared", None)
                db.execute(text("UPDATE social_accounts SET platform_account_id=:c, content_fetch_enabled=true, extra=:e WHERE id=:i"),
                           {"c": new, "e": json.dumps(extra), "i": m["id"]})
    if a.apply:
        db.commit()
        persisted = db.execute(text("SELECT count(*) FROM social_posts WHERE platform='youtube' AND is_repost AND original_author = ANY(:n)"), {"n": list(names.values())}).scalar()
        print(f"PERSISTED: youtube posts now is_repost with a channel original_author: {persisted}")
    print("STATS:", stats)
    print("channel names:", names)
    db.close()

if __name__ == "__main__":
    main()
