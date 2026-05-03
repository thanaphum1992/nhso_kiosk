from fastapi import APIRouter, HTTPException, Header
from app.models.claim import NHSOClaimDetail
from app.services.nhso_api import NHSOService
from typing import Optional

router = APIRouter()
nhso_service = NHSOService()

@router.post("/send-detail")
async def send_claim_detail(
    claim_detail: NHSOClaimDetail,
    authorization: Optional[str] = Header(None)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    # Extract token from Bearer <token>
    token = authorization.split(" ")[1] if " " in authorization else authorization
    
    result = nhso_service.send_claim(claim_detail, token)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result

@router.get("/check-privilege/{pid}")
async def check_privilege(
    pid: str,
    authorization: Optional[str] = Header(None)
):
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization Header")
        
        token = authorization.split(" ")[1] if " " in authorization else authorization
        result = nhso_service.check_privilege(pid, token)
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/fetch-and-send/{vn}")
async def fetch_and_send_claim(
    vn: str,
    authorization: Optional[str] = Header(None)
):
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization Header")
        
        # 1. Fetch data from HOSxP
        claim_detail = nhso_service.fetch_data_from_db(vn)
        if not claim_detail:
            raise HTTPException(status_code=404, detail=f"VN {vn} not found in database")
        
        # 2. Extract token
        token = authorization.split(" ")[1] if " " in authorization else authorization
        
        # 3. Send to NHSO
        result = nhso_service.send_claim(claim_detail, token)
        
        return {
            "status": "nhso_error" if (result.get("error") or result.get("dataError")) else "success",
            "nhso_response": result,
            "data_sent": claim_detail
        }
    except Exception as e:
        return {
            "status": "system_error",
            "message": str(e)
        }
