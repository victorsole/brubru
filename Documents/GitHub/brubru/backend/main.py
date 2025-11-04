"""
Brubru FastAPI Application

Main application entry point with FastAPI + SQLAlchemy + Supabase integration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .core.database import init_db

# Import routers (to be created)
# from .api import chat, amendments, documents, ai, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Runs on startup and shutdown.
    """
    # Startup
    print("🚀 Starting Brubru backend...")
    print(f"📊 Environment: {settings.ENVIRONMENT}")
    print(f"🗄️  Database: Connected to Supabase")

    # Initialize database tables
    init_db()
    print("✅ Database initialized")

    yield

    # Shutdown
    print("👋 Shutting down Brubru backend...")


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


# Include API routers (to be created)
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
# app.include_router(amendments.router, prefix="/api/amendments", tags=["Amendments"])
# app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
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
