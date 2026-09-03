---
name: social-eu
description: Daily EU social-media review. The /news of social — refreshes and reviews recent posts from EVERY mapped account (EU institutions, agencies, MEPs, Commissioners, EU-affairs journalists) via the Phase 4 social directory + content layer (social_accounts / social_posts / /api/v2/social), surfaces the day's EU social pulse by actor, cross-references the /news ledger, and proposes improvements across the Brubru feature tree (Chat, MEUB MEP Watch / Council Watch / Stakeholder Mapping / Position Analysis / News, the social directory itself, API). Open-tier content only (Bluesky/Mastodon/YouTube + X via syndication); IG/LinkedIn/TikTok are mapping-only.
argument-hint: [today (default) | "48h" for 2-day window | "mep" / "commissioner" / "institution" / "influencer" to focus one actor type]
allowed-tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebFetch", "WebSearch", "mcp__brubru__search_knowledge_guides", "mcp__brubru__ask_brubru", "mcp__brubru__get_procedure_status"]
---

# Daily EU Social-Media Review (/social-eu)

The social-media sibling of `/news`. Where `/news` reviews what EU institutions *publish*, `/social-eu` reviews what EU actors *say and perform* on social media — the layer that often precedes or explains the formal documents. It is a **product-intelligence activity across the Brubru feature tree**: a Commissioner announcing a proposal, an MEP signalling a position, a journalist breaking a file, a stakeholder campaigning — each is a potential improvement to Chat, My EU Bubble (MEP Watch, Council Watch, Stakeholder Mapping, Position Analysis, News, Predictions), or the social API.

Read `memory/MEMORY.md` for daily context and `memory/reference_eu_social_media_directory.md` + the Phase 4 design in `docs/api/extract_engine_plan.md` for the directory model. Scope decisions (D1): mapping covers ALL platforms; content is fetched only where free + ToS-clean (Bluesky/Mastodon/YouTube + X via the public syndication endpoint). IG/LinkedIn/TikTok are **mapping-only** — never scrape them for posts.

## Step 0: Context check

```bash
cd /Users/victorsole/Developer/brubru/backend
python3.12 - <<'PY'
import logging; logging.disable(logging.WARNING)
from core.database import SessionLocal; from sqlalchemy import text
db=SessionLocal(); q=lambda s: db.execute(text(s)).scalar()
print("accounts:", q("SELECT count(*) FROM social_accounts"), "| verified:", q("SELECT count(*) FROM social_accounts WHERE verified"))
print("by entity_type:", dict(db.execute(text("SELECT entity_type,count(*) FROM social_accounts GROUP BY 1 ORDER BY 2 DESC")).fetchall()))
print("posts total:", q("SELECT count(*) FROM social_posts"), "| last 24h:", q("SELECT count(*) FROM social_posts WHERE posted_at >= now()-interval '24 hours'"))
print("oldest last_checked (drip frontier):", q("SELECT min(last_checked_at) FROM social_accounts WHERE content_fetch_enabled"))
db.close()
PY
```
Report coverage + freshness to the user before proceeding.

## Step 1: Refresh content (drip) + directory freshness

