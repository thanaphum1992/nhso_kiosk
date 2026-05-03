from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core import config_manager
from app.core.auth import require_admin
from sqlalchemy import create_engine, text

router = APIRouter()

class AdminCredentials(BaseModel):
    username: str
    new_password: str
    confirm_password: str

class ConfigUpdate(BaseModel):
    HOSXP_DB_URL: str
    NHSO_TOKEN: str
    NHSO_MODE: str = "PRD"
    NHSO_PRD_URL: str
    HOSPITAL_CODE: str
    RECORDER_PID: str
    KIOSK_HOSPITAL_NAME: str = ""
    KIOSK_HOSPITAL_PHONE: str = ""

@router.get("/", dependencies=[Depends(require_admin)])
async def get_config():
    return config_manager.get_env_values()

@router.post("/change-password", dependencies=[Depends(require_admin)])
async def change_password(creds: AdminCredentials):
    if creds.new_password != creds.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if not creds.username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    if not creds.new_password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    try:
        config_manager.update_env_value("ADMIN_USERNAME", creds.username)
        config_manager.update_env_value("ADMIN_PASSWORD", creds.new_password)
        return {"message": "Credentials updated. Please re-login."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update", dependencies=[Depends(require_admin)])
async def update_config(config: ConfigUpdate):
    try:
        data = config.dict()
        for key, value in data.items():
            config_manager.update_env_value(key, value)
        return {"message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-db", dependencies=[Depends(require_admin)])
async def test_db_connection(db_url: str):
    try:
        # Create engine without generic timeout to avoid driver conflicts
        engine = create_engine(db_url)
        
        # Try to connect and execute a simple query
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
            
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        # Provide a cleaner error message
        error_msg = str(e)
        if "Access denied" in error_msg:
            error_msg = "Access denied: Check username/password"
        elif "can't connect to" in error_msg or "not found" in error_msg:
            error_msg = "Could not reach server: Check Host/IP and Port"
            
        return {"status": "error", "message": error_msg}


@router.post("/run-db-setup", dependencies=[Depends(require_admin)])
async def run_db_setup():
    """Run predefined ALTER TABLE migrations on nhso_claim_log."""
    from app.db.database import SessionLocal
    migrations = [
        {
            "name": "Add authen_code column",
            "sql": "ALTER TABLE nhso_claim_log ADD COLUMN IF NOT EXISTS authen_code VARCHAR(50) NULL AFTER transaction_id"
        },
        {
            "name": "Add api_mode column",
            "sql": "ALTER TABLE nhso_claim_log ADD COLUMN IF NOT EXISTS api_mode VARCHAR(5) NULL AFTER error_message"
        },
        {
            "name": "Add dep_code column",
            "sql": "ALTER TABLE nhso_claim_log ADD COLUMN IF NOT EXISTS dep_code VARCHAR(20) NULL AFTER inscl_code"
        },
    ]
    results = []
    db = SessionLocal()
    try:
        for m in migrations:
            try:
                db.execute(text(m["sql"]))
                db.commit()
                results.append({"name": m["name"], "status": "success"})
            except Exception as e:
                db.rollback()
                results.append({"name": m["name"], "status": "error", "detail": str(e)})
        overall = "success" if all(r["status"] == "success" for r in results) else "partial"
        return {"status": overall, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
