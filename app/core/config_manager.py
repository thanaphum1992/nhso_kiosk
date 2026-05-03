import os
import re
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(os.environ.get("ENV_FILE_PATH", ".env"))

def get_env_values():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    return {
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", ""),
        "HOSXP_DB_URL": os.getenv("HOSXP_DB_URL", ""),
        "NHSO_MODE": os.getenv("NHSO_MODE", "PRD"),
        "NHSO_PRD_URL": os.getenv("NHSO_PRD_URL", ""),
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
