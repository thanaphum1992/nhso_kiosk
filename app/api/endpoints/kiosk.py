from fastapi import APIRouter, HTTPException, Header, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.nhso_api import NHSOService
from app.services.card_mock import mock_reader, CardEvent
from app.core.logger import logger
from typing import Optional, List
from datetime import datetime
from functools import lru_cache
import asyncio
import io
import os
import json
import traceback
import re
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

router = APIRouter()
nhso_service = NHSOService()
_subscribers: dict[str, set[asyncio.Queue]] = {}

def _clean_client_id(value: Optional[str]) -> str:
    value = (value or "").strip()
    if not value:
        return "default"
    return re.sub(r"[^A-Za-z0-9_.:-]", "_", value)[:80] or "default"

def _client_id_from_request(request: Request, explicit: Optional[str] = None) -> str:
    if explicit:
        return _clean_client_id(explicit)
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return _clean_client_id(forwarded_for.split(",")[0])
    return _clean_client_id(request.client.host if request.client else None)

async def _broadcast(event, client_id: Optional[str] = None):
    targets = [_clean_client_id(client_id)] if client_id else list(_subscribers.keys())
    for target in targets:
        for q in list(_subscribers.get(target, set())):
            await q.put(event)
_card_reader_instance = None

class ClaimByCidRequest(BaseModel):
    cid: str

class MockCardRequest(BaseModel):
    cid: str
    name_th: str = "ผู้ป่วยทดสอบ"

class RemoteCardRequest(BaseModel):
    cid: str
    client_id: Optional[str] = None
    name_th: str = "ผู้รับบริการ"
    dep_code: Optional[str] = None

# --- Card Reader Lifecycle ---

async def start_card_reader(loop: asyncio.AbstractEventLoop):
    class BroadcastProxy:
        def put_nowait(self, event):
            loop.call_soon_threadsafe(asyncio.ensure_future, _broadcast(event))
        def put(self, event):
            loop.call_soon_threadsafe(asyncio.ensure_future, _broadcast(event))
    proxy = BroadcastProxy()
    global _card_reader_instance
    load_dotenv(override=True)
    use_mock = os.getenv("CARD_READER_MOCK", "false").lower() == "true"
    
    if use_mock:
        mock_reader.start_monitor(proxy, loop)
        _card_reader_instance = mock_reader
        logger.info("[CardReader] Mock mode started")
    else:
        try:
            from app.services.card_reader import ThaiCardReader
            reader = ThaiCardReader()
            if reader.connect():
                reader.start_monitor(proxy, loop)
                logger.info(f"[CardReader] Started — {reader.get_status()}")
            else:
                logger.warning("[CardReader] No reader available — running in degraded mode")
            _card_reader_instance = reader
        except Exception as e:
            logger.error(f"[CardReader] Init failed: {e}\n{traceback.format_exc()}")
            _card_reader_instance = None

async def stop_card_reader():
    if _card_reader_instance:
        _card_reader_instance.stop_monitor()

# --- Internal Logic ---

