"""
Brubru FastAPI Application

Main application entry point with FastAPI + SQLAlchemy + Supabase integration.
Version: 2026.03.06
"""

# Ensure /app is in Python path for Cloud Run deployment
import sys
import os
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from core.database import init_db
from services.rss.rss_scheduler import start_scheduler, stop_scheduler
from services.email_scheduler import start_email_scheduler, stop_email_scheduler
from services.schedulers.amendment_sync_scheduler import (
    start_amendment_sync_scheduler, stop_amendment_sync_scheduler
)

# Import routers
from api import (
    chat, documents, auth, subscriptions, my_eu_bubble, rss_feeds,
    user_documents, legislative_tracking, notifications, export, personalization,
    feedback, admin_panel, admin_api_keys, me_api_keys, billing, mcp_http, mcp_openapi, committees, amendments, legislative_train,
    eu_law_comply, admin_eu_comply, stripe_payment, tenderator, admin_tenders, tender_files, tender_templates,
    user_preferences, admin_analytics, generate, committee_work, public_consultations,
    predictions, texts_adopted, commission_documents, mep_amendments, eu_calendar,
    eprs, cron, preuser_analytics, dg_grow, daily_brief, catalan_translations,
    whatsapp, positions, archive, amendator_examples, public_analytics,
    datasets_dcat, comparator, dashboard, proactive, impact,
    alerts, language_analytics, efpia, ep_votes, oj, eu_news, transcripts,
    parliamentary_questions, lobby_meetings, council_watch, mep_watch, plenary_agenda,
    databases, stakeholders, policy_taxonomy, sync_status,
)
from api.chat_examples import public_router as chat_examples_public_router, admin_router as chat_examples_admin_router
# from api import ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Runs on startup and shutdown.
    """
    # Startup
    print("[START] Starting Brubru backend...")
    print(f"[INFO] Environment: {settings.ENVIRONMENT}")

    # Initialize database tables (non-fatal if fails)
    try:
        init_db()
        print("[OK] Database initialized")
    except Exception as e:
        print(f"[WARN] Database connection failed (non-fatal): {str(e)}")
        print("       The backend will start without database functionality.")

    # Start RSS feed scheduler (for My EU Bubble).
    # It is an AsyncIOScheduler running SYNCHRONOUS feed fetches on the event loop,
    # so each run blocks the single worker and wedges the API (the recurring dev
    # "backend off"). Opt-in via ENABLE_RSS_SCHEDULER=true; OFF by default so dev
    # (and any single-worker deploy) stays responsive. Proper fix TODO: offload the
    # fetch to a thread / run it as a separate process.
    import os as _os
    if _os.getenv("ENABLE_RSS_SCHEDULER", "false").lower() == "true":
        try:
            start_scheduler()
            print("[OK] RSS feed scheduler started")
        except Exception as e:
            print(f"[WARN] RSS scheduler failed to start (non-fatal): {str(e)}")
    else:
        print("[INFO] RSS feed scheduler disabled (set ENABLE_RSS_SCHEDULER=true to enable)")

    # Start email scheduler (weekly re-engagement emails)
    try:
        start_email_scheduler()
        print("[OK] Email scheduler started")
    except Exception as e:
        print(f"[WARN] Email scheduler failed to start (non-fatal): {str(e)}")

    # Start amendment sync scheduler (daily EP Open Data sync)
    try:
        start_amendment_sync_scheduler()
        print("[OK] Amendment sync scheduler started")
    except Exception as e:
        print(f"[WARN] Amendment sync scheduler failed to start (non-fatal): {str(e)}")

    # Connect to MCP Toolbox for Databases (non-fatal if unavailable)
    try:
        from services.toolbox_service import get_toolbox_service
        toolbox = get_toolbox_service()
        await toolbox.connect()
    except Exception as e:
        print(f"[WARN] MCP Toolbox connection failed (non-fatal): {str(e)}")

    yield

    # Shutdown
    print("[STOP] Shutting down Brubru backend...")

    # Close MCP Toolbox connection
    try:
        from services.toolbox_service import get_toolbox_service
        toolbox = get_toolbox_service()
        await toolbox.close()
    except Exception as e:
        print(f"[WARN] MCP Toolbox shutdown error: {str(e)}")

    # Stop RSS feed scheduler
    try:
        stop_scheduler()
        print("[OK] RSS feed scheduler stopped")
    except Exception as e:
        print(f"[WARN] RSS scheduler shutdown error: {str(e)}")

    # Stop email scheduler
    try:
        stop_email_scheduler()
        print("[OK] Email scheduler stopped")
    except Exception as e:
        print(f"[WARN] Email scheduler shutdown error: {str(e)}")

    # Stop amendment sync scheduler
    try:
        stop_amendment_sync_scheduler()
        print("[OK] Amendment sync scheduler stopped")
    except Exception as e:
        print(f"[WARN] Amendment sync scheduler shutdown error: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Brubru API",
    description="AI-powered EU policy intelligence and amendment authoring",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Billing refund middleware (Phase B — refunds 5xx debits on /api/v1/*).
# Must be added AFTER CORS so the refund logic sees the final response.
from api.v1._billing_middleware import BillingRefundMiddleware  # noqa: E402
app.add_middleware(BillingRefundMiddleware)

# Tabular export — ?format=csv|xlsx turns any JSON list response into a CSV/Excel download.
# Added LAST so it is outermost and transforms the FINAL response (after CORS + billing);
# it only acts when the caller sets the format param, so normal traffic is untouched.
from api.export_middleware import TabularExportMiddleware  # noqa: E402
app.add_middleware(TabularExportMiddleware)

# ---------------------------------------------------------------------------
# Brand favicon at the backend origin. MCP hosts (Claude, ChatGPT, Gemini,
# DeepSeek) derive a remote connector's icon from the favicon of the server's
# ORIGIN — i.e. this Railway host, not brubru.beresol.eu. Without this the
# connector shows a generic/Railway icon. Serve the Brubru marks here so any
# host that reads the origin favicon brands the connector as Brubru.
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse  # noqa: E402

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse(
        os.path.join(_STATIC_DIR, "favicon.ico"),
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/favicon.png", include_in_schema=False)
async def favicon_png():
    return FileResponse(
        os.path.join(_STATIC_DIR, "brubru-icon.png"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - API status check"""
    return {
        "status": "ok",
        "service": "Brubru API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "database": "connected",
        "supabase": "connected"
    }


# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(stripe_payment.router, prefix="/api")
app.include_router(chat.router, tags=["Chat"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(my_eu_bubble.router, tags=["My EU Bubble"])
app.include_router(rss_feeds.router, tags=["RSS Feeds"])
app.include_router(user_documents.router, tags=["User Documents"])
app.include_router(legislative_tracking.router, tags=["Legislative Tracking"])
app.include_router(legislative_train.router, tags=["Legislative Train"])
app.include_router(notifications.router, tags=["Notifications"])
app.include_router(export.router, tags=["Data Export"])
app.include_router(personalization.router, prefix="/api", tags=["Personalization"])
app.include_router(feedback.router, tags=["Feedback"])
app.include_router(admin_panel.router, tags=["Admin Panel"])
app.include_router(admin_api_keys.router, tags=["Admin API Keys"])
app.include_router(me_api_keys.router, tags=["Self-Serve API Keys"])
app.include_router(billing.router, tags=["API Billing"])
app.include_router(mcp_http.router, tags=["MCP — HTTP transport"])
app.include_router(mcp_openapi.router, tags=["MCP — OpenAPI for ChatGPT"])
app.include_router(admin_eu_comply.router, prefix="/api/admin/eu-comply", tags=["Admin EU Comply"])
app.include_router(committees.router, tags=["Committees"])
app.include_router(committee_work.router, tags=["Committee Work"])
app.include_router(texts_adopted.router, tags=["Texts Adopted"])
app.include_router(public_consultations.router, tags=["Public Consultations"])
app.include_router(chat_examples_public_router)
app.include_router(chat_examples_admin_router)
app.include_router(amendments.router, tags=["Amendments"])
app.include_router(amendator_examples.router)
app.include_router(datasets_dcat.router, tags=["DCAT-AP Self-Catalogue"])
app.include_router(public_analytics.router)
app.include_router(eu_law_comply.router, prefix="/api", tags=["EU Law Comply"])
app.include_router(comparator.router, tags=["Comparator"])
app.include_router(ep_votes.router, tags=["EP Votes"])
app.include_router(oj.router, tags=["My OJ"])
app.include_router(eu_news.router, tags=["EU News"])
app.include_router(transcripts.router, tags=["Transcripts"])
app.include_router(parliamentary_questions.router, tags=["Parliamentary Questions"])
app.include_router(lobby_meetings.router, tags=["Lobby Meetings"])
app.include_router(council_watch.router, tags=["Council Watch"])
app.include_router(mep_watch.router, tags=["MEP Watch"])
app.include_router(plenary_agenda.router, tags=["EP Plenary Order of Business"])
app.include_router(tenderator.router, tags=["Tenderator"])
app.include_router(tender_files.router, tags=["Tender Docs"])
app.include_router(tender_templates.router, tags=["Tender Docs"])
from api import generate_tender_section as _gen_tender_section
app.include_router(_gen_tender_section.router, tags=["Tender Docs"])
app.include_router(archive.router, tags=["Archive"])
app.include_router(admin_tenders.router, tags=["Admin Tenders"])
app.include_router(user_preferences.router, tags=["User Preferences"])
app.include_router(admin_analytics.router, tags=["Admin Analytics"])
app.include_router(generate.router, tags=["Document Generation"])
app.include_router(predictions.router, tags=["Predictions"])
app.include_router(commission_documents.router, tags=["Commission Documents"])
app.include_router(eprs.router, tags=["EPRS Publications"])
app.include_router(mep_amendments.router, tags=["MEP Amendments"])
app.include_router(eu_calendar.router, tags=["EU Calendar"])
app.include_router(cron.router, tags=["Cron Jobs"])
app.include_router(dg_grow.router, tags=["DG GROW Databases"])
app.include_router(preuser_analytics.router, tags=["Pre-User Analytics"])
app.include_router(daily_brief.router, tags=["Daily Brief"])
app.include_router(efpia.router, tags=["EFPIA"])
app.include_router(catalan_translations.router, tags=["Catalan Translations"])
app.include_router(whatsapp.router, tags=["WhatsApp"])
app.include_router(positions.router, tags=["Position Analysis"])
app.include_router(databases.router, tags=["Brubru Databases"])
app.include_router(stakeholders.router, tags=["Stakeholder Mapping"])
app.include_router(policy_taxonomy.router, prefix="/api", tags=["Policy Taxonomy"])
app.include_router(sync_status.router, prefix="/api", tags=["Sync Status"])
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(proactive.router, tags=["Proactive Chat"])
app.include_router(impact.router, tags=["Personalised Impact"])
app.include_router(alerts.router, tags=["Alerts"])
app.include_router(language_analytics.router, tags=["Language Analytics"])
# app.include_router(ai.router, prefix="/api/ai", tags=["AI Services"])

# Data Provider API v1 (public paid surface, /api/v1/*)
# v1 endpoints + raw /api/v1/openapi.json stay live for existing integrations,
# but the v1 Scalar docs viewer and the /api/docs→v1 alias are retired:
# v2 is now the only public API reference (see below). v1_docs_alias is no
# longer included.
from api.v1 import router as v1_router
from api.v1._errors import register_v1_error_handlers
app.include_router(v1_router)
register_v1_error_handlers(app)  # error envelope covers /api/v1/* AND /api/v2/*

# Data Provider API v2 (institution-based surface, /api/v2/*)
# Reuses the v1 auth/scope/billing dependency, envelope and error handlers.
# v2_docs_alias owns the canonical public docs: /api/docs + /api/openapi.json.
from api.v2 import router as v2_router, docs_alias_router as v2_docs_alias
app.include_router(v2_router)
app.include_router(v2_docs_alias)


@app.middleware("http")
async def _v1_rate_limit_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/v1/", "/api/v2/")):
        limit = getattr(request.state, "rate_limit_limit", None)
        remaining = getattr(request.state, "rate_limit_remaining", None)
        tier = getattr(request.state, "rate_limit_tier", None)
        if limit is not None:
            response.headers["X-RateLimit-Limit"] = str(limit)
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        if tier is not None:
            response.headers["X-RateLimit-Tier"] = tier
        # Attribution headers replace the now-removed envelope `meta` block.
        response.headers["X-Powered-By"] = "Brubru"
        response.headers["X-Source"] = "brubru.beresol.eu"
        # Phase 3 of docs/applications/euvoc.md — declare OP Core conformance.
        response.headers["X-OP-Core-Conformance"] = "v1.0"
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