1. **Pull fresh posts** (oldest-checked accounts first; the same fetchers the cron uses):
   ```bash
   # ABSOLUTE PATHS, always (set 2 Sep 2026). A backgrounded shell does not
   # inherit the foreground `cd backend`; on 2 Sep both drips ran from the
   # repo root, printed "can't open file 'scripts/fetch_social_posts.py'",
   # exited 2, and the day's pulse was nearly reported as "refreshed".
   B=/Users/victorsole/Developer/brubru/backend
   # open tier (robust, keyless) — a wide batch
   cd $B && python3.12 $B/scripts/fetch_social_posts.py --platforms bluesky,mastodon,youtube --per-account 10 --pace 0.4 --limit 200 --apply
   # X drip (paced + throttle-stop; the syndication endpoint rate-limits, so a small slow batch)
   cd $B && python3.12 $B/scripts/fetch_social_posts.py --platforms x --per-account 10 --pace 5 --empty-streak-stop 8 --limit 40 --apply
   ```

   **Prove the drip happened before quoting it.** The log line is not the proof;
   the rows are. Run this and require `fetched_this_run > 0` on at least one
   open-tier platform before writing "refreshed" anywhere:

   ```sql
   SELECT platform, count(*) AS fetched_this_run,
          count(*) FILTER (WHERE posted_at >= now()-interval '24 hours') AS of_which_24h
   FROM social_posts WHERE fetched_at >= now()-interval '30 minutes' GROUP BY 1;
   ```
   A zero here with a green-looking log means the script did not run (wrong
   CWD, wrong interpreter, exit 2 swallowed by `;`), not that the EU was quiet.

   **The X backlog does not clear at `--limit 40`** (measured 27 Aug 2026): 719 of
   1,135 fetch-enabled X accounts were stale beyond seven days, which is 18 runs
   at that cap even before throttling. The open tier was 100% fresh in the same
   window, so the staleness is X-specific and structural, not a drip failure.
   X carries ~69% of fetch-enabled accounts and nearly every MEP, so the MEP
   layer is the thinnest part of any day's picture. Raise the cap when the
   endpoint tolerates it:

   ```bash
   # second, larger X window -- stop early on a throttle streak, as before
   python3.12 scripts/fetch_social_posts.py --platforms x --per-account 5 --pace 4 --empty-streak-stop 10 --limit 150 --apply
   ```

   **Always check whether an empty run is throttle or a dead pipeline** before
   reporting it: `SELECT posted_at::date, count(*) FROM social_posts WHERE
   platform='x' AND posted_at > now()-interval '10 days' GROUP BY 1`. On 27 Aug
   the batch returned 0 posts while X had produced 78 the previous day -- that is
   throttle. Never add a proxy or evasion to beat it.
   X is best-effort: if it stops early on a throttle streak that is expected (the cron keeps dripping). Never add proxy/evasion to beat the throttle.

