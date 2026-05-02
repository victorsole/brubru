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
