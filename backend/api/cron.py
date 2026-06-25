"""
Cron Job Endpoints

Internal endpoints for scheduled data synchronisation tasks.
Authenticated via CRON_SECRET header, not user JWT.

Railway cron service calls these endpoints on a schedule.
"""

import logging
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
    results["texts_submitted"] = _run_script("texts_submitted", "scripts/ingest_texts_submitted.py", ["--apply"], timeout=600)
    results["college_agendas"] = _run_script("college_agendas", "scripts/sync_college_agendas.py", [], timeout=600)
    results["calendar"] = _run_script("calendar", "scripts/sync_eu_calendar.py", [], timeout=900)
    results["cellar_recent"] = _run_script("cellar_recent", "scripts/sync_eurlex_via_sparql.py", ["--days", "1", "--apply"], timeout=600)

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
    results["eprs_publications"] = _run_script("eprs_publications", "scripts/sync_eprs_publications.py", ["--days", "3"], timeout=900)
    results["eprs_legislation"] = _run_script("eprs_legislation", "scripts/sync_eprs_legislation_in_progress.py", [], timeout=600)
    results["committee_minutes"] = _run_script("committee_minutes", "scripts/sync_committee_minutes.py", ["--max-pages", "2"], timeout=600)
    results["committee_agendas"] = _run_script("committee_agendas", "scripts/sync_committee_agendas.py", [], timeout=600)
    results["committee_transcripts"] = _run_script("committee_transcripts", "scripts/sync_committee_transcripts.py", ["--days", "30", "--max", "50"], timeout=900)
    # Auto-archive items past their lifespan (adopted carriages 90d+, closed
    # consultations 30d+, stale Commission docs 180d+). Idempotent; applies.
    results["auto_archive"] = _run_script("auto_archive", "scripts/auto_archive_old_items.py", [], timeout=300)

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
    result = _run_script(
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

    results["consultations"] = _run_script("consultations", "scripts/sync_consultations.py", [], timeout=900)
    results["comitology"] = _run_script("comitology", "scripts/backfill_eu_comitology.py", ["--apply", "--limit", "100"], timeout=900)
    results["tris"] = _run_script("tris", "scripts/sync_dg_grow.py", ["--source", "tris", "--days", "7"], timeout=600)
    results["sanctions"] = _run_script("sanctions", "scripts/backfill_eu_sanctions.py", ["--apply", "--limit", "100"], timeout=600)
    results["transparency_register"] = _run_script("transparency_register", "scripts/backfill_eu_transparency_register.py", ["--apply", "--limit", "1000"], timeout=900)
    results["jrc"] = _run_script("jrc", "scripts/backfill_eu_jrc_datasets.py", ["--apply", "--max-pages", "5"], timeout=600)
    results["infringements"] = _run_script("infringements", "scripts/backfill_infringement_summary.py", ["--apply", "--limit", "50"], timeout=600)
    results["eesc"] = _run_script("eesc", "scripts/backfill_eu_eesc.py", ["--apply"], timeout=600)
    results["cor"] = _run_script("cor", "scripts/backfill_eu_cor.py", ["--apply"], timeout=600)
    results["euagenda"] = _run_script("euagenda", "scripts/sync_euagenda.py", ["--max", "100"], timeout=600)
    results["tenders"] = _run_script("tenders", "scripts/backfill_tenders_description.py", ["--apply", "--limit", "200"], timeout=900)
    # Per-programme F&T grant calls (economy_items, item_type='grant') backing
    # /api/v2/funding/justice + /innovation-fund. Pulled from SEDIA by topic-id
    # prefix; idempotent upsert on (body_code, item_type, public_url).
    results["ft_programme_calls"] = _run_script("ft_programme_calls", "scripts/ingest_ft_programme_calls.py", ["--all", "--apply"], timeout=900)
    # F&T Portal news + events (economy_items body 'ftportal') backing
    # /api/v2/funding/ft-news + /ft-events. SEDIA news/events indexes.
    results["ft_news_events"] = _run_script("ft_news_events", "scripts/ingest_ft_news_events.py", ["--all", "--apply"], timeout=600)

    # Tenderator translations (MEUB-news pattern, migration 133): detect lang
    # on freshly-arrived TED + F&T rows and translate any foreign-language
    # titles into Brubru's 6 (en/es/ca/fr/it/nl). Idempotent — already-detected
    # rows are skipped. Capped per table per day so a single Railway cron run
    # stays inside the 30-min ceiling (M2M100 on CPU is ~1-3s per translation;
    # 6 langs × 2 fields per foreign row). Cheap (~seconds) when nothing new.
    results["tenderator_translations_ted"] = _run_script(
        "tenderator_translations_ted",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "tenders", "--limit", "100", "--batch", "20"], timeout=900,
    )
    results["tenderator_translations_ft_tenders"] = _run_script(
        "tenderator_translations_ft_tenders",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_calls_for_tenders", "--limit", "50", "--batch", "20"], timeout=600,
    )
    results["tenderator_translations_ft_proposals"] = _run_script(
        "tenderator_translations_ft_proposals",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_calls_for_proposals", "--limit", "50", "--batch", "20"], timeout=600,
    )
    results["tenderator_translations_ft_projects"] = _run_script(
        "tenderator_translations_ft_projects",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "ft_funded_projects", "--limit", "50", "--batch", "20"], timeout=600,
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
    ["acer", "amla", "berec", "cedefop", "council", "cpvo", "eba", "ecb", "ecb_ssm", "ecdc", "echa",
     "cinea", "easa", "ela", "cepol", "eismea", "cdt", "cjeu", "eesc"],
    # batch 1 (15:00 UTC) — Playwright-fed body for this window: europol.
    ["eea", "efca", "efsa", "eib", "eige", "eiopa", "eit", "ema", "enisa", "eppo", "era", "esm", "esma",
     "emsa", "europol", "eacea", "ercea", "epso", "eas", "eca"],
    # batch 2 (21:00 UTC) — Playwright-fed body for this window: eeas.
    ["esrb", "etf", "eu_lisa", "eu_osha", "euaa", "euda", "eurofound", "euipo", "eurojust", "fra", "parliament", "srb",
     "euspa", "frontex", "eeas", "hadea", "rea", "cert_eu"],
]
# Playwright note: cepol/europol/eeas (and the echa-topics + eurofound resources
# already in the batches) render through headless Chromium inside the backend
# container. They are spread one-per-window so at most one Chromium-heavy sync
# runs at 10:00 / 15:00 / 21:00 UTC. If the container OOMs on these, move the
# offending body to a local/manual refresh (drop it from this list).


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

    Cadence: once per day per body. `commission` is excluded (its sources are
    already scheduled via the dedicated daily/weekly backfill scripts).
    """
    _verify_cron_secret(authorization)
    bodies = _ECONOMY_BATCHES[batch] if 0 <= batch < len(_ECONOMY_BATCHES) else []
    results = {}
    for body in bodies:
        results[body] = _run_script(
            f"economy_{body}", "scripts/sync_economy.py",
            ["--body", body, "--type", "all"], timeout=600,
        )

    # Tenderator translations for economy_items funding rows. Runs AFTER all
    # bodies in this batch have synced so any freshly-arrived foreign agency
    # row (DE / PL / SV / etc. — ~8% of the agency-procurement universe) gets
    # its title + summary cached in Brubru's 6 languages by the next read.
    # Capped per batch to stay within the per-batch Railway cron budget.
    results["tenderator_translations_agency"] = _run_script(
        "tenderator_translations_agency",
        "scripts/backfill_tenderator_translations.py",
        ["--table", "economy_items", "--funding-only", "--limit", "100", "--batch", "20"],
        timeout=900,
    )

    logger.info(f"[CRON] economy batch {batch} sync complete: "
                f"{ {k: v.get('status') for k, v in results.items()} }")
    return {"status": "success", "tier": f"economy_b{batch}", "results": results}


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

    results["fta"] = _run_script("fta", "scripts/backfill_eu_trade_agreements.py", ["--apply", "--limit", "20"], timeout=1800)
    results["trade_defence"] = _run_script("trade_defence", "scripts/backfill_eu_trade_defence.py", ["--apply", "--limit", "20"], timeout=1800)
    results["gi"] = _run_script("gi", "scripts/backfill_eu_gi.py", ["--apply", "--limit", "50"], timeout=900)
    results["cohesion"] = _run_script("cohesion", "scripts/backfill_eu_cohesion_datasets.py", ["--apply", "--limit", "50"], timeout=900)
    # Per-fund cohesion finance + outcome data backing /api/v2/funding/<fund>[/outcomes].
    results["cohesion_finances"] = _run_script("cohesion_finances", "scripts/backfill_cohesion_finances.py", ["--all", "--apply"], timeout=900)
    results["cohesion_outcomes"] = _run_script("cohesion_outcomes", "scripts/backfill_cohesion_outcomes.py", ["--all", "--apply"], timeout=1800)
    results["eusf"] = _run_script("eusf", "scripts/backfill_eusf.py", ["--apply"], timeout=300)
    results["cap_payments"] = _run_script("cap_payments", "scripts/backfill_cap_payments.py", ["--all", "--apply"], timeout=300)
    results["commissioner_agendas"] = _run_script("commissioner_agendas", "scripts/backfill_commissioner_agenda_bodies.py", ["--apply", "--limit", "50"], timeout=600)

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

    results["officials"] = _run_script("officials", "scripts/backfill_officials_country.py", ["--apply"], timeout=1800)
    results["euvoc_releases"] = _run_script("euvoc_releases", "scripts/check_euvoc_releases.py", [], timeout=600)
    results["authority_labels_freshness"] = _run_script("authority_labels_freshness", "scripts/check_authority_labels_freshness.py", [], timeout=300)

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
            res = _run_script(spec.key, spec.script, list(spec.args), timeout=spec.timeout)
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
async def cron_daily_brief(
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
