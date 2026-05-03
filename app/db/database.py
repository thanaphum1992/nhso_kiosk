from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Get DB URL from environment
SQLALCHEMY_DATABASE_URL = os.getenv("HOSXP_DB_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("HOSXP_DB_URL is not set in .env")

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
