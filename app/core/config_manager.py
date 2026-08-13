import os
import re
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(os.environ.get("ENV_FILE_PATH", ".env"))

def build_db_url():
    """ประกอบ database URL จากตัวแปรแยก เพื่อความปลอดภัย"""
    db_engine = os.getenv("DB_ENGINE", "mysql+pymysql")
    db_user = os.getenv("DB_USER", "")
    db_pass = os.getenv("DB_PASS", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "hospink")
    
    if not db_user or not db_pass:
        return os.getenv("HOSXP_DB_URL", "")
    
    # Encode special characters in password
    encoded_pass = quote_plus(db_pass)
    return f"{db_engine}://{db_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}"

def get_env_values():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    
    # Build DB URL from separate variables
    db_url = build_db_url()
    
    return {
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", ""),
        "HOSXP_DB_URL": db_url,
        "DB_ENGINE": os.getenv("DB_ENGINE", "mysql+pymysql"),
        "DB_USER": os.getenv("DB_USER", ""),
        "DB_PASS": os.getenv("DB_PASS", ""),
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_PORT": os.getenv("DB_PORT", "3306"),
        "DB_NAME": os.getenv("DB_NAME", "hospink"),
        "NHSO_MODE": os.getenv("NHSO_MODE", "PRD"),
        "NHSO_PRD_URL": os.getenv("NHSO_PRD_URL", ""),
        "NHSO_TEST_URL": os.getenv("NHSO_TEST_URL", ""),
        "HOSPITAL_CODE": os.getenv("HOSPITAL_CODE", ""),
        "SOURCE_ID": os.getenv("SOURCE_ID", ""),
        "NHSO_TOKEN": os.getenv("NHSO_TOKEN", ""),
        "RECORDER_PID": os.getenv("RECORDER_PID", ""),
        "KIOSK_MODE": os.getenv("KIOSK_MODE", "false"),
        "CARD_READER_NAME": os.getenv("CARD_READER_NAME", ""),
        "CARD_READER_MOCK": os.getenv("CARD_READER_MOCK", "false"),
        "KIOSK_AUTO_RESET_SEC": os.getenv("KIOSK_AUTO_RESET_SEC", "8"),
        "KIOSK_HOSPITAL_NAME": os.getenv("KIOSK_HOSPITAL_NAME", ""),
        "KIOSK_HOSPITAL_PHONE": os.getenv("KIOSK_HOSPITAL_PHONE", ""),
        "UPDATE_HOSXP_AUTHEN_CODE": os.getenv("UPDATE_HOSXP_AUTHEN_CODE", "true"),
        "NHSO_VERIFY_SSL": os.getenv("NHSO_VERIFY_SSL", "false"),
    }

def update_env_value(key: str, value: str):
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    pattern = re.compile(rf"^{re.escape(key)}\s*=")
    new_line = f"{key}='{value}'"
    updated = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value
    return True
