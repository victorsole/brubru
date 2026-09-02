"""Phase 4.2 — open-tier social post fetcher.

Fetches recent posts from mapped accounts via public, keyless, ToS-clean APIs:
  bluesky  -> public AppView XRPC app.bsky.feed.getAuthorFeed
  mastodon -> instance REST /api/v1/accounts/lookup + /statuses
  youtube  -> channel RSS (videos.xml) — only /channel/<UC..> urls
Hard platforms (x/instagram/linkedin/tiktok/threads) are NEVER fetched (D1). Only accounts
with content_fetch_enabled=true are processed. Idempotent UPSERT on (account_id, platform_post_id).
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.social_post import SocialPost

logger = logging.getLogger("social-post-fetcher")
_UA = "BrubruBot/1.0 (https://brubru.beresol.eu; hello@beresol.eu)"
# Browser-ish UA for X's public syndication embed endpoint.
_BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")
OPEN_TIER = ("bluesky", "mastodon", "youtube")
# X added via its PUBLIC syndication/embed endpoint (keyless, login-free, the same feed
# Twitter serves for embedded timelines). Instagram/LinkedIn/TikTok have no equivalent free
# post feed -> content still deferred there (mapping only).
FETCHABLE = ("bluesky", "mastodon", "youtube", "x")
_REFRESH = ["post_url", "content", "lang", "posted_at", "like_count", "repost_count",
            "is_repost", "original_author",
            "reply_count", "view_count", "media", "extra"]


# X syndication prefixes an amplified post with "RT @handle:". It is the only
# repost marker that endpoint gives us, and it is reliable.
_RT_PREFIX_RE = re.compile(r"^RT @([A-Za-z0-9_]{1,15})\s*:")


def _get(url, parse="json", tries=3, timeout=25):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": _UA}), timeout=timeout) as r:
                raw = r.read().decode()
                return json.loads(raw) if parse == "json" else raw
        except Exception:
            time.sleep(1.5)
    return None


def _strip(s):
    return unescape(re.sub("<[^>]+>", " ", s or "")).strip()


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _dt_twitter(s):
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        return None


def fetch_x(handle, n=20):
    """Recent tweets via the PUBLIC syndication embed endpoint (keyless). Parses __NEXT_DATA__."""
    handle = handle.lstrip("@")
    try:
        req = urllib.request.Request(
            f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{urllib.parse.quote(handle)}",
            headers={"User-Agent": _BROWSER_UA})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    except Exception:
        return []
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return []
    tweets = []

    def walk(o):
        if isinstance(o, dict):
            if "full_text" in o and "id_str" in o:
                tweets.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    try:
        walk(json.loads(m.group(1)))
    except (ValueError, TypeError):
        return []
    out = []
    seen = set()
    for t in tweets[:n]:
        tid = t.get("id_str")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        _txt = t.get("full_text") or ""
        _rt = _RT_PREFIX_RE.match(_txt)
        out.append({"platform_post_id": tid, "content": _txt,
                    "post_url": f"https://x.com/{handle}/status/{tid}",
                    "posted_at": _dt_twitter(t.get("created_at")), "lang": t.get("lang"),
                    "like_count": t.get("favorite_count"), "repost_count": t.get("retweet_count"),
                    "reply_count": t.get("reply_count"), "view_count": None, "media": [], "extra": {},
                    "is_repost": bool(_rt), "original_author": _rt.group(1) if _rt else None})
    return out


def fetch_bluesky(handle, n=10):
    d = _get(f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={urllib.parse.quote(handle)}&limit={n}")
    out = []
    for it in (d.get("feed", []) if isinstance(d, dict) else []):
        p = it.get("post", {})
        rec = p.get("record", {})
        uri = p.get("uri", "")
        rkey = uri.split("/")[-1] if uri else None
        langs = rec.get("langs") or []
        # `reason` is present when this feed entry is an amplification. The real
        # author sits on the post, not on the feed we asked for -- without this,
        # a repost is stored as the account's own statement, which is how
        # Thomas Pellerin-Carlin came to "declare" for the French presidency.
        _reason = it.get("reason") or {}
        _author = (p.get("author") or {}).get("handle")
        _is_rt = bool(_reason) or (bool(_author) and _author.lower() != handle.lower())
        out.append({"platform_post_id": uri or rkey, "content": rec.get("text"),
                    "post_url": (f"https://bsky.app/profile/{_author or handle}/post/{rkey}"
                                 if rkey else None),
                    "posted_at": _dt(rec.get("createdAt")), "lang": langs[0] if langs else None,
                    "like_count": p.get("likeCount"), "repost_count": p.get("repostCount"),
                    "reply_count": p.get("replyCount"), "view_count": None, "media": [], "extra": {},
                    "is_repost": _is_rt, "original_author": _author if _is_rt else None})
    return out


def fetch_mastodon(instance, user, n=10):
    look = _get(f"https://{instance}/api/v1/accounts/lookup?acct={urllib.parse.quote(user)}")
    aid = look.get("id") if isinstance(look, dict) else None
    if not aid:
        return []
    posts = _get(f"https://{instance}/api/v1/accounts/{aid}/statuses?limit={n}&exclude_reblogs=true")
    out = []
    for s in (posts if isinstance(posts, list) else []):
        out.append({"platform_post_id": s.get("id"), "content": _strip(s.get("content")),
                    "post_url": s.get("url"), "posted_at": _dt(s.get("created_at")),
                    "lang": s.get("language"), "like_count": s.get("favourites_count"),
                    "repost_count": s.get("reblogs_count"), "reply_count": s.get("replies_count"),
                    "view_count": None, "media": s.get("media_attachments") or [], "extra": {},
                    "is_repost": False, "original_author": None})  # exclude_reblogs=true upstream
    return out


def resolve_youtube_channel_id(url):
    """Resolve a YouTube /@handle, /user/X, /c/X or bare /X URL to its channel id (UC...).

    Reads the page's OWN identity only: the canonical <link> (always /channel/UC...)
    or the `externalId` inside `channelMetadataRenderer`. Never the first
    `"channelId"` on the page: on the European Parliament's own page that key
    belongs to the European Commission (related channels are serialised before the
    page's metadata), which is how 19 EU handles collapsed onto one channel and
    every EC video was stored as 19 "original" statements (found 2 Sep 2026).
    Cached by the caller into social_accounts.platform_account_id, so a wrong answer
    here is permanent; when in doubt return None and let the account skip."""
    html = _youtube_page(url)
    if html is None:
        return None
    cid = _own_channel_id(html)
    if cid:
        # The canonical link of the page served for the account's OWN URL is the
        # account's identity. Do NOT additionally require the modern @handle to equal
        # the legacy /user/ or /c/ name: `/user/eutube` legitimately serves the channel
        # whose vanity handle is @EuropeanCommission, and an equality gate cleared the
        # Commission itself on the 2 Sep 2026 dry run.
        return cid
    # No canonical link: a dead legacy name (404) or a redirect page. Retry once
    # through the modern handle form before giving up.
    handle = re.search(r'/(?:@|user/|c/)([^/?#]+)', url) or re.search(r'youtube\.com/([^/?#@]+)/?$', url)
    if handle and not url.startswith("https://www.youtube.com/@"):
        return resolve_youtube_channel_id(f"https://www.youtube.com/@{handle.group(1)}")
    return None


def _youtube_page(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en-GB,en;q=0.9"})
        return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return None


def _own_channel_id(html):
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]+)"', html)
    if m:
        return m.group(1)
    i = html.find('"channelMetadataRenderer"')
    if i >= 0:
        m = re.search(r'"externalId":"(UC[\w-]+)"', html[i:i + 6000])
        if m:
            return m.group(1)
    return None


def _own_handle(html):
    """The page's own vanity handle, lower-cased, or None. The FIRST vanityChannelUrl on
    the page is the page's own; related channels' entries come later."""
    m = re.search(r'"vanityChannelUrl":"[^"]*?/(?:@|user/|c/)([^"/?#]+)"', html)
    return m.group(1).lower() if m else None


def _channel_matches_handle(channel_id, handle):
    """True when the channel page for `channel_id` declares `handle` as its own vanity
    handle. Used by the collision backfill; any fetch failure counts as a mismatch."""
    html = _youtube_page(f"https://www.youtube.com/channel/{channel_id}")
    if html is None:
        return False
    return _own_handle(html) == handle.lower().lstrip("@")


def fetch_youtube(channel_id, n=10):
    xml = _get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", parse="raw")
    if not isinstance(xml, str):
        return []
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S)[:n]:
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry)
        title = re.search(r"<title>(.*?)</title>", entry)
        pub = re.search(r"<published>(.*?)</published>", entry)
        views = re.search(r'views="(\d+)"', entry)
        if not vid:
            continue
        out.append({"platform_post_id": vid.group(1), "content": unescape(title.group(1)) if title else None,
                    "post_url": f"https://www.youtube.com/watch?v={vid.group(1)}",
                    "posted_at": _dt(pub.group(1)) if pub else None, "lang": None,
                    "like_count": None, "repost_count": None, "reply_count": None,
                    "view_count": int(views.group(1)) if views else None, "media": [], "extra": {}})
    return out


def fetch_for_account(platform, account_url, n=10):
    """Dispatch by platform; returns (posts, skip_reason)."""
    try:
        if platform == "bluesky":
            return fetch_bluesky(account_url.rstrip("/").split("/")[-1], n), None
        if platform == "mastodon":
            m = re.match(r"https?://([^/]+)/@(.+)$", account_url)
            return (fetch_mastodon(m.group(1), m.group(2), n), None) if m else ([], "bad_mastodon_url")
        if platform == "youtube":
            m = re.search(r"/channel/(UC[\w-]+)", account_url)
            return (fetch_youtube(m.group(1), n), None) if m else ([], "no_channel_id")
        if platform == "x":
            h = account_url.rstrip("/").split("/")[-1].split("?")[0]
            return (fetch_x(h, n), None) if h else ([], "bad_x_url")
        return [], "unsupported_platform"
    except Exception as e:
        return [], f"error:{type(e).__name__}"


def _resolve_youtube(db, a, dry_run):
    """Return channel id for a youtube account; resolve + persist to platform_account_id once."""
    cid = a["platform_account_id"]
    if cid:
        return cid
    m = re.search(r"/channel/(UC[\w-]+)", a["account_url"])
    if m:
        cid = m.group(1)
    else:
        cid = resolve_youtube_channel_id(a["account_url"])
    if cid and not dry_run:
        db.execute(text("UPDATE social_accounts SET platform_account_id=:c WHERE id=:i"),
                   {"c": cid, "i": a["id"]})
    return cid


def run(db, *, platforms=FETCHABLE, limit_accounts=None, per_account=10, pace=0.4,
        empty_streak_stop=None, dry_run=False, handles=None,
        prioritise_verified=False) -> dict:
    """Fetch posts for content_fetch_enabled accounts, OLDEST-checked first (so a capped
    cron run drips through the whole set over time). empty_streak_stop: stop the run after
    this many consecutive empty fetches (X throttle signal). last_checked_at is bumped per
    account so the next run advances.

    `handles`: fetch these specific handles INSTEAD of the oldest-first queue, ignoring
    when they were last checked. Added 25 Aug 2026. The drip alone cannot answer the
    question /social-eu asks on a law-drop day -- "did the institutions amplify their own
    law?" -- because the responsible DG is wherever the oldest-first queue happens to
    have left it. On 25 Aug the Commission published CBAM verifier guidance and
    @EU_Taxud had last been checked four days EARLIER, so a search for "CBAM" returned
    zero posts. Zero there meant "we have not looked", not "they said nothing", and the
    two are opposite findings. Targeting the handle makes the difference visible.
    """
    params = {"plats": list(platforms)}
    if handles:
        q = ("SELECT id, platform, account_url, platform_account_id, entity_name "
             "FROM social_accounts "
             "WHERE content_fetch_enabled = true AND platform = ANY(:plats) "
             "AND lower(handle) = ANY(:handles) "
             "ORDER BY last_checked_at ASC NULLS FIRST")
        params["handles"] = [h.lower().lstrip("@") for h in handles]
    elif prioritise_verified:
        # Verified accounts first, THEN oldest-first within each group.
        #
        # Pure oldest-first is the right policy when a full cycle is short. On X
        # it is not: the syndication endpoint throttles, every run stops early on
        # its empty-streak guard, and the measured throughput is ~70 accounts a
        # day against 1,135 enabled -- a 16-day cycle, not the 4.9 days the slot
        # arithmetic predicts. Adding cron slots does not fix that; it just hits
        # the throttle more often.
        #
        # So spend the scarce budget where the signal is. 464 of the 1,135 are
        # verified -- institutions, Commissioners, confirmed MEPs -- and those
        # cycle in ~6.6 days on the same throughput, while the unverified tail
        # lags. A Commissioner announcing a proposal is worth more than an
        # unconfirmed handle, and until today both waited the same 16 days.
        q = ("SELECT id, platform, account_url, platform_account_id, entity_name "
             "FROM social_accounts "
             "WHERE content_fetch_enabled = true AND platform = ANY(:plats) "
             "ORDER BY verified DESC, last_checked_at ASC NULLS FIRST")
    else:
        q = ("SELECT id, platform, account_url, platform_account_id, entity_name "
             "FROM social_accounts "
             "WHERE content_fetch_enabled = true AND platform = ANY(:plats) "
             "ORDER BY last_checked_at ASC NULLS FIRST")
    rows = db.execute(text(q + (f" LIMIT {int(limit_accounts)}" if limit_accounts else "")),
                      params).mappings().all()
    if handles and not rows:
        # Say so. A targeted fetch that matched nothing must not look like a quiet feed.
        logger.warning("[social] no fetch-enabled account matches handles=%s on platforms=%s",
                       handles, list(platforms))
    stats = {"accounts": len(rows), "fetched_ok": 0, "skipped": 0, "posts_written": 0,
             "by_platform": {}, "skips": {}, "stopped_early": False, "dry_run": dry_run}
    empty_streak = 0
    for a in rows:
        plat = a["platform"]
        if plat == "youtube":
            cid = _resolve_youtube(db, a, dry_run)
            posts, skip = (fetch_youtube(cid, per_account), None) if cid else ([], "no_channel_id")
        else:
            posts, skip = fetch_for_account(plat, a["account_url"], per_account)
        if not dry_run:
            db.execute(text("UPDATE social_accounts SET last_checked_at=now() WHERE id=:i"), {"i": a["id"]})
        if skip:
            stats["skipped"] += 1
            stats["skips"][skip] = stats["skips"].get(skip, 0) + 1
        else:
            stats["fetched_ok"] += 1
            for p in posts:
                if not p.get("platform_post_id"):
                    continue
                stats["posts_written"] += 1
                stats["by_platform"][plat] = stats["by_platform"].get(plat, 0) + 1
                if not dry_run:
                    row = {"account_id": a["id"], "platform": plat, **p, "fetched_at": func.now()}
                    stmt = pg_insert(SocialPost).values(**row)
                    stmt = stmt.on_conflict_do_update(
                        constraint="social_posts_account_post_uq",
                        set_={c: getattr(stmt.excluded, c) for c in _REFRESH} | {"fetched_at": func.now(), "updated_at": func.now()})
                    db.execute(stmt)
        if not dry_run:
            db.commit()
        # cooldown / throttle detection (mainly X syndication): stop after an empty streak
        if empty_streak_stop:
            empty_streak = empty_streak + 1 if not posts else 0
            if empty_streak >= empty_streak_stop:
                stats["stopped_early"] = True
                logger.warning("empty streak %d -> stopping run early (throttle?)", empty_streak)
                break
        time.sleep(pace)
    return stats
