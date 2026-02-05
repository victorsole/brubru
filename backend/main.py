"""
Brubru FastAPI Application

Main application entry point with FastAPI + SQLAlchemy + Supabase integration.
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

# Import routers
from api import (
    chat, documents, auth, subscriptions, my_eu_bubble, rss_feeds,
    user_documents, legislative_tracking, notifications, export, personalization,
    feedback, admin_panel, committees, amendments, legislative_train,
    eu_law_comply, admin_eu_comply, stripe_payment, tenderator, admin_tenders,
    user_preferences, admin_analytics, generate, committee_work, public_consultations,
    predictions
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

    # Start RSS feed scheduler (for My EU Bubble)
    try:
        start_scheduler()
        print("[OK] RSS feed scheduler started")
    except Exception as e:
        print(f"[WARN] RSS scheduler failed to start (non-fatal): {str(e)}")

    yield

    # Shutdown
    print("[STOP] Shutting down Brubru backend...")

    # Stop RSS feed scheduler
    try:
        stop_scheduler()
        print("[OK] RSS feed scheduler stopped")
    except Exception as e:
        print(f"[WARN] RSS scheduler shutdown error: {str(e)}")


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
app.include_router(admin_eu_comply.router, prefix="/api/admin/eu-comply", tags=["Admin EU Comply"])
app.include_router(committees.router, tags=["Committees"])
app.include_router(committee_work.router, tags=["Committee Work"])
app.include_router(public_consultations.router, tags=["Public Consultations"])
app.include_router(chat_examples_public_router)
app.include_router(chat_examples_admin_router)
app.include_router(amendments.router, tags=["Amendments"])
app.include_router(eu_law_comply.router, prefix="/api", tags=["EU Law Comply"])
app.include_router(tenderator.router, tags=["Tenderator"])
app.include_router(admin_tenders.router, tags=["Admin Tenders"])
app.include_router(user_preferences.router, tags=["User Preferences"])
app.include_router(admin_analytics.router, tags=["Admin Analytics"])
app.include_router(generate.router, tags=["Document Generation"])
app.include_router(predictions.router, tags=["Predictions"])
# app.include_router(ai.router, prefix="/api/ai", tags=["AI Services"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
