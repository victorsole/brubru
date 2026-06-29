"""/api/v2/social — EU social media directory + posts (Phase 4 surface).

Read-only data-provider folder over social_accounts (3.8k mapped accounts: institutions,
agencies, MEPs, Commissioners, EU-affairs journalists) and social_posts (open-tier content:
Bluesky/Mastodon/YouTube + X via syndication). Every item exposes the 5 datapoints
(public_url, body_txt, body_html, document_date, creation_date); body_* are null on list and
composed on detail, the URL + dates are always populated. The cron fetchers are the write side.
IG/LinkedIn/TikTok are mapping-only (no content) — reflected by social_platforms.fetch_tier.
"""
from __future__ import annotations

import html as _html
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/social", tags=["v2-social"])

_ENTITY_TYPES = ("institution", "ec_dg", "ep_committee", "political_group", "eu_agency",
                 "perm_rep", "eutr_org", "mep", "commissioner", "ec_official", "eu_influencer")


# ---- models -------------------------------------------------------------------- #
class SocialPost(BaseModel):
    id: int
    account_id: int
    entity_type: str
    entity_key: str
    entity_name: Optional[str] = None
    platform: str
    handle: Optional[str] = None
    like_count: Optional[int] = None
    repost_count: Optional[int] = None
    reply_count: Optional[int] = None
    view_count: Optional[int] = None
    title: str
    summary: Optional[str] = None
    public_url: Optional[str] = Field(None, description="Permalink to the post on the platform.")
    body_txt: Optional[str] = Field(None, description="Plain-text post body (null on list; full on detail).")
    body_html: Optional[str] = Field(None, description="HTML post body (null on list; full on detail).")
    document_date: Optional[datetime] = Field(None, description="When the post was published.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru fetched the post.")


class SocialAccount(BaseModel):
    id: int
    entity_type: str
    entity_key: str
    entity_name: Optional[str] = None
    platform: str
    scope: str
    handle: Optional[str] = None
    status: str
    verified: bool
    discovery_source: str
    content_fetch_enabled: bool
    title: str
    summary: Optional[str] = None
    public_url: Optional[str] = Field(None, description="Canonical URL of the account on the platform.")
    body_txt: Optional[str] = Field(None, description="Composed profile (null on list; full on detail).")
    body_html: Optional[str] = Field(None, description="HTML profile (null on list; full on detail).")
    document_date: Optional[datetime] = Field(None, description="When the account was last checked / first seen.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first mapped the account.")


class SocialPlatform(BaseModel):
    code: str
    name: str
    fetch_tier: str = Field(..., description="open | gated | hard | none — content-fetch feasibility.")
    notes: Optional[str] = None
    account_count: int = 0
    post_count: int = 0


class SocialDirectory(BaseModel):
    total_accounts: int
    total_posts: int
    verified_accounts: int
    accounts_by_entity_type: dict
    accounts_by_platform: dict
    posts_by_platform: dict
    note: str


# ---- item builders (fill the 5 datapoints) ------------------------------------- #
def _post_item(r, with_body: bool) -> SocialPost:
    content = (r["content"] or "").strip()
    name = r["entity_name"] or r["handle"] or r["entity_key"]
    title = f"{name} on {r['platform']}"
    summary = (content[:240] or None)
    body_txt = body_html = None
    if with_body:
        body_txt = content or f"[{r['platform']} post without text]"
        url = r["post_url"] or ""
        link = f'<p><a href="{_html.escape(url)}">{_html.escape(url)}</a></p>' if url else ""
        body_html = f"<p>{_html.escape(body_txt)}</p>{link}"
    return SocialPost(
        id=r["id"], account_id=r["account_id"], entity_type=r["entity_type"], entity_key=r["entity_key"],
        entity_name=r["entity_name"], platform=r["platform"], handle=r["handle"],
        like_count=r["like_count"], repost_count=r["repost_count"], reply_count=r["reply_count"],
        view_count=r["view_count"], title=title, summary=summary,
        public_url=r["post_url"], body_txt=body_txt, body_html=body_html,
        document_date=r["posted_at"], creation_date=r["created_at"])