async def _process_card_async(cid: Optional[str], name_th: Optional[str], token: str, dep_code: Optional[str] = None) -> dict:
    logger.info(f"[Card] Processing CID={'***'+cid[-4:] if cid else 'None'} name={name_th} dep_code={dep_code or 'ALL'}")
    if not cid:
        logger.warning("[Card] CID is None — card read failed")
        return {"status": "db_error", "message_th": "อ่านข้อมูลบัตรไม่ได้ กรุณาลองใหม่หรือติดต่อเจ้าหน้าที่"}
    try:
        visits = nhso_service.get_kiosk_visits(cid)
        if not visits:
            logger.info(f"[Card] No visits today for CID ***{cid[-4:]}")
            return {"status": "no_visit", "message_th": "ไม่พบข้อมูลการเข้ารับบริการวันนี้"}

        # Filter by dep_code ถ้ากำหนดใน config
        if dep_code:
            matched = [v for v in visits if v.department and v.department.code == dep_code]
            if matched:
                logger.info(f"[Card] dep_code={dep_code} matched {len(matched)} visit(s)")
                visits = matched
            else:
                logger.info(f"[Card] dep_code={dep_code} no match — fallback to latest visit")
                visits = visits[:1]

        # ตรวจสิทธิ์สดครั้งเดียวก่อน loop (เพื่อประหยัด API call)
        live_inscl = None
        try:
            priv_res = nhso_service.check_privilege(cid, token)
            funds = priv_res.get("funds") if priv_res else None
            if funds and isinstance(funds, list) and len(funds) > 0:
                live_inscl = funds[0].get("mainInscl", {}).get("id")
                if live_inscl:
                    print(f"[Kiosk] Live Privilege OK: {live_inscl}")
        except Exception as e:
            print(f"[Kiosk] Warning: Live privilege check failed: {e}")

        last_error_result = None

        for claim_detail in visits:
            vn = claim_detail.visitNumber

            # Apply live inscl ถ้ามี
            if live_inscl:
                claim_detail.mainInsclCode = live_inscl

            # ถ้า visit นี้ส่งแล้ว ข้ามไป visit ถัดไป
            if nhso_service.check_duplicate(vn):
                existing_tid = nhso_service.get_transaction_id(vn)
                # ถ้าเป็น visit สุดท้ายและทุก visit already_claimed
                last_error_result = {
                    "status": "already_claimed",
                    "message_th": "ท่านได้รับการบันทึกการใช้สิทธิ์แล้ววันนี้",
                    "transaction_id": existing_tid,
                    "visit_number": vn,
                    "patient_name": name_th or "ผู้รับบริการ",
                    "inscl_code": claim_detail.mainInsclCode,
                    "total_amount": claim_detail.totalAmount,
                    "paid_amount": claim_detail.paidAmount,
                    "privilege_amount": claim_detail.privilegeAmount
                }
                continue

            vstdate = datetime.fromtimestamp(claim_detail.serviceDateTime / 1000).date()
            nhso_res = nhso_service.send_claim(claim_detail, token)
            logger.info(f"[NHSO] VN={vn} response: {json.dumps(nhso_res, ensure_ascii=False)}")

            has_error = nhso_res.get("error") or nhso_res.get("dataError")
            status = "nhso_error" if has_error else "success"
            
            authen_code = nhso_res.get("authenCode") or nhso_res.get("authen_code") or nhso_res.get("claimCode") or None

            nhso_service.log_claim(
                vn=vn, vstdate=vstdate, cid=cid, status=status,
                transaction_id=claim_detail.transactionId,
                nhso_status_code=str(nhso_res.get("responseCode") or nhso_res.get("statusCode") or ""),
                nhso_response=nhso_res,
                total_amount=claim_detail.totalAmount,
                paid_amount=claim_detail.paidAmount,
                privilege_amount=claim_detail.privilegeAmount,
                inscl_code=claim_detail.mainInsclCode,
                error_message=str(has_error) if status == "nhso_error" else None,
                authen_code=authen_code,
                dep_code=claim_detail.department.code if claim_detail.department else None
            )

            if status == "nhso_error":
                logger.error(f"[NHSO] VN={vn} FAILED — error={has_error}")

            if status == "success":
                logger.info(f"[NHSO] VN={vn} SUCCESS — authen={authen_code}")
                return {
                    "status": "success",
                    "message_th": "บันทึกการใช้สิทธิ์เรียบร้อยแล้ว",
                    "transaction_id": claim_detail.transactionId,
                    "authen_code": nhso_res.get("authenCode") or nhso_res.get("authen_code") or "",
                    "patient_name": name_th or "ผู้รับบริการ",
                    "visit_number": vn,
                    "inscl_code": claim_detail.mainInsclCode,
                    "total_amount": claim_detail.totalAmount,
                    "paid_amount": claim_detail.paidAmount,
                    "privilege_amount": claim_detail.privilegeAmount,
                    "nhso_response": nhso_res
                }

            # visit นี้ error บันทึกไว้แล้ว ลอง visit ถัดไป
            last_error_result = {
                "status": "nhso_error",
                "message_th": "ระบบ สปสช. ขัดข้อง กรุณาติดต่อเจ้าหน้าที่",
                "visit_number": vn,
                "nhso_error_detail": str(has_error)
            }

        # ถ้าวน loop ครบแล้วยังไม่ success
        return last_error_result or {"status": "nhso_error", "message_th": "ระบบ สปสช. ขัดข้อง กรุณาติดต่อเจ้าหน้าที่"}
    except Exception as e:
        logger.error(f"[Card] Unhandled exception: {e}\n{traceback.format_exc()}")
        return {"status": "db_error", "message_th": "เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล"}

# --- Endpoints ---

@router.get("/status")
async def get_kiosk_status():
    load_dotenv(override=True)
    status = _card_reader_instance.get_status() if _card_reader_instance else \
             {"available": False, "reader_name": "none", "monitoring": False}
    return {
        "reader_available": status["available"],
        "reader_name": status["reader_name"],
        "monitoring": status["monitoring"],
        "mode": os.getenv("NHSO_MODE", "TEST"),
        "kiosk_mode": os.getenv("KIOSK_MODE", "false").lower() == "true"
    }

