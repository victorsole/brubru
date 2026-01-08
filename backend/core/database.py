"""
Database Configuration

SQLAlchemy setup for Supabase PostgreSQL connection.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from .config import settings


# Create SQLAlchemy engine
# Use NullPool for serverless environments, or QueuePool for long-running servers
# Supabase Session mode has strict connection limits, so we keep pool very small
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool if settings.ENVIRONMENT == "production" else None,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,  # Increased pool size for concurrent requests
    max_overflow=5,  # Allow more overflow connections
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_timeout=30,  # Timeout for getting connection from pool
)

# SessionLocal class for database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for SQLAlchemy models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI routes.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            users = db.query(User).all()
            return users
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    Call this during application startup.
    """
    Base.metadata.create_all(bind=engine)