def _account_item(r, with_body: bool) -> SocialAccount:
    name = r["entity_name"] or r["handle"] or r["entity_key"]
    title = f"{name} — {r['platform']}"
    summary = f"{r['entity_type']} · @{r['handle'] or '?'} · {r['status']}"
    body_txt = body_html = None
    if with_body:
        body_txt = (f"{name} — {r['entity_type']} on {r['platform']}. Handle: {r['handle']}. "
                    f"Status: {r['status']} (verified={r['verified']}). Scope: {r['scope']}. "
                    f"Discovered via: {r['discovery_source']}. URL: {r['account_url']}.")
        body_html = f"<p>{_html.escape(body_txt)}</p>"
    return SocialAccount(
        id=r["id"], entity_type=r["entity_type"], entity_key=r["entity_key"], entity_name=r["entity_name"],
        platform=r["platform"], scope=r["scope"], handle=r["handle"], status=r["status"],
        verified=r["verified"], discovery_source=r["discovery_source"],
        content_fetch_enabled=r["content_fetch_enabled"], title=title, summary=summary,
        public_url=r["account_url"], body_txt=body_txt, body_html=body_html,
        document_date=r["last_checked_at"] or r["first_seen_at"], creation_date=r["created_at"])


_POST_COLS = ("p.id, p.account_id, a.entity_type, a.entity_key, a.entity_name, p.platform, "
              "a.handle, p.like_count, p.repost_count, p.reply_count, p.view_count, p.content, "
              "p.post_url, p.posted_at, p.created_at")
_ACC_COLS = ("id, entity_type, entity_key, entity_name, platform, scope, handle, status, verified, "
             "discovery_source, content_fetch_enabled, account_url, last_checked_at, first_seen_at, created_at")


# ---- endpoints ----------------------------------------------------------------- #
@router.get("", response_model=SocialDirectory, summary="Social folder directory — what's mapped and what carries content",
            description="""**What it does**: Overview of Brubru's EU social directory: how many accounts and posts, broken down by entity type and platform.

**When to use it**: First call to understand coverage before querying posts or accounts.

**Input**: none.

**Try it**: `GET /api/v2/social`

**You get back**: total accounts/posts, verified count, accounts by entity_type (mep, commissioner, institution, eu_agency, ec_official, eu_influencer), accounts and posts by platform, and a note on which platforms carry content vs mapping-only.""")
async def directory(db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    def d(sql):
        return {k: v for k, v in db.execute(text(sql)).fetchall()}
    return SocialDirectory(
        total_accounts=db.execute(text("SELECT count(*) FROM social_accounts")).scalar(),
        total_posts=db.execute(text("SELECT count(*) FROM social_posts")).scalar(),
        verified_accounts=db.execute(text("SELECT count(*) FROM social_accounts WHERE verified")).scalar(),
        accounts_by_entity_type=d("SELECT entity_type,count(*) FROM social_accounts GROUP BY 1 ORDER BY 2 DESC"),
        accounts_by_platform=d("SELECT platform,count(*) FROM social_accounts GROUP BY 1 ORDER BY 2 DESC"),
        posts_by_platform=d("SELECT platform,count(*) FROM social_posts GROUP BY 1 ORDER BY 2 DESC"),
        note="Content fetched for open platforms (Bluesky, Mastodon, YouTube) + X (paced). "
             "Instagram/LinkedIn/TikTok are mapping-only (no posts).")


@router.get("/posts", response_model=PaginatedResponse[SocialPost], summary="Recent EU social posts (newest first)",
            description="""**What it does**: Lists recent posts from mapped EU accounts, newest first.

**When to use it**: Monitor what EU institutions, MEPs, Commissioners and EU-affairs journalists are posting.

**Input**: `platform`, `entity_type`, `entity_key`, `account_id`, `since` (ISO date), `q` (text search), `page`, `limit`.

**Try it**: `GET /api/v2/social/posts?entity_type=commissioner&platform=x&limit=20`

**You get back**: a `PaginatedResponse[SocialPost]`. Each item: entity, platform, engagement counts, and the 5 datapoints (post URL as public_url, body null on list, published date). Use the detail endpoint for the full text.""")
async def list_posts(db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit),
                     platform: Optional[str] = Query(None), entity_type: Optional[str] = Query(None),
                     entity_key: Optional[str] = Query(None), account_id: Optional[int] = Query(None),
                     since: Optional[str] = Query(None, description="ISO date; posts on/after this"),
                     q: Optional[str] = Query(None, description="text search in post content"),
                     page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200)):
    where, params = ["1=1"], {}
    if platform: where.append("p.platform=:pf"); params["pf"] = platform
    if entity_type: where.append("a.entity_type=:et"); params["et"] = entity_type
    if entity_key: where.append("a.entity_key=:ek"); params["ek"] = entity_key
    if account_id: where.append("p.account_id=:aid"); params["aid"] = account_id
    if since: where.append("p.posted_at >= :since"); params["since"] = since
    if q: where.append("p.content ILIKE :q"); params["q"] = f"%{q}%"
    w = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM social_posts p JOIN social_accounts a ON a.id=p.account_id WHERE {w}"), params).scalar()
    params.update(off=(page - 1) * limit, lim=limit)
    rows = db.execute(text(f"SELECT {_POST_COLS} FROM social_posts p JOIN social_accounts a ON a.id=p.account_id "
                           f"WHERE {w} ORDER BY p.posted_at DESC NULLS LAST, p.id DESC LIMIT :lim OFFSET :off"), params).mappings().all()
    return build_envelope([_post_item(r, with_body=False) for r in rows], total, page, limit)