@router.get("/stream")
async def kiosk_stream(request: Request, client_id: Optional[str] = Query(None)):
    stream_client_id = _client_id_from_request(request, client_id)
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(stream_client_id, set()).add(q)
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event: CardEvent = await asyncio.wait_for(q.get(), timeout=30.0)
                    if event.type == "insert":
                        yield {"event": "card_detected", "data": json.dumps({"name_th": event.name_th or ""})}
                        if event.result:
                            result = event.result
                        else:
                            yield {"event": "processing", "data": json.dumps({"step": 1, "label": "กำลังค้นหาข้อมูล..."})}
                            token = os.getenv("NHSO_TOKEN", "")
                            result = await _process_card_async(event.cid, event.name_th, token)
                        yield {"event": result["status"], "data": json.dumps(result)}
                    elif event.type == "remove":
                        yield {"event": "card_removed", "data": "{}"}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                except Exception as e:
                    logger.error(f"[SSE] Stream error: {e}\n{traceback.format_exc()}")
                    break
        finally:
            clients = _subscribers.get(stream_client_id)
            if clients:
                clients.discard(q)
                if not clients:
                    _subscribers.pop(stream_client_id, None)
    return EventSourceResponse(event_generator())

@router.post("/dev/mock-card")
async def trigger_mock_card(body: MockCardRequest):
    load_dotenv(override=True)
    if os.getenv("CARD_READER_MOCK", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Mock mode not enabled")
    mock_reader.trigger_insert(body.cid, body.name_th)
    return {"status": "triggered"}

@router.post("/remote-insert")
async def remote_insert(body: RemoteCardRequest, request: Request):
    load_dotenv(override=True)
    client_id = _client_id_from_request(request, body.client_id)
    token = os.getenv("NHSO_TOKEN", "")
    result = await _process_card_async(body.cid, body.name_th, token, dep_code=body.dep_code)
    await _broadcast(CardEvent(type="insert", cid=body.cid, name_th=body.name_th, result=result), client_id)
    return result

@lru_cache(maxsize=64)
def _gtts_bytes(text: str) -> bytes:
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(text=text, lang="th", slow=False).write_to_fp(buf)
    return buf.getvalue()

@router.get("/tts")
async def kiosk_tts(text: str = Query(..., max_length=200)):
    audio = _gtts_bytes(text)
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")

@router.post("/claim-by-cid")
async def claim_by_cid(body: ClaimByCidRequest, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    token = authorization.split(" ")[1] if " " in authorization else authorization
    cid = body.cid
    visits = nhso_service.get_kiosk_visits(cid)
    if not visits:
        return {"status": "not_found", "message": "ไม่พบข้อมูลการรับบริการในวันนี้"}
    results = []
    for claim_detail in visits:
        vn = claim_detail.visitNumber
        vstdate = datetime.fromtimestamp(claim_detail.serviceDateTime / 1000).date()
        if nhso_service.check_duplicate(vn):
            results.append({"vn": vn, "status": "already_claimed", "message": f"Visit {vn} ได้ทำการส่งเคลมสำเร็จไปแล้ว"})
            continue
        nhso_res = nhso_service.send_claim(claim_detail, token)
        has_error = nhso_res.get("error") or nhso_res.get("dataError")
        status = "nhso_error" if has_error else "success"
        error_msg = nhso_res.get("error") if status == "nhso_error" else None
        nhso_status_code = nhso_res.get("responseCode") or nhso_res.get("statusCode")
        
        authen_code = nhso_res.get("authenCode") or nhso_res.get("authen_code") or nhso_res.get("claimCode") or None
        
        nhso_service.log_claim(
            vn=vn, vstdate=vstdate, cid=cid, status=status,
            transaction_id=claim_detail.transactionId,
            nhso_status_code=str(nhso_status_code) if nhso_status_code else None,
            nhso_response=nhso_res,
            total_amount=claim_detail.totalAmount,
            paid_amount=claim_detail.paidAmount,
            privilege_amount=claim_detail.privilegeAmount,
            inscl_code=claim_detail.mainInsclCode,
            error_message=error_msg,
            authen_code=authen_code,
            dep_code=claim_detail.department.code if claim_detail.department else None
        )
        results.append({"vn": vn, "status": status, "nhso_response": nhso_res, "error_message": error_msg})
    return {"status": "completed", "results": results}
