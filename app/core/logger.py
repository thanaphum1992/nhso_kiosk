import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logger() -> logging.Logger:
    app_dir = os.environ.get("APP_DIR")
    if app_dir:
        log_dir = Path(app_dir)
    else:
        # fallback: 3 levels up from this file (app/core/logger.py → project root)
        log_dir = Path(__file__).parent.parent.parent
    log_path = log_dir / "nhso_kiosk.log"

    logger = logging.getLogger("nhso_kiosk")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler — rotate ที่ 5MB เก็บ 3 ไฟล์
    fh = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"Logger initialized → {log_path}")
    return logger

logger = setup_logger()

def mask_cid(cid: str) -> str:
    """แสดง 2 หลักแรก และ 3 หลักสุดท้าย: 1234567890123 → 12xxxxxxxx123"""
    if not cid or len(cid) < 5:
        return "xxxx"
    return cid[:2] + "x" * (len(cid) - 5) + cid[-3:]