@router.get("/posts/{post_id}", response_model=SocialPost, summary="One post (full text)",
            description="""**What it does**: Returns a single post with its full body.

**When to use it**: After finding a post in the list and you want the complete text.

**Input**: `post_id` (path).

**Try it**: `GET /api/v2/social/posts/12345`

**You get back**: a `SocialPost` with all 5 datapoints populated: public_url, body_txt + body_html (full text), document_date (published), creation_date (fetched).""")
async def get_post(post_id: int = PathParam(...), db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    r = db.execute(text(f"SELECT {_POST_COLS} FROM social_posts p JOIN social_accounts a ON a.id=p.account_id WHERE p.id=:i"), {"i": post_id}).mappings().first()
    if not r:
        raise HTTPException(404, "post not found")
    return _post_item(r, with_body=True)


@router.get("/accounts", response_model=PaginatedResponse[SocialAccount], summary="The account directory (search by entity, platform, verified)",
            description="""**What it does**: Lists mapped social accounts across all platforms.

**When to use it**: Find an entity's accounts, or browse who Brubru tracks on a platform.

**Input**: `entity_type`, `platform`, `verified` (bool), `q` (name/handle search), `page`, `limit`.

**Try it**: `GET /api/v2/social/accounts?entity_type=mep&platform=bluesky&verified=true`

**You get back**: a `PaginatedResponse[SocialAccount]`. Each item: entity, platform, scope, handle, status/verified, discovery source, and the 5 datapoints (account URL as public_url, composed profile on detail, last-checked date).""")
async def list_accounts(db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit),
                        entity_type: Optional[str] = Query(None), platform: Optional[str] = Query(None),
                        verified: Optional[bool] = Query(None), q: Optional[str] = Query(None),
                        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200)):
    where, params = ["1=1"], {}
    if entity_type: where.append("entity_type=:et"); params["et"] = entity_type
    if platform: where.append("platform=:pf"); params["pf"] = platform
    if verified is not None: where.append("verified=:v"); params["v"] = verified
    if q: where.append("(entity_name ILIKE :q OR handle ILIKE :q)"); params["q"] = f"%{q}%"
    w = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM social_accounts WHERE {w}"), params).scalar()
    params.update(off=(page - 1) * limit, lim=limit)
    rows = db.execute(text(f"SELECT {_ACC_COLS} FROM social_accounts WHERE {w} "
                           f"ORDER BY verified DESC, entity_name ASC NULLS LAST, id ASC LIMIT :lim OFFSET :off"), params).mappings().all()
    return build_envelope([_account_item(r, with_body=False) for r in rows], total, page, limit)


