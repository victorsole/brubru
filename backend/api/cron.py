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

    Runs OEIL + EUR-Lex syncs sequentially.
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

    logger.info(f"[CRON] Combined sync complete: {results}")

    return {"status": "success", "results": results}
