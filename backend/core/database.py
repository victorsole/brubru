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
# Use NullPool for serverless environments (Cloud Run), or QueuePool for long-running servers
# NullPool doesn't support pool-related arguments
if settings.ENVIRONMENT == "production":
    # Serverless: NullPool (no connection pooling, each request gets fresh connection)
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False,  # Disable SQL logging in production
        pool_pre_ping=True,  # Verify connections before using
    )
else:
    # Development: Use connection pooling
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL queries in debug mode
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Pool size for concurrent requests
        max_overflow=5,  # Allow overflow connections
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
