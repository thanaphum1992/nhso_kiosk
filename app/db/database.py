from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from typing import Optional
import os
from dotenv import load_dotenv
from app.core.config_manager import build_db_url

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        load_dotenv(override=True)
        # Try to build URL from separate variables first, fallback to HOSXP_DB_URL
        url = build_db_url()
        if not url:
            url = os.getenv("HOSXP_DB_URL")
        if not url:
            raise RuntimeError("Database credentials not set. Set DB_USER/DB_PASS or HOSXP_DB_URL in .env")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def SessionLocal():
    return _get_session_factory()()


def reset_engine():
    """Dispose cached engine so the next DB call picks up fresh .env credentials."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