@router.get("/accounts/{account_id}", response_model=SocialAccount, summary="One account (composed profile)",
            description="""**What it does**: Returns one account with its composed profile body.

**When to use it**: Inspect a specific account's metadata.

**Input**: `account_id` (path).

**Try it**: `GET /api/v2/social/accounts/7145`

**You get back**: a `SocialAccount` with all 5 datapoints: public_url, body_txt + body_html (composed profile), document_date (last checked), creation_date (first mapped).""")
async def get_account(account_id: int = PathParam(...), db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    r = db.execute(text(f"SELECT {_ACC_COLS} FROM social_accounts WHERE id=:i"), {"i": account_id}).mappings().first()
    if not r:
        raise HTTPException(404, "account not found")
    return _account_item(r, with_body=True)


@router.get("/entity/{entity_type}/{entity_key}", summary="One entity's full social footprint (accounts + recent posts)",
            description="""**What it does**: Returns every mapped account for one entity plus its most recent posts.

**When to use it**: 'Show me everything X says' — one MEP, Commissioner, institution, agency or journalist.

**Input**: `entity_type` (path), `entity_key` (path; the official id/slug), `posts_limit`.

**Try it**: `GET /api/v2/social/entity/commissioner/maros_sefcovic`

**You get back**: `{entity_type, entity_key, entity_name, accounts: [SocialAccount], recent_posts: [SocialPost]}` — accounts with composed profiles, posts with full body.""")
async def entity_footprint(entity_type: str = PathParam(...), entity_key: str = PathParam(...),
                           posts_limit: int = Query(20, ge=1, le=100),
                           db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    accs = db.execute(text(f"SELECT {_ACC_COLS} FROM social_accounts WHERE entity_type=:t AND entity_key=:k ORDER BY platform"),
                      {"t": entity_type, "k": entity_key}).mappings().all()
    if not accs:
        raise HTTPException(404, "entity not found")
    posts = db.execute(text(f"SELECT {_POST_COLS} FROM social_posts p JOIN social_accounts a ON a.id=p.account_id "
                            f"WHERE a.entity_type=:t AND a.entity_key=:k ORDER BY p.posted_at DESC NULLS LAST LIMIT :lim"),
                       {"t": entity_type, "k": entity_key, "lim": posts_limit}).mappings().all()
    return {"entity_type": entity_type, "entity_key": entity_key,
            "entity_name": accs[0]["entity_name"],
            "accounts": [_account_item(r, with_body=True) for r in accs],
            "recent_posts": [_post_item(r, with_body=True) for r in posts]}


@router.get("/platforms", response_model=List[SocialPlatform], summary="Platform pick-list + content-fetch feasibility",
            description="""**What it does**: Lists the social platforms Brubru recognises, each with its content-fetch tier and how many accounts/posts it holds.

**When to use it**: To know which platforms carry post content (open) vs mapping-only.

**Input**: none.

**Try it**: `GET /api/v2/social/platforms`

**You get back**: a list of `SocialPlatform`: code, name, fetch_tier (open/gated/hard/none), notes, account_count, post_count.""")
async def platforms(db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    rows = db.execute(text("""
        SELECT pl.code, pl.name, pl.fetch_tier, pl.notes,
               (SELECT count(*) FROM social_accounts a WHERE a.platform=pl.code) AS account_count,
               (SELECT count(*) FROM social_posts p WHERE p.platform=pl.code) AS post_count
        FROM social_platforms pl WHERE pl.is_active ORDER BY account_count DESC""")).mappings().all()
    return [SocialPlatform(**r) for r in rows]