2. **Directory freshness (weekly-ish, surface gaps daily):**
   - New current MEPs / Commissioners since last run → re-run the relevant loader (`load_wikidata_mep_socials.py` / `load_directory_persons.py` / `load_eu_social_directory.py`) only if the roster changed.
   - **Influencer outlets** (`scripts/load_influencers.py`): Politico Europe (Feedspot roster), **Financial Times** EU/Brussels reporters (web-search → Feedspot → verified on each ft.com author profile, X handles), Sifted newsroom, Contexte EU newsroom. To add a new outlet, hand its roster URL to the loader (search the outlet's EU/Brussels team, confirm via profile pages, never fabricate a handle). New fetchable-platform accounts must be `content_fetch_enabled=true` (the loaders default it false, so enable x/bluesky/mastodon/youtube after a load).
   - **Dark actors**: MEPs/Commissioners with zero mapped accounts → candidates for the internet-search gap-fill (Wave 2.1 step 3). List them; do not fabricate handles.
   - **Dead/renamed accounts**: accounts returning 0 posts for many runs while peers are active → flag for review (could be a handle change). Never delete blindly.

## Step 2: Present the day's EU social pulse (SINGLE OUTPUT)

Pull recent posts and present, grouped **by actor type**, newest + highest-signal first:

```bash
python3.12 - <<'PY'
import logging; logging.disable(logging.WARNING)
from core.database import SessionLocal; from sqlalchemy import text
db=SessionLocal()
rows=db.execute(text("""
  SELECT a.entity_type, a.entity_name, p.platform, p.posted_at::date d,
         coalesce(p.like_count,0)+coalesce(p.repost_count,0) AS eng, left(p.content,120) c, p.post_url
  FROM social_posts p JOIN social_accounts a ON a.id=p.account_id
  WHERE p.posted_at >= now()-interval '24 hours'
    AND NOT p.is_repost          -- an amplification is not this actor's statement
  ORDER BY a.entity_type,
           -- Rank on POLICY SIGNAL, not raw engagement. On 24 Aug 2026 the
           -- most-amplified post in the window was an MEP's domestic Pride post
           -- at 2,526, while Kallas announcing the largest Russia sanctions
           -- package of the war scored 434. Engagement measures reach, not
           -- relevance, and this feed exists to find the second thing.
           (CASE a.entity_type WHEN 'commissioner' THEN 3 WHEN 'institution' THEN 2
                               WHEN 'eu_agency' THEN 2 ELSE 1 END) DESC,
           -- The concatenation MUST be parenthesised (fixed 27 Aug 2026). `~*`
           -- binds tighter than `||`, so without the outer parentheses Postgres
           -- evaluates `content ~* '(regulation|...|'` -- an unbalanced regex --
           -- and the whole query dies with
           -- "invalid regular expression: parentheses () not balanced".
           -- This query had never run as written.
           (p.content ~* ('(regulation|directive|proposal|sanction|deadline|entry into force|'
                       || 'applies from|adopt|trilogue|delegated act|implementing act|'
                       || 'consultation|passport|ecodesign|tariff)')) DESC,
           eng DESC NULLS LAST, p.posted_at DESC""")).mappings().all()
print("posts in window:", len(rows))
PY
```

Output sections (skip an empty one):
- **A. Commissioners** — what the College said (policy announcements, positions). Highest priority.
- **B. MEPs** — rapporteur/shadow signals, position statements, file reactions.
- **C. Institutions / agencies / offices** — official announcements, campaigns, events.
- **D. EU-affairs journalists** — what the press is flagging/breaking (often the earliest signal).
- **E. Top by engagement** — the most-amplified posts today. Report engagement as a
  SEPARATE section, never as the primary ordering: it measures reach, not policy
  relevance, and on 24 Aug 2026 it put a domestic Pride post (2,526) above the
  largest Russia sanctions announcement of the war (434).
- **E2. Reposts** — excluded from the actor sections by `NOT p.is_repost`
  (migration 219). List them separately if useful, attributed to
  `original_author`. A repost is evidence of what an actor AMPLIFIED, never of
  what they said.
- **F. Cross-reference vs `/news`** — where a post corroborates, precedes, or contradicts today's `/news` ledger (a Commissioner tweet before the formal COM; a journalist breaking a file before the OJ). This is the unique value: social as the leading indicator.

For each item: actor + type, platform, engagement, one-line content, permalink. Be honest about gaps (X may be thin on a throttled day; IG/LinkedIn/TikTok carry no posts by design).

## Step 3: Feature-tree proposals

Walk the relevant features (use the EXACT MEUB sub-tab names from `memory/reference_meub_organisation.md`):

- **Chat (KB)** — a Commissioner/MEP post announcing or positioning on a file → a guide trigger or a fact to ground. Never ground an unverified rumour; a post is a *signal*, the formal source is the citation.
- **MEUB › MEP Watch** — surface a tracked MEP's latest posts/positions.
- **MEUB › Council Watch** — Council/PermRep/minister social signals on a dossier.
- **MEUB › Stakeholder Mapping** — EUTR-org + influencer posts as stakeholder-position evidence.
- **MEUB › Position Analysis** — a post stating a position → a refresh trigger / evidence row (flag, do not auto-assert; the post is the provenance).
- **MEUB › News** — the social feed as a complementary surface to the news feed.
- **MEUB › Predictions** — sustained social activity/sentiment on a file as a soft leading-indicator feature (candidate signal, clearly flagged, never a fabricated metric).
- **Social directory itself** — coverage gaps (dark MEPs, missing platforms), verification promotions (candidate→verified where a new official source confirms), new influencer outlets to add (hand a roster URL to `load_influencers.py`).
- **API (`/api/v2/social`)** — any endpoint gap surfaced (a filter consumers need, a missing field). Touching it = retrofit the 5-section description + run `/postman`.

Present as a single proposals table (feature | signal | proposed action | source post URL). **Do NOT implement yet** — wait for the user's pick, per the morning consent gate.

## Step 4: Implement (user-directed)

Implement only what the user greenlights, per feature. Hard rules carry over:
- **No fabrication**: a social post grounds a *signal*; the citable fact still comes from the official source. Never invent a handle, a stat, or a position the post does not state.
- **No hard-platform scraping**: X via the public syndication endpoint only; never IG/LinkedIn/TikTok posts.
- Directory edits go through the loaders (idempotent, upsert on account_url); verification promotions require a confirming source.
- If the API changed, run `/postman` in the same session.

## Step 5: Log

Append a one-line summary to the day's session MD (`docs/morning_routine/YYYY/MM_monthname/...`): posts reviewed, top signal, gaps flagged, features touched. If `/social-eu` ran inside `/morning`, this folds into the session MD already open.

## Important notes
- This is the **social** review; `/news` remains the institutional-publication review. They are complementary — run `/social-eu` AFTER `/news` so you can cross-reference the same day's ledger.
- Open-tier content is keyless + ToS-clean; X is paced/best-effort; IG/LinkedIn/TikTok stay mapping-only (D1, no paid API, no covert scraping).
- The cron (`/api/cron/fetch-social-posts`) already drips content daily; the skill's Step-1 pull is a fresh top-up, not the only refresh.
