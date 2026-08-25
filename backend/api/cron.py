"""
Cron Job Endpoints

Internal endpoints for scheduled data synchronisation tasks.
Authenticated via CRON_SECRET header, not user JWT.

Railway cron service calls these endpoints on a schedule.
"""

import logging
import time as _time
from fastapi import APIRouter, HTTPException, Header, Query
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cron", tags=["Cron Jobs"])


def _verify_cron_secret(authorization: str = Header(...)):
    """Verify the cron secret key from Authorization header."""
    expected = settings.CRON_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="Cron jobs not configured")

    # Accept "Bearer <secret>" or plain "<secret>"
    token = authorization.replace("Bearer ", "").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid cron secret")


@router.post("/sync/oeil")
async def cron_sync_oeil(
    authorization: str = Header(...),
    days: int = Query(default=7, ge=1, le=30),
):
    """
    Sync OEIL XML feeds (called by Railway cron every 6 hours).

    Fetches latest procedures, documents, and committee reports from OEIL.
    """
    _verify_cron_secret(authorization)

    db = SessionLocal()
    try:
        from services.scrapers.oeil_sync_service import OEILSyncService

        logger.info(f"[CRON] OEIL sync started (days={days})")

        service = OEILSyncService(db=db)
        result = await service.sync_all(
            procedures_days=days,
            documents_days=days,
            reports_days=30,
            skip_existing=True,
        )

        logger.info(
            f"[CRON] OEIL sync complete: added={result['added']}, "
            f"updated={result['updated']}, skipped={result['skipped']}"
        )

        return {
            "status": "success",
            "source": "oeil",
            "added": result["added"],
            "updated": result["updated"],
            "skipped": result["skipped"],
            "errors": result["errors"],
        }

    except Exception as e:
        logger.error(f"[CRON] OEIL sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OEIL sync failed: {str(e)}")
    finally:
        db.close()


