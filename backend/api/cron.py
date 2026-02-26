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
