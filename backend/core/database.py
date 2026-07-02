"""
Database Configuration

SQLAlchemy setup for Supabase PostgreSQL connection.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
import logging as _logging
import os as _os

_db_log = _logging.getLogger(__name__)

from .config import settings

# Prod actually runs the `else` (dev) engine branch below: the app-level
# settings.ENVIRONMENT is unset in Railway (only RAILWAY_ENVIRONMENT is set), so
# it defaults to "development" and DEBUG defaults to True. Detect real prod via
# Railway's own var so we can force SQL echo OFF there. `echo=True` sets an
# instance flag (engine._echo) that SQLAlchemy checks as `_echo OR
# logger.isEnabledFor(INFO)` — so it BYPASSES logger levels; the only reliable
# way to silence it is to not set echo=True in the first place (incident 2 Jul).
_RAILWAY_PROD = _os.environ.get("RAILWAY_ENVIRONMENT") == "production"


# Create SQLAlchemy engine
# Use NullPool for serverless environments (Cloud Run), or QueuePool for long-running servers
# NullPool doesn't support pool-related arguments
if settings.ENVIRONMENT == "production":
    # Railway is a LONG-RUNNING server, not serverless. NullPool (the original
    # Cloud Run assumption) opened a fresh DB connection per request, causing
    # per-request connection churn and connection-count spikes toward the DB
    # ceiling under concurrency -> slow/failing logins (incident 2 Jul 2026).
    # Use a bounded QueuePool with connection reuse via the Supabase pooler.
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,  # Disable SQL logging in production
        pool_pre_ping=True,  # Verify connections before using
        pool_size=20,  # Reused connections for concurrent requests
        max_overflow=20,  # Burst headroom
        pool_recycle=300,  # Recycle connections after 5 minutes
        pool_timeout=30,  # Timeout for getting connection from pool
    )
else:
    # Development: Use connection pooling
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG and not _RAILWAY_PROD,  # SQL echo in LOCAL dev only; never on Railway
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Pool size for concurrent requests
        max_overflow=5,  # Allow overflow connections
        pool_recycle=300,  # Recycle connections after 5 minutes
        pool_timeout=30,  # Timeout for getting connection from pool
    )

# Defense-in-depth: with echo now off in prod, statement logging is already
# gated by logger level, so pin the sqlalchemy loggers to WARNING to also mute
# pool checkout/checkin chatter and any stray INFO. App logger.info lines are
# separate loggers and unaffected. (The real SQL-echo fix is echo=... above; a
# logger pin alone can't beat echo=True because engine._echo bypasses levels.)
for _noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    _logging.getLogger(_noisy).setLevel(_logging.WARNING)

# Safety net against leaked sessions: cap idle-in-transaction at 5 minutes at the
# Postgres level, so any connection whose session is never committed/closed (a
# leaked `SessionLocal()` somewhere) is auto-terminated rather than holding locks
# for hours (which previously blocked DDL/migrations and exhausted the pool).
# Supabase's session pooler keeps this SET for the connection's life. Idle-IN-
# TRANSACTION only — normal idle pooled connections are unaffected.
@event.listens_for(engine, "connect")
def _set_idle_in_transaction_timeout(dbapi_conn, _conn_record):
    try:
        cur = dbapi_conn.cursor()
        cur.execute("SET idle_in_transaction_session_timeout = '300000'")  # 5 min
        cur.close()
    except Exception as exc:  # never block a connection over this
        _db_log.warning("could not set idle_in_transaction_session_timeout: %s", exc)


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
