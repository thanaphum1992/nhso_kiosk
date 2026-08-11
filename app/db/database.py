from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from typing import Optional
import os
from dotenv import load_dotenv

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        load_dotenv(override=True)
        url = os.getenv("HOSXP_DB_URL")
        if not url:
            raise RuntimeError("HOSXP_DB_URL is not set in .env")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def SessionLocal():
    return _get_session_factory()()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
