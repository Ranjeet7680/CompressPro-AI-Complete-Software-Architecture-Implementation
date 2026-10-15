"""
CompressPro AI - Real Database Engine & Session Manager
Supports SQLite (local dev & production portable) and PostgreSQL.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from apps.api.src.db_models import Base, User

# Resolve database URL
is_serverless = os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
if is_serverless:
    DEFAULT_DB_PATH = Path("/tmp/compresspro.db")
else:
    DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "storage_vault" / "compresspro.db"

try:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    DEFAULT_DB_PATH = Path("/tmp/compresspro.db")
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

# Configure engine based on dialect
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Enable SQLite Write-Ahead Logging (WAL) for concurrent reads & writes
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables and seeds the default system guest user."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        guest_user = db.query(User).filter(User.id == "guest_default").first()
        if not guest_user:
            guest_user = User(
                id="guest_default",
                email="guest@compresspro.ai",
                role="guest",
                status="active"
            )
            db.add(guest_user)
            db.commit()


def get_db():
    """FastAPI dependency yielding database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