@router.post("/sync/eurlex")
async def cron_sync_eurlex(
    authorization: str = Header(...),
    days: int = Query(default=7, ge=1, le=30),
):
    """
    Sync EUR-Lex RSS feeds (called by Railway cron every 6 hours).

    Fetches latest legislation and Commission proposals from EUR-Lex.
    """
    _verify_cron_secret(authorization)

    db = SessionLocal()
    try:
        from services.scrapers.eurlex_sync_service import EURLexSyncService

        logger.info(f"[CRON] EUR-Lex sync started (days={days})")

        service = EURLexSyncService(db=db)
        result = await service.sync_all(
            legislation_days=days,
            proposals_days=days,
            skip_existing=True,
        )

        logger.info(
            f"[CRON] EUR-Lex sync complete: added={result['added']}, "
            f"updated={result['updated']}, skipped={result['skipped']}"
        )

        return {
            "status": "success",
            "source": "eurlex",
            "added": result["added"],
            "updated": result["updated"],
            "skipped": result["skipped"],
            "errors": result["errors"],
        }

    except Exception as e:
        logger.error(f"[CRON] EUR-Lex sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"EUR-Lex sync failed: {str(e)}")
    finally:
        db.close()


@router.post("/sync/all")
async def cron_sync_all(
    authorization: str = Header(...),
    days: int = Query(default=7, ge=1, le=30),
):
    """
    Run all sync tasks (called by Railway cron every 6 hours).

    Runs sequentially: OEIL, EUR-Lex, Committee Work, Texts Adopted, Commission Docs.
    Each source uses its own DB session. Failures are isolated (one failing doesn't stop others).
    """
    _verify_cron_secret(authorization)

    results = {}

    # OEIL sync
    db = SessionLocal()
    try:
        from services.scrapers.oeil_sync_service import OEILSyncService

        logger.info("[CRON] Starting combined sync: OEIL")
        service = OEILSyncService(db=db)
        oeil_result = await service.sync_all(
            procedures_days=days,
            documents_days=days,
            reports_days=30,
            skip_existing=True,
        )
        results["oeil"] = {
            "status": "success",
            "added": oeil_result["added"],
            "updated": oeil_result["updated"],
        }
    except Exception as e:
        logger.error(f"[CRON] OEIL sync failed: {str(e)}")
        results["oeil"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    # EUR-Lex sync
    db = SessionLocal()
    try:
        from services.scrapers.eurlex_sync_service import EURLexSyncService

        logger.info("[CRON] Starting combined sync: EUR-Lex")
        service = EURLexSyncService(db=db)
        eurlex_result = await service.sync_all(
            legislation_days=days,
            proposals_days=days,
            skip_existing=True,
        )
        results["eurlex"] = {
            "status": "success",
            "added": eurlex_result["added"],
            "updated": eurlex_result["updated"],
        }
    except Exception as e:
        logger.error(f"[CRON] EUR-Lex sync failed: {str(e)}")
        results["eurlex"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    # Committee Work sync (26 EP committees)
    db = SessionLocal()
    try:
        from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService

        logger.info("[CRON] Starting combined sync: Committee Work")
        service = CommitteeWorkSyncService(db=db)
        cw_result = await service.sync_all(skip_existing=True)
        results["committee_work"] = {
            "status": "success",
            "added": cw_result.get("added", 0),
            "updated": cw_result.get("updated", 0),
        }
    except Exception as e:
        logger.error(f"[CRON] Committee Work sync failed: {str(e)}")
        results["committee_work"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    # Texts Adopted sync (EP plenary votes via RSS)
    db = SessionLocal()
    try:
        from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

        logger.info("[CRON] Starting combined sync: Texts Adopted")
        service = TextsAdoptedSyncService(db=db)
        ta_result = await service.sync_rss(skip_existing=True)
        results["texts_adopted"] = {
            "status": "success",
            "added": ta_result.get("added", 0),
            "updated": ta_result.get("updated", 0),
        }
    except Exception as e:
        logger.error(f"[CRON] Texts Adopted sync failed: {str(e)}")
        results["texts_adopted"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    # Commission Documents sync (COM/OJ via EUR-Lex fallback)
    db = SessionLocal()
    try:
        from services.scrapers.commission_doc_sync_service import CommissionDocSyncService

        logger.info("[CRON] Starting combined sync: Commission Documents")
        service = CommissionDocSyncService(db=db)
        cd_result = await service.sync_all(days=days, skip_existing=True)
        results["commission_docs"] = {
            "status": "success",
            "added": cd_result.get("added", 0),
            "updated": cd_result.get("updated", 0),
        }
    except Exception as e:
        logger.error(f"[CRON] Commission Documents sync failed: {str(e)}")
        results["commission_docs"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    logger.info(f"[CRON] Combined sync complete: {results}")

    return {"status": "success", "results": results}


# ---------------------------------------------------------------------------
# Tiered cron endpoints (14 May 2026 onwards) — driven by sync_cadence.json
# ---------------------------------------------------------------------------
#
# Each tier endpoint runs a curated set of sync services / scripts in sequence,
# fail-soft per source. Called by the single Railway service `brubru-cron-sync`
# via `scripts/cron_dispatch.py`, which decides which tier(s) to fire based on
# the current UTC time.
#
# Cadence (from backend/config/sync_cadence.json):
#   hot_6h   → 00:00 / 06:00 / 12:00 / 18:00 UTC  (calendar, OEIL, EUR-Lex, plenary)
#   warm_12h → 02:00 / 14:00 UTC                  (committees, EPRS)
#   daily    → 04:00 UTC                          (consultations, comitology, specialised mirrors)
#   weekly   → Sunday 05:00 UTC                   (slow universes — FTAs, GIs, vocabs, research)
#   monthly  → 1st of month 02:00 UTC             (officials whoiswho, NAL releases check)


def _run_service(name: str, fn):
    """Run a sync coroutine with a fresh DB session. Fail-soft + log."""
    import asyncio as _asyncio
    db = SessionLocal()
    try:
        logger.info(f"[CRON] Tier sync: {name} started")
        out = _asyncio.run(fn(db)) if _asyncio.iscoroutinefunction(fn) else fn(db)
        added = (out or {}).get("added", 0) if isinstance(out, dict) else 0
        updated = (out or {}).get("updated", 0) if isinstance(out, dict) else 0
        logger.info(f"[CRON] Tier sync: {name} done (added={added}, updated={updated})")
        return {"status": "success", "added": added, "updated": updated}
    except Exception as e:
        logger.error(f"[CRON] Tier sync: {name} failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


async def _run_async_service(name: str, coro_fn):
    """Async variant — awaits the coroutine in the current event loop."""
    db = SessionLocal()
    try:
        logger.info(f"[CRON] Tier sync: {name} started")
        out = await coro_fn(db)
        added = (out or {}).get("added", 0) if isinstance(out, dict) else 0
        updated = (out or {}).get("updated", 0) if isinstance(out, dict) else 0
        logger.info(f"[CRON] Tier sync: {name} done (added={added}, updated={updated})")
        return {"status": "success", "added": added, "updated": updated}
    except Exception as e:
        logger.error(f"[CRON] Tier sync: {name} failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def _run_script(name: str, script_relpath: str, args: list[str] | None = None, timeout: int = 600):
    """Run a CLI sync script as a subprocess. Fail-soft + log."""
    import subprocess
    import sys
    import os
    args = args or []
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(backend_root, script_relpath)
    if not os.path.exists(script_path):
        logger.warning(f"[CRON] Tier sync: {name} script not found at {script_path}, skipping")
        return {"status": "skipped", "reason": "script_not_found"}
    try:
        logger.info(f"[CRON] Tier sync: {name} started ({script_relpath})")
        proc = subprocess.run(
            [sys.executable, script_path, *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=backend_root,
        )
        if proc.returncode == 0:
            logger.info(f"[CRON] Tier sync: {name} done")
            return {"status": "success", "stdout_tail": (proc.stdout or "")[-500:]}
        logger.error(f"[CRON] Tier sync: {name} exited {proc.returncode}: {(proc.stderr or '')[-300:]}")
        return {"status": "failed", "returncode": proc.returncode, "stderr_tail": (proc.stderr or "")[-500:]}
    except subprocess.TimeoutExpired:
        logger.error(f"[CRON] Tier sync: {name} timed out after {timeout}s")
        return {"status": "failed", "error": f"timeout_{timeout}s"}
    except Exception as e:
        logger.error(f"[CRON] Tier sync: {name} crashed: {e}")
        return {"status": "failed", "error": str(e)}


async def _run_script_async(name: str, script_relpath: str, args: list[str] | None = None, timeout: int = 600):
    """Async wrapper for `_run_script`.

    `_run_script` runs a blocking `subprocess.run`. The backend is a SINGLE
    uvicorn worker (one event loop), so calling it directly from an `async def`
    cron endpoint freezes EVERY HTTP request for the whole subprocess duration.
    A fast-tier chain (news/OJ/votes) is 15+ minutes of back-to-back scripts, so
    the entire backend went unresponsive during each cron window and all MEUB
    surfaces (Calendar, Votes, cockpit) hung on "Loading..." (incident 2 Jul 2026).

    Offloading to the threadpool keeps the event loop free to serve users while
    the sync runs. subprocess.run releases the GIL while waiting on the child, so
    the loop is genuinely unblocked.
    """
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_run_script, name, script_relpath, args, timeout)


@router.post("/sync/hot-6h")
async def cron_sync_hot_6h(
    authorization: str = Header(...),
    days: int = Query(default=2, ge=1, le=30, description="Lookback window for delta sync"),
):
    """
    Hot-tier sync (every 6 hours): OEIL + EUR-Lex + Texts Adopted/Submitted + Commission Docs +
    College agendas + Calendar + Cellar /recent.

    Cadence: 00:00 / 06:00 / 12:00 / 18:00 UTC. Sources where same-day freshness is a conversion lever.
    """
    _verify_cron_secret(authorization)
    results = {}

    async def _oeil(db):
        from services.scrapers.oeil_sync_service import OEILSyncService
        return await OEILSyncService(db=db).sync_all(
            procedures_days=days, documents_days=days, reports_days=30, skip_existing=True,
        )

    async def _eurlex(db):
        from services.scrapers.eurlex_sync_service import EURLexSyncService
        return await EURLexSyncService(db=db).sync_all(
            legislation_days=days, proposals_days=days, skip_existing=True,
        )

    async def _texts_adopted(db):
        from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService
        return await TextsAdoptedSyncService(db=db).sync_rss(skip_existing=True)

    async def _commission_docs(db):
        from services.scrapers.commission_doc_sync_service import CommissionDocSyncService
        return await CommissionDocSyncService(db=db).sync_all(days=days, skip_existing=True)

    results["oeil"] = await _run_async_service("oeil", _oeil)
    results["eurlex"] = await _run_async_service("eurlex", _eurlex)
    results["texts_adopted"] = await _run_async_service("texts_adopted", _texts_adopted)
    results["commission_docs"] = await _run_async_service("commission_docs", _commission_docs)

    # Script-based syncs (no service wrapper yet)
    results["texts_submitted"] = await _run_script_async("texts_submitted", "scripts/ingest_texts_submitted.py", ["--apply"], timeout=600)
    results["college_agendas"] = await _run_script_async("college_agendas", "scripts/sync_college_agendas.py", [], timeout=600)
    results["calendar"] = await _run_script_async("calendar", "scripts/sync_eu_calendar.py", [], timeout=900)
    results["cellar_recent"] = await _run_script_async("cellar_recent", "scripts/sync_eurlex_via_sparql.py", ["--days", "1", "--apply"], timeout=600)

    logger.info(f"[CRON] hot-6h tier sync complete: {results}")
    return {"status": "success", "tier": "hot_6h", "results": results}


@router.post("/sync/warm-12h")
async def cron_sync_warm_12h(
    authorization: str = Header(...),
):
    """
    Warm-tier sync (every 12 hours): EP committee work + EPRS + committee minutes + committee agendas + transcripts.

    Cadence: 02:00 / 14:00 UTC. Sources that move daily but where half-day lag is acceptable.
    """
    _verify_cron_secret(authorization)
    results = {}

    async def _committee_work(db):
        from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService
        return await CommitteeWorkSyncService(db=db).sync_all(skip_existing=True)

    results["committee_work"] = await _run_async_service("committee_work", _committee_work)
    results["eprs_publications"] = await _run_script_async("eprs_publications", "scripts/sync_eprs_publications.py", ["--days", "3"], timeout=900)
    results["eprs_legislation"] = await _run_script_async("eprs_legislation", "scripts/sync_eprs_legislation_in_progress.py", [], timeout=600)
    results["committee_minutes"] = await _run_script_async("committee_minutes", "scripts/sync_committee_minutes.py", ["--max-pages", "2"], timeout=600)
    results["committee_agendas"] = await _run_script_async("committee_agendas", "scripts/sync_committee_agendas.py", [], timeout=600)
    results["committee_transcripts"] = await _run_script_async("committee_transcripts", "scripts/sync_committee_transcripts.py", ["--days", "30", "--max", "50"], timeout=900)
    # Auto-archive items past their lifespan (adopted carriages 90d+, closed
    # consultations 30d+, stale Commission docs 180d+). Idempotent; applies.
    results["auto_archive"] = await _run_script_async("auto_archive", "scripts/auto_archive_old_items.py", [], timeout=300)

    logger.info(f"[CRON] warm-12h tier sync complete: {results}")
    return {"status": "success", "tier": "warm_12h", "results": results}


@router.post("/precompute-journeys")
async def cron_precompute_journeys(
    authorization: str = Header(...),
    limit: int = Query(5, ge=1, le=40, description="Max dossiers to analyse this run"),
):
    """
    Precompute the legislative-journey AI analysis for tracked dossiers that are
    missing or stale. Throttled (default 5/run) so it backfills gradually. Runs
    in the warm tier alongside the committee-document syncs that feed it.
    """
    _verify_cron_secret(authorization)
    from core.database import SessionLocal
    from services.analysis.legislative_journey_service import precompute_tracked
    db = SessionLocal()
    try:
        result = await precompute_tracked(db, limit=limit)
    finally:
        db.close()
    logger.info(f"[CRON] precompute-journeys complete: {result}")
    return {"status": "success", "results": result}


@router.post("/build-procedure-snapshots")
async def cron_build_procedure_snapshots(
    authorization: str = Header(...),
    limit: int = Query(None, ge=1, description="Cap carriages (testing); omit for all"),
):
    """
    Build today's procedure-snapshot cube: one row per legislative procedure (carriage)
    with its slow state plus the five fast-signal counts (amendments, documents, committee
    work, lobby meetings, EPRS briefings). Idempotent — re-running the same day refreshes
    rows via ON CONFLICT (carriage_id, snapshot_date). Feeds the predictors' trajectory
    features. Runs once daily on a quiet hour.
    """
    _verify_cron_secret(authorization)
    from starlette.concurrency import run_in_threadpool
    from services.snapshots.snapshot_writer import write_daily_snapshots
    db = SessionLocal()
    try:
        result = await run_in_threadpool(write_daily_snapshots, db, limit=limit)
    finally:
        db.close()
    logger.info(f"[CRON] build-procedure-snapshots complete: {result}")
    return {"status": "success", "results": result}


@router.post("/fetch-social-posts")
async def cron_fetch_social_posts(
    authorization: str = Header(...),
    mode: str = Query("open", description="'open' = Bluesky/Mastodon/YouTube batch; 'x' = paced X drip"),
    limit: int = Query(None, ge=1, description="cap accounts this run (drip size)"),
):
    """
    Fetch recent posts from mapped social accounts (Phase 4.2 content layer). Oldest-checked
    accounts first, so each run drips through the set over time. mode='open' pulls the robust
    keyless APIs (Bluesky/Mastodon/YouTube). mode='x' drips the X accounts (1,135 enabled as of 25 Aug 2026) via the public
    syndication endpoint with slow pacing + a throttle-stop (no paid API, no IG/LinkedIn/TikTok).
    """
    _verify_cron_secret(authorization)
    from starlette.concurrency import run_in_threadpool
    from services.social.post_fetcher import run
    db = SessionLocal()
    try:
        if mode == "x":
            # prioritise_verified added 25 Aug 2026. X throttles, so every run
            # stops early on its empty-streak guard and real throughput is ~70
            # accounts/day against 1,135 enabled -- a 16-day cycle, not the 4.9
            # the slot arithmetic predicts. More slots just hit the throttle
            # more often. Spending the scarce budget on the 464 verified
            # accounts first cycles institutions, Commissioners and confirmed
            # MEPs in ~6.6 days and lets the unverified tail lag.
            result = await run_in_threadpool(
                run, db, platforms=("x",), limit_accounts=limit or 40,
                per_account=10, pace=5.0, empty_streak_stop=8,
                prioritise_verified=True)
        else:
            result = await run_in_threadpool(
                run, db, platforms=("bluesky", "mastodon", "youtube"),
                limit_accounts=limit or 150, per_account=10, pace=0.4)
    finally:
        db.close()
    logger.info(f"[CRON] fetch-social-posts mode={mode} complete: {result}")
    return {"status": "success", "results": result}


@router.post("/transcribe-pending")
async def cron_transcribe_pending(
    authorization: str = Header(...),
    limit: int = Query(3, ge=1, le=10, description="Max committee meetings to transcribe this run"),
):
    """
    Proactively transcribe PENDING committee-meeting recordings that have a ready
    HLS URL, newest-first within users' tracked / Policy-Interest committees.
    Uses Groq-hosted whisper-large-v3 (FREE tier) so the backlog drains at no cost.
    Self-heals rows stuck in TRANSCRIBING from a deploy-killed run. Throttled
    (default 3/run) and fired on otherwise-quiet hours so a run stays bounded.
    """
    _verify_cron_secret(authorization)
    result = await _run_script_async(
        "transcribe_pending",
        "scripts/transcribe_pending_committees.py",
        ["--all", "--max", str(limit), "--engine", "groq", "--reset-stuck"],
        timeout=1500,
    )
    logger.info(f"[CRON] transcribe-pending complete: {result}")
    return {"status": "success", "results": result}


@router.post("/sync/daily")
async def cron_sync_daily(
    authorization: str = Header(...),
):
    """
    Daily sync (04:00 UTC): consultations + delegated/implementing acts + TRIS + EU sanctions +
    transparency register + comitology + JRC + infringements + EESC + CoR + euagenda.

    Cadence: once per day. Sources that move a few times per week.
    """
    _verify_cron_secret(authorization)
    results = {}

    results["consultations"] = await _run_script_async("consultations", "scripts/sync_consultations.py", [], timeout=900)
    # Full Have Your Say sweep. The job above had only ever collected 362 of the
    # ~4,100 initiatives on the portal, so a user tracking a file could be told there
    # was no consultation on it when there was one (found 11 Aug 2026 looking for
    # initiative 16116, the ESPR delegated act on apparel textiles). This one pages
    # the whole portal and upserts on initiative_id, so the two are complementary:
    # this gives breadth, sync_consultations.py above enriches detail.
    results["have_your_say"] = await _run_script_async(
        "have_your_say", "scripts/sync_have_your_say.py", ["--apply"], timeout=1800)
    results["comitology"] = await _run_script_async("comitology", "scripts/backfill_eu_comitology.py", ["--apply", "--limit", "100"], timeout=900)
    results["tris"] = await _run_script_async("tris", "scripts/sync_dg_grow.py", ["--source", "tris", "--days", "7"], timeout=600)
    results["sanctions"] = await _run_script_async("sanctions", "scripts/backfill_eu_sanctions.py", ["--apply", "--limit", "100"], timeout=600)
    results["transparency_register"] = await _run_script_async("transparency_register", "scripts/backfill_eu_transparency_register.py", ["--apply", "--limit", "1000"], timeout=900)
    results["jrc"] = await _run_script_async("jrc", "scripts/backfill_eu_jrc_datasets.py", ["--apply", "--max-pages", "5"], timeout=600)
    results["infringements"] = await _run_script_async("infringements", "scripts/backfill_infringement_summary.py", ["--apply", "--limit", "50"], timeout=600)
    results["eesc"] = await _run_script_async("eesc", "scripts/backfill_eu_eesc.py", ["--apply"], timeout=600)
    results["cor"] = await _run_script_async("cor", "scripts/backfill_eu_cor.py", ["--apply"], timeout=600)
    results["euagenda"] = await _run_script_async("euagenda", "scripts/sync_euagenda.py", ["--max", "100"], timeout=600)
    # TED (tenders). This is the INGEST -- it fetches notices published in the
    # last 2 days from api.ted.europa.eu and inserts the new ones. Until 10 Aug
    # 2026 the only job named "tenders" here was the description backfill below,
    # which is pure compute over XML already in the table: it can enrich rows but
    # can never add one. The result was 386 rows whose newest arrival was 3 Jan
    # 2026, so a Blue-tier user opened the Tenderator on a seven-month-old feed.
    # 2 days rather than 1 covers a missed run without re-reading a week.
    results["tenders_fetch"] = await _run_script_async(
        "tenders_fetch",
        "scripts/fetch_tenders.py",
        ["--days", "2", "--max-results", "400"], timeout=1500,
    )
    # Enrichment pass over whatever is now in the table, including what the
    # fetch just added.
    results["tenders"] = await _run_script_async("tenders", "scripts/backfill_tenders_description.py", ["--apply", "--limit", "200"], timeout=900)
    # Repair any country the ingest could not resolve from the search payload,
    # reading each row's own stored XML. Cheap and idempotent: rows with a valid
    # country are skipped without touching the network.
    results["tenders_country_repair"] = await _run_script_async(
        "tenders_country_repair",
        "scripts/repair_tender_country.py",
        ["--apply"], timeout=300,
    )
    # Per-programme F&T grant calls (economy_items, item_type='grant') backing
    # /api/v2/funding/justice + /innovation-fund. Pulled from SEDIA by topic-id
    # prefix; idempotent upsert on (body_code, item_type, public_url).
    results["ft_programme_calls"] = await _run_script_async("ft_programme_calls", "scripts/ingest_ft_programme_calls.py", ["--all", "--apply"], timeout=900)
    # F&T Portal news + events (economy_items body 'ftportal') backing
    # /api/v2/funding/ft-news + /ft-events. SEDIA news/events indexes.
    results["ft_news_events"] = await _run_script_async("ft_news_events", "scripts/ingest_ft_news_events.py", ["--all", "--apply"], timeout=600)
    # F&T Portal opportunities (funding_opportunities + ft_calls_for_proposals)
    # — Horizon, EIC, EIE, CEF, Digital Europe, Erasmus+, CREA, CERV, EU4Health.
    # Pulled from SEDIA search API; idempotent upsert on topic_id / call_id.
    # Closes the 33-day ingest gap surfaced 30 June 2026 (last batch 27 May).
    # --write-ft is load-bearing. Without it this writes funding_opportunities
    # ONLY, and the Tenderator's unified feed reads ft_calls_for_proposals --
    # so the daily job refreshed a table no Tenderator surface queries while
    # the one it does query sat untouched since 15 Jun 2026.
    results["ft_funding_opportunities"] = await _run_script_async(
        "ft_funding_opportunities",
        "scripts/ingest_funding_sedia.py",
        ["--apply", "--limit", "500", "--write-ft"], timeout=900,
    )

    # Tenderator translations (MEUB-news pattern, migration 133): detect lang
    # on freshly-arrived TED + F&T rows and translate any foreign-language
    # titles into Brubru's 6 (en/es/ca/fr/it/nl). Idempotent — already-detected
    # rows are skipped. Capped per table per day so a single Railway cron run
    # stays inside the 30-min ceiling (M2M100 on CPU is ~1-3s per translation;
    # 6 langs × 2 fields per foreign row). Cheap (~seconds) when nothing new.
    results["tenderator_translations_ted"] = await _run_script_async(
        "tenderator_translations_ted",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "tenders", "--limit", "100", "--batch", "20"], timeout=900,
    )
    results["tenderator_translations_ft_tenders"] = await _run_script_async(
        "tenderator_translations_ft_tenders",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_calls_for_tenders", "--limit", "50", "--batch", "20"], timeout=600,
    )
    results["tenderator_translations_ft_proposals"] = await _run_script_async(
        "tenderator_translations_ft_proposals",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_calls_for_proposals", "--limit", "50", "--batch", "20"], timeout=600,
    )
    results["tenderator_translations_ft_projects"] = await _run_script_async(
        "tenderator_translations_ft_projects",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_funded_projects", "--limit", "50", "--batch", "20"], timeout=600,
    )

    # Tell users when a legislative file they track has moved. Added 25 Aug
    # 2026, because until that day Brubru had NEVER sent one of these: 613
    # carriage tracks, `last_notified_at` set on zero of them ever, and the
    # notifications table untouched since 18 June. Tracking is a promise of
    # future notification and the promise had never once been kept.
    #
    # This runs AFTER the carriage/OEIL syncs above on purpose: it compares each
    # track's stored baseline against the status those syncs have just written,
    # so running it first would report yesterday's world.
    #
    # Safe to run before seeding: a track with no baseline is skipped, never
    # notified, so a fresh environment cannot fire hundreds of notifications on
    # its first night. Seed deliberately with --seed-baseline.
    results["carriage_status_notifications"] = await _run_script_async(
        "carriage_status_notifications",
        "scripts/notify_carriage_status.py",
        [], timeout=600,
    )

    logger.info(f"[CRON] daily tier sync complete: {results}")
    return {"status": "success", "tier": "daily", "results": results}


# Economy folders (economy_items): the v2 institutional, agency and database
# endpoints (/api/v2/<body>/* + Funding & Tenders + Public Consultations). One
# sync_economy.py run per body backfills that body's news, events, publications,
# databases, tenders, grants, calls and consultations. ~45 bodies are split into
# three daily batches fired at 10:00 / 15:00 / 21:00 UTC (otherwise-quiet hours)
# so the scraper load is spread rather than hitting every EU site at once.
# `commission` is intentionally excluded: its sources (sanctions, comitology,
# GIs, trade defence, JRC, transparency register) are already on the daily and
# weekly tiers via their dedicated backfill scripts.
_ECONOMY_BATCHES: list[list[str]] = [
    # batch 0 (10:00 UTC) — financial-sector + early-alphabet bodies
    # Playwright-fed body for this window: cepol (one heavy Chromium body per
    # window so renders never overlap; see note below).
    ["dpp", "acer", "amla", "berec", "cedefop", "council", "cpvo", "eba", "ecb", "ecb_ssm", "ecdc", "echa",
     "cinea", "easa", "ela", "cepol", "eismea", "cdt", "cjeu", "eesc", "edps", "euiss", "esdc", "hydrogen", "euratom", "chips", "sesar"],
    # batch 1 (15:00 UTC) — Playwright-fed bodies for this window: europol, rail.
    ["eea", "efca", "efsa", "eib", "eige", "eiopa", "eit", "ema", "enisa", "eppo", "era", "esm", "esma",
     "emsa", "europol", "eacea", "ercea", "epso", "eas", "eca", "cor", "edpb", "eda", "edctp3", "aviation", "cbe", "rail"],
    # batch 2 (21:00 UTC) — Playwright-fed body for this window: eeas.
    ["esrb", "etf", "eu_lisa", "eu_osha", "euaa", "euda", "eurofound", "euipo", "eurojust", "fra", "parliament", "srb",
     "euspa", "frontex", "eeas", "hadea", "rea", "cert_eu", "ombudsman", "eccc", "satcen", "eurohpc", "ihi", "f4e", "sns"],
]
# Playwright note: cepol/europol/eeas (and the echa-topics + eurofound resources
# already in the batches) render through headless Chromium inside the backend
# container. They are spread one-per-window so at most one Chromium-heavy sync
# runs at 10:00 / 15:00 / 21:00 UTC. If the container OOMs on these, move the
# offending body to a local/manual refresh (drop it from this list).


# Strong references to in-flight economy background tasks. Without this the
# event loop can garbage-collect a bare create_task() coroutine mid-run.
_economy_tasks: set = set()
_economy_running: set[int] = set()


async def _run_economy_batch_bg(batch: int, bodies: list[str]) -> None:
    """Run one economy batch in the background (fire-and-forget from the endpoint).

    Moved off the request path 10 Jul 2026: a batch runs ~26 heavy bodies
    sequentially (up to 600s each, several via headless Chromium), which on the
    single uvicorn worker routinely overran the dispatcher's 1800s `_fire`
    timeout and got cut off before rows committed -- economy news ingestion had
    silently frozen since ~25 June. Returning immediately lets the dispatcher's
    HTTP call finish fast; the work continues here and records its own run so
    `/api/sync/health` surfaces the tier (root cause: it never called
    record_run, so the stall was invisible).
    """
    from datetime import datetime, timezone
    from services.sync.freshness import record_run

    started = datetime.now(timezone.utc)
    results: dict = {}
    ok_count = 0
    first_fail: str = ""  # "body: <stderr/return summary>" for the first non-success body
    try:
        for body in bodies:
            res = await _run_script_async(
                f"economy_{body}", "scripts/sync_economy.py",
                ["--body", body, "--type", "all"], timeout=600,
            )
            results[body] = res.get("status")
            if res.get("status") == "success":
                ok_count += 1
            elif not first_fail:
                _detail = (res.get("stderr_tail") or res.get("error")
                           or res.get("reason") or f"rc={res.get('returncode')}")
                first_fail = f"{body}: {str(_detail)[:400]}"

        # Tenderator translations for economy_items funding rows, AFTER all
        # bodies so freshly-arrived foreign agency rows get their 6-language
        # cache. Capped per batch to stay within budget.
        res_tr = await _run_script_async(
            "tenderator_translations_agency",
            "scripts/backfill_tenderator_translations.py",
            ["--table", "economy_items", "--funding-only", "--limit", "100", "--batch", "20"],
            timeout=900,
        )
        results["tenderator_translations_agency"] = res_tr.get("status")
        logger.info(f"[CRON] economy batch {batch} sync complete: {results}")

        db = SessionLocal()
        try:
            record_run(
                db, source_key="cron_dispatch", tier=f"economy_b{batch}",
                status=("success" if ok_count else "failed"),
                items_added=ok_count, started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=(None if ok_count else f"{ok_count}/{len(bodies)} bodies ok; first_fail {first_fail}"),
            )
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[CRON] economy batch {batch} background run failed: {exc}")
        db = SessionLocal()
        try:
            record_run(
                db, source_key="cron_dispatch", tier=f"economy_b{batch}",
                status="failed", error=str(exc)[:500], started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            db.close()
    finally:
        _economy_running.discard(batch)


@router.post("/sync/economy")
async def cron_sync_economy(
    batch: int = Query(0, ge=0, le=2, description="Economy body batch (0=10:00, 1=15:00, 2=21:00 UTC)."),
    authorization: str = Header(...),
):
    """
    Economy folders sync (daily, batched): refreshes the v2 institutional,
    agency and database endpoints backed by economy_items -- news, events,
    publications, databases, tenders/grants/calls and agency consultations --
    across ~45 EU bodies. Split into three batches (10:00 / 15:00 / 21:00 UTC)
    to spread scraper load. Fail-soft per body: one body's scraper failing
    never blocks the rest.

    Runs the batch as a BACKGROUND task and returns immediately so the
    dispatcher's HTTP call cannot time out and kill the run mid-flight. Records
    a freshness run at the end (visible in /api/sync/health). Cadence: once per
    day per body. `commission` is excluded here; its heavy bulk sub-datasets run
    on the dedicated `/sync/commission-heavy` weekly tier (Sunday 07:00 UTC).
    """
    _verify_cron_secret(authorization)
    import asyncio
    bodies = _ECONOMY_BATCHES[batch] if 0 <= batch < len(_ECONOMY_BATCHES) else []
    if not bodies:
        return {"status": "noop", "tier": f"economy_b{batch}", "bodies": 0}
    if batch in _economy_running:
        return {"status": "already_running", "tier": f"economy_b{batch}", "bodies": len(bodies)}
    _economy_running.add(batch)
    task = asyncio.create_task(_run_economy_batch_bg(batch, bodies))
    _economy_tasks.add(task)
    task.add_done_callback(_economy_tasks.discard)
    return {"status": "started", "tier": f"economy_b{batch}", "bodies": len(bodies)}


# ---- Commission heavy bulk datasets (weekly) -------------------------------
# The 6 large economy_items sub-types under body_code='commission' that NO other
# cron tier covers. Bulk reference universes (tens-to-hundreds of thousands of
# rows) that move slowly; without this tier they went stale ~2 months (frozen
# since June 2026 until the 17 Aug 2026 general DB update surfaced it). Each
# syncs one at a time via sync_economy --no-bodies (500-row batched commits +
# reconnect-on-drop), so a 100k-row upsert stays gentle on the pooled connection.
_COMMISSION_HEAVY_TYPES: list[str] = [
    "research_project",    # CORDIS Horizon projects (~23k)
    "rasff_notification",  # RASFF food-safety alerts (~32k)
    "state_aid_case",      # DG COMP state-aid cases (~62k)
    "tariff_ruling",       # EBTI binding tariff rulings (~76k; slow EBTI export)
    "tariff_code",         # TARIC tariff codes (~13k)
    "funding_recipient",   # FTS funding recipients (~186k)
]
_commission_heavy_running: set = set()
_commission_heavy_tasks: set = set()


async def _run_commission_heavy_bg() -> None:
    """Run the 6 heavy commission sub-datasets sequentially, fail-soft per type."""
    from datetime import datetime, timezone
    from services.sync.freshness import record_run

    started = datetime.now(timezone.utc)
    results: dict = {}
    ok_count = 0
    first_fail = ""
    try:
        for t in _COMMISSION_HEAVY_TYPES:
            res = await _run_script_async(
                f"commission_{t}", "scripts/sync_economy.py",
                ["--body", "commission", "--type", t, "--no-bodies"], timeout=1800,
            )
            results[t] = res.get("status")
            if res.get("status") == "success":
                ok_count += 1
            elif not first_fail:
                _detail = (res.get("stderr_tail") or res.get("error")
                           or res.get("reason") or f"rc={res.get('returncode')}")
                first_fail = f"{t}: {str(_detail)[:400]}"
        logger.info(f"[CRON] commission-heavy sync complete: {results}")
        db = SessionLocal()
        try:
            record_run(
                db, source_key="cron_dispatch", tier="commission_heavy",
                status=("success" if ok_count else "failed"),
                items_added=ok_count, started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=(None if ok_count else
                       f"{ok_count}/{len(_COMMISSION_HEAVY_TYPES)} types ok; first_fail {first_fail}"),
            )
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[CRON] commission-heavy background run failed: {exc}")
        db = SessionLocal()
        try:
            record_run(
                db, source_key="cron_dispatch", tier="commission_heavy",
                status="failed", error=str(exc)[:500], started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            db.close()
    finally:
        _commission_heavy_running.discard(0)


@router.post("/sync/commission-heavy")
async def cron_sync_commission_heavy(authorization: str = Header(...)):
    """
    Commission heavy bulk datasets (weekly, Sunday 07:00 UTC): the 6 large
    economy_items sub-types under body_code='commission' that no other cron tier
    covers -- CORDIS research projects, RASFF food-safety alerts, DG COMP
    state-aid cases, EBTI tariff rulings, TARIC tariff codes, and FTS funding
    recipients. Bulk reference universes (tens-to-hundreds of thousands of rows)
    that move slowly; without this tier they were frozen ~2 months (stuck since
    June 2026 until the 17 Aug general DB update).

    Runs as a BACKGROUND task (returns immediately) so the dispatcher's HTTP call
    cannot time out. Each sub-type syncs one at a time via sync_economy
    --no-bodies (its own 500-row batched commits + reconnect-on-drop). Records a
    freshness run for /api/sync/health.
    """
    _verify_cron_secret(authorization)
    import asyncio
    if 0 in _commission_heavy_running:
        return {"status": "already_running", "tier": "commission_heavy"}
    _commission_heavy_running.add(0)
    task = asyncio.create_task(_run_commission_heavy_bg())
    _commission_heavy_tasks.add(task)
    task.add_done_callback(_commission_heavy_tasks.discard)
    return {"status": "started", "tier": "commission_heavy", "types": len(_COMMISSION_HEAVY_TYPES)}


# ---- Scraper-health detector (nightly) -------------------------------------
# Runs scripts/scraper_health.py in confirm mode: a DB fetched_at scan narrows to
# stale/empty candidates, then a live ingest-run confirms broken vs cron-gap. Only
# ALERTS when a scraper is BROKEN/ERROR on >= 2 consecutive nightly runs -- a single
# run can trip a source rate-limit and false-positive -- tracked by the
# consecutive_fails counter in scraper_health_state.
# The concurrency guard is a LEASE (a start timestamp), not a boolean.
#
# It used to be `set()` with the release in `_run_scraper_health_bg`'s `finally`.
# On 22 Aug 2026 a run wedged inside the detector, so the `finally` never ran,
# the flag stayed set for the life of the process, and every subsequent nightly
# POST returned "already_running" and wrote nothing. The detector was silent for
# two nights and nothing anywhere said so. A `finally` that lives inside the
# thing that can hang is not a release mechanism.
#
# A lease expires on wall-clock instead, so a wedged run self-heals on the next
# nightly tick rather than needing a redeploy.
_SCRAPER_HEALTH_DEADLINE_S = 20 * 60   # a healthy confirm run takes ~2.5 min
_SCRAPER_HEALTH_LEASE_S = 40 * 60      # 2x the deadline; the job runs once a day
_scraper_health_started_at: float | None = None
_scraper_health_tasks: set = set()


def _scraper_health_lease_held() -> bool:
    """True only while a run is genuinely in flight and inside its lease."""
    if _scraper_health_started_at is None:
        return False
    return (_time.monotonic() - _scraper_health_started_at) < _SCRAPER_HEALTH_LEASE_S

_SCRAPER_HEALTH_UPSERT = """
    INSERT INTO scraper_health_state
      (body_code, item_type, consecutive_fails, last_status, rows_count, last_parse, detail, last_checked)
    VALUES (:b, :t, :init_cf, :st, :rows, :parse, :detail, now())
    ON CONFLICT (body_code, item_type) DO UPDATE SET
      consecutive_fails = CASE WHEN :is_break
          THEN scraper_health_state.consecutive_fails + 1 ELSE 0 END,
      last_status = EXCLUDED.last_status, rows_count = EXCLUDED.rows_count,
      last_parse = EXCLUDED.last_parse, detail = EXCLUDED.detail, last_checked = now()
    RETURNING consecutive_fails
"""


async def _run_scraper_health_bg() -> None:
    """Run the detector, update consecutive-fail counters, log/record confirmed breaks."""
    global _scraper_health_started_at
    import asyncio as _asyncio
    from datetime import datetime, timezone
    from sqlalchemy import text as _text
    from services.sync.freshness import record_run

    started = datetime.now(timezone.utc)
    confirmed: list[str] = []
    try:
        import scripts.scraper_health as sh
        # confirm mode does blocking live scraper runs -> off the event loop, and
        # under a hard deadline. `to_thread` cannot be cancelled, so on timeout the
        # worker thread is abandoned; that is deliberate and safe. `sh.run` reads
        # DB state up front and closes the connection before the slow part, and
        # all the writing happens HERE, in the caller. An abandoned thread
        # therefore touches nothing -- it just finishes into the void.
        results = await _asyncio.wait_for(
            _asyncio.to_thread(sh.run, "confirm", None),
            timeout=_SCRAPER_HEALTH_DEADLINE_S,
        )
        db = SessionLocal()
        try:
            for r in results:
                is_break = r["cls"] in ("BROKEN", "ERROR")
                cf = db.execute(_text(_SCRAPER_HEALTH_UPSERT), {
                    "b": r["body"], "t": r["type"],
                    "init_cf": 1 if is_break else 0, "is_break": is_break,
                    "st": r["cls"], "rows": r["rows"], "parse": r.get("parse"),
                    "detail": r["detail"],
                }).scalar()
                if is_break and cf and cf >= 2:
                    confirmed.append(f'{r["body"]}/{r["type"]} (x{cf}): {r["detail"]}')
            db.commit()
            record_run(
                db, source_key="cron_dispatch", tier="scraper_health",
                status="success", items_added=len(confirmed), started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=(None if not confirmed else "CONFIRMED BREAKS: " + "; ".join(confirmed[:12])),
            )
        finally:
            db.close()
        if confirmed:
            logger.warning(f"[CRON] scraper-health {len(confirmed)} CONFIRMED break(s): {confirmed}")
        else:
            logger.info(f"[CRON] scraper-health OK ({len(results)} scrapers, no confirmed breaks)")
    except Exception as exc:  # noqa: BLE001 - every failure must leave a trace
        # A failure used to reach only logger.warning, so `sync_runs` had no row
        # and /api/sync/health showed nothing: the run was indistinguishable from
        # a run that never happened. Record it.
        kind = "TIMEOUT" if isinstance(exc, (_asyncio.TimeoutError, TimeoutError)) else type(exc).__name__
        detail = f"{kind}: {str(exc)[:200]}" if str(exc) else kind
        if kind == "TIMEOUT":
            detail = f"TIMEOUT: exceeded {_SCRAPER_HEALTH_DEADLINE_S}s (thread abandoned)"
        logger.warning(f"[CRON] scraper-health run failed: {detail}")
        try:
            db2 = SessionLocal()
            try:
                record_run(
                    db2, source_key="cron_dispatch", tier="scraper_health",
                    status="failed", items_added=0, started_at=started,
                    finished_at=datetime.now(timezone.utc), error=detail,
                )
            finally:
                db2.close()
        except Exception as rec_exc:  # noqa: BLE001
            logger.warning(f"[CRON] scraper-health could not record failure: {rec_exc}")
    finally:
        # Released HERE and, if this coroutine never gets here, by lease expiry
        # in the endpoint. Two independent releases, because one of them lives
        # inside the thing that can hang.
        _scraper_health_started_at = None


@router.post("/scraper-health")
async def cron_scraper_health(authorization: str = Header(...)):
    """
    Scraper-health detector (nightly, 23:00 UTC). Runs scripts/scraper_health.py in
    confirm mode: a fast fetched_at scan narrows to stale/empty candidates, a live
    ingest-run confirms broken vs cron-gap, and a retry filters transient blips.
    Persists a per-(body,item_type) consecutive-fail counter in scraper_health_state
    and logs/records CONFIRMED breaks (BROKEN/ERROR on >= 2 consecutive runs -- a
    single run can trip a source rate-limit). Fire-and-forget background task so the
    dispatcher's HTTP call cannot time out. The result IS now visible in
    /api/sync/health (`scrapers`) -- until 24 Aug 2026 this docstring claimed it
    was while that endpoint iterated a hardcoded ("fast", "warm") and could not
    show it.
    """
    _verify_cron_secret(authorization)
    import asyncio
    global _scraper_health_started_at
    if _scraper_health_lease_held():
        held_s = int(_time.monotonic() - (_scraper_health_started_at or 0))
        return {"status": "already_running", "tier": "scraper_health",
                "held_for_s": held_s}
    # Past the lease, a previous run is presumed wedged: take over rather than
    # decline for ever. Say so, so a recurring takeover is visible as a symptom.
    if _scraper_health_started_at is not None:
        logger.warning(
            "[CRON] scraper-health lease expired after "
            f"{int(_time.monotonic() - _scraper_health_started_at)}s -- previous run "
            "presumed wedged; taking over")
    _scraper_health_started_at = _time.monotonic()
    task = asyncio.create_task(_run_scraper_health_bg())
    _scraper_health_tasks.add(task)
    task.add_done_callback(_scraper_health_tasks.discard)
    return {"status": "started", "tier": "scraper_health"}


@router.post("/sync/weekly")
async def cron_sync_weekly(
    authorization: str = Header(...),
):
    """
    Weekly sync (Sunday 05:00 UTC): FTAs + GIs + cohesion datasets + trade defence + commissioners.

    Cadence: once per week. Slow-moving universes.
    """
    _verify_cron_secret(authorization)
    results = {}

    # ft_participants, derived from the participant payload already stored on
    # ft_funded_projects. Weekly because its source (funded projects) moves
    # slowly, and the whole pass is a re-read of data we hold: no network.
    results["ft_participants"] = await _run_script_async(
        "ft_participants",
        "scripts/derive_ft_participants.py",
        ["--apply"], timeout=1800,
    )
    results["fta"] = await _run_script_async("fta", "scripts/backfill_eu_trade_agreements.py", ["--apply", "--limit", "20"], timeout=1800)
    results["trade_defence"] = await _run_script_async("trade_defence", "scripts/backfill_eu_trade_defence.py", ["--apply", "--limit", "20"], timeout=1800)
    results["gi"] = await _run_script_async("gi", "scripts/backfill_eu_gi.py", ["--apply", "--limit", "50"], timeout=900)
    results["cohesion"] = await _run_script_async("cohesion", "scripts/backfill_eu_cohesion_datasets.py", ["--apply", "--limit", "50"], timeout=900)
    # Per-fund cohesion finance + outcome data backing /api/v2/funding/<fund>[/outcomes].
    results["cohesion_finances"] = await _run_script_async("cohesion_finances", "scripts/backfill_cohesion_finances.py", ["--all", "--apply"], timeout=900)
    results["cohesion_outcomes"] = await _run_script_async("cohesion_outcomes", "scripts/backfill_cohesion_outcomes.py", ["--all", "--apply"], timeout=1800)
    results["eusf"] = await _run_script_async("eusf", "scripts/backfill_eusf.py", ["--apply"], timeout=300)
    results["cap_payments"] = await _run_script_async("cap_payments", "scripts/backfill_cap_payments.py", ["--all", "--apply"], timeout=300)
    results["commissioner_agendas"] = await _run_script_async("commissioner_agendas", "scripts/backfill_commissioner_agenda_bodies.py", ["--apply", "--limit", "50"], timeout=600)

    logger.info(f"[CRON] weekly tier sync complete: {results}")
    return {"status": "success", "tier": "weekly", "results": results}


@router.post("/sync/monthly")
async def cron_sync_monthly(
    authorization: str = Header(...),
):
    """
    Monthly sync (1st of month 02:00 UTC): officials whoiswho + EU Vocabularies releases check.

    Cadence: once per month. Corpora and release cycles.
    """
    _verify_cron_secret(authorization)
    results = {}

    results["officials"] = await _run_script_async("officials", "scripts/backfill_officials_country.py", ["--apply"], timeout=1800)
    results["euvoc_releases"] = await _run_script_async("euvoc_releases", "scripts/check_euvoc_releases.py", [], timeout=600)
    results["authority_labels_freshness"] = await _run_script_async("authority_labels_freshness", "scripts/check_authority_labels_freshness.py", [], timeout=300)

    logger.info(f"[CRON] monthly tier sync complete: {results}")
    return {"status": "success", "tier": "monthly", "results": results}


def _send_staleness_email(stale: list[dict]) -> None:
    """Ping the operator when fast MEUB feeds miss their refresh window."""
    if not stale:
        return
    recipient = settings.ALERT_EMAIL or settings.SMTP_USER
    if not recipient:
        logger.warning("[CRON] Stale feeds but no ALERT_EMAIL/SMTP_USER configured")
        return
    try:
        from services.email_service import EmailService
        rows = "".join(
            f"<li><strong>{s['label']}</strong> — last success: "
            f"{s['last_success_at'] or 'never'}</li>"
            for s in stale
        )
        html = (
            "<p>Heads up — these MEUB feeds have not refreshed within their "
            "window and may be showing stale data:</p>"
            f"<ul>{rows}</ul>"
            "<p>Check the Railway cron logs and the source endpoints.</p>"
        )
        EmailService().send(
            to=recipient,
            subject=f"[Brubru] {len(stale)} MEUB feed(s) went stale",
            html_body=html,
        )
        logger.info("[CRON] Staleness email sent to %s (%d feeds)", recipient, len(stale))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[CRON] Staleness email failed: %s", exc)


@router.post("/heartbeat")
async def cron_heartbeat(authorization: str = Header(...)):
    """Dispatcher liveness ping.

    `scripts/cron_dispatch.py` fires this every hour regardless of which tiers
    run, so `/api/sync/health` can tell whether the hourly Railway cron is
    actually alive (vs the app being up but the cron not scheduled).
    """
    _verify_cron_secret(authorization)
    from services.sync.freshness import record_run
    db = SessionLocal()
    try:
        record_run(db, source_key="cron_dispatch", tier="heartbeat", status="ok", items_added=0)
    finally:
        db.close()
    return {"status": "ok"}


@router.post("/sync/tier/{tier}")
async def cron_sync_tier(
    tier: str,
    authorization: str = Header(...),
):
    """
    Run every MEUB feed registered for a cadence tier, recording freshness.

    Railway cron calls this: `fast` every ~3h (News, My OJ, Votes), `warm`
    every ~6h (Calendar, Transcripts, Lobby Meetings, Parliamentary Questions).
    Each source runs as a fail-soft subprocess; one failure never blocks the
    others. After the `fast` tier, any feed past its staleness window triggers
    an operator email.
    """
    _verify_cron_secret(authorization)

    from datetime import datetime, timezone
    from services.sync.source_registry import sources_for_tier
    from services.sync.freshness import record_run, find_stale

    if tier not in ("fast", "warm"):
        raise HTTPException(status_code=400, detail="tier must be 'fast' or 'warm'")

    specs = sources_for_tier(tier)
    results: dict = {}
    stale: list[dict] = []
    db = SessionLocal()
    try:
        for spec in specs:
            started = datetime.now(timezone.utc)
            res = await _run_script_async(spec.key, spec.script, list(spec.args), timeout=spec.timeout)
            status = res.get("status", "failed")
            err = res.get("stderr_tail") or res.get("error") or res.get("reason")
            record_run(
                db,
                source_key=spec.key,
                tier=tier,
                status=status,
                error=(err if status != "success" else None),
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
            results[spec.key] = status

        if tier == "fast":
            stale = find_stale(db, tier="fast")
            if stale:
                _send_staleness_email(stale)
    finally:
        db.close()

    return {"tier": tier, "ran": results, "stale_fast": [s["key"] for s in stale]}


@router.post("/sync/authority-labels")
async def cron_sync_authority_labels(
    authorization: str = Header(...),
    nal: str = Query(default=None, description="Restrict to one NAL (e.g. corporate-body)"),
    lang: str = Query(default=None, description="Restrict to one language (en|fr|es|ca|it|nl)"),
    limit: int = Query(default=None, ge=1, le=100000, description="Cap concepts per NAL"),
):
    """
    Nightly EU authority-label sync (Phase 1, EU Vocabularies arc).

    Pulls skos:prefLabel + skos:altLabel for the 12 hot NALs in 6 languages
    from the Cellar SPARQL endpoint and upserts into eu_authority_labels.

    Idempotent. Fail-soft: if Cellar returns 5xx for some queries, those
    NAL/lang pairs are skipped and the rest still write. Returns 200 with
    a result summary regardless — this is an internal cron, not a user
    surface, so the operator reads the body to see partial success.

    Recommended Railway cron schedule: 0 3 * * *  (daily 03:00 UTC)
    """
    _verify_cron_secret(authorization)

    try:
        from scripts.sync_eu_authority_labels import run as run_sync

        logger.info(
            f"[CRON] Authority-label sync started (nal={nal or 'all'}, "
            f"lang={lang or 'all'}, limit={limit or 'unlimited'})"
        )

        exit_code = await run_sync(
            nal_filter=nal,
            lang_filter=lang,
            force=False,
            dry_run=False,
            limit=limit,
        )

        # exit_code 0 = full success; 1 = partial (some NAL/lang failed but others wrote)
        status = "success" if exit_code == 0 else "partial"
        logger.info(f"[CRON] Authority-label sync done: status={status}")

        return {
            "status": status,
            "source": "eu_authority_labels",
            "exit_code": exit_code,
        }

    except Exception as e:
        logger.error(f"[CRON] Authority-label sync failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Authority-label sync failed: {str(e)}",
        )


@router.post("/daily-brief")
def cron_daily_brief(
    authorization: str = Header(...),
):
    """
    Scrape EU news, save top headlines, and send daily brief emails.

    Called by Railway cron at 11:00 UTC (12:00 CET) every day.
    Steps: (1) scrape 44 portals, (2) save top 20 to daily_briefs, (3) email all subscribers.
    """
    _verify_cron_secret(authorization)

    import asyncio
    import subprocess
    import sys
    import os

    results = {}

    # Step 1: Scrape EU news and save to daily_briefs table
    try:
        logger.info("[CRON] Daily brief: scraping EU news portals")
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'scrape_eu_news.py')
        proc = subprocess.run(
            [sys.executable, script_path, '--save', '--hours', '24'],
            capture_output=True, text=True, timeout=180,
            cwd=os.path.dirname(script_path),
        )
        if proc.returncode == 0:
            results["scrape"] = {"status": "success", "output": proc.stderr[-500:] if proc.stderr else ""}
            logger.info("[CRON] Daily brief: news scrape complete")
        else:
            results["scrape"] = {"status": "failed", "error": proc.stderr[-300:] if proc.stderr else "Unknown error"}
            logger.error(f"[CRON] Daily brief: scrape failed: {proc.stderr[-200:]}")
    except Exception as e:
        logger.error(f"[CRON] Daily brief: scrape error: {str(e)}")
        results["scrape"] = {"status": "failed", "error": str(e)}

    # Step 2: Send daily brief emails to all subscribers
    db = SessionLocal()
    try:
        from services.daily_brief_email import send_daily_brief_batch

        logger.info("[CRON] Daily brief: sending emails to subscribers")
        email_result = send_daily_brief_batch(db)
        results["email"] = {
            "status": "success",
            "sent": email_result.get("sent", 0),
            "failed": email_result.get("failed", 0),
            "total_recipients": email_result.get("total_recipients", 0),
            "registered_users": email_result.get("registered_users", 0),
            "pre_users": email_result.get("pre_users", 0),
        }
        if email_result.get("error"):
            results["email"]["error"] = email_result["error"]
        logger.info(f"[CRON] Daily brief: emails sent={email_result.get('sent', 0)}/{email_result.get('total_recipients', 0)}")
    except Exception as e:
        logger.error(f"[CRON] Daily brief: email send failed: {str(e)}")
        results["email"] = {"status": "failed", "error": str(e)}
    finally:
        db.close()

    return {"status": "success", "results": results}
