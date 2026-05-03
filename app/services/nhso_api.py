import re
import requests
import os
import time
import uuid
import hashlib
import json
import traceback
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import text
from app.models.claim import NHSOClaimDetail, Department
from app.db.database import SessionLocal
from app.core.logger import logger

# Disable SSL warning for verify=False
requests.packages.urllib3.disable_warnings()

class NHSOService:
    def __init__(self):
        load_dotenv(override=True)
        self.mode = os.getenv("NHSO_MODE", "TEST")
        if self.mode == "PRD":
            self.url = os.getenv("NHSO_PRD_URL", "https://nhsoapi.nhso.go.th/nhsoendpoint/api/nhso-claim-detail")
        else:
            self.url = os.getenv("NHSO_TEST_URL", "https://test.nhso.go.th/nhsoendpoint/api/nhso-claim-detail")
            
        self.hcode = os.getenv("HOSPITAL_CODE", "")
        self.source_id = os.getenv("SOURCE_ID") or "BAAC01"
        self.recorder_pid = os.getenv("RECORDER_PID", "")
        
    def hash_cid(self, cid: str) -> str:
        """Hash CID using SHA256 for PDPA compliance."""
        if not cid:
            return ""
        return hashlib.sha256(cid.encode()).hexdigest()

    def check_duplicate(self, vn: str) -> bool:
        """Check if this VN has already been claimed successfully."""
        db = SessionLocal()
        try:
            query = text("SELECT id FROM nhso_claim_log WHERE vn = :vn AND status = 'success' LIMIT 1")
            result = db.execute(query, {"vn": vn}).fetchone()
            return result is not None
        except Exception as e:
            print(f"Check duplicate error: {str(e)}")
            return False
        finally:
            db.close()

    def log_claim(self, vn: str, vstdate: Any, cid: str, status: str,
                  transaction_id: str = None, nhso_status_code: str = None,
                  nhso_response: Any = None, total_amount: float = 0,
                  paid_amount: float = 0, privilege_amount: float = 0,
                  inscl_code: str = None, error_message: str = None,
                  authen_code: str = None, dep_code: str = None):
        """Log claim attempt to nhso_claim_log table."""
        db = SessionLocal()
        try:
            cid_hash = self.hash_cid(cid)
            _cid_pattern = re.compile(r'^\d{13}$')
            safe_response = None
            if nhso_response:
                safe_response = {
                    k: v for k, v in nhso_response.items()
                    if not (isinstance(v, str) and _cid_pattern.match(v))
                }

            query = text("""
                INSERT INTO nhso_claim_log
                (vn, vstdate, cid_hash, status, transaction_id, authen_code, nhso_status_code,
                 nhso_response, total_amount, paid_amount, privilege_amount,
                 inscl_code, dep_code, error_message, api_mode, created_at)
                VALUES
                (:vn, :vstdate, :cid_hash, :status, :transaction_id, :authen_code, :nhso_status_code,
                 :nhso_response, :total_amount, :paid_amount, :privilege_amount,
                 :inscl_code, :dep_code, :error_message, :api_mode, NOW())
            """)

            db.execute(query, {
                "vn": vn,
                "vstdate": vstdate,
                "cid_hash": cid_hash,
                "status": status,
                "transaction_id": transaction_id,
                "authen_code": authen_code,
                "nhso_status_code": nhso_status_code,
                "nhso_response": json.dumps(safe_response) if safe_response else None,
                "total_amount": total_amount,
                "paid_amount": paid_amount,
                "privilege_amount": privilege_amount,
                "inscl_code": inscl_code,
                "dep_code": dep_code,
                "error_message": error_message,
                "api_mode": self.mode
            })
            db.commit()
        except Exception as e:
            print(f"Log claim error: {str(e)}")
            db.rollback()
        finally:
            db.close()

    def check_privilege(self, pid: str, token: str) -> Dict[str, Any]:
        """
        Check patient privilege from NHSO v2 right-search API
        """
        # Base URL from config, but change path to right-search
        base_url = self.url.split('/api/')[0]
        check_url = f"{base_url}/api/v2/right-search"
        
        # Today's date in ISO format as required by API
        check_date = datetime.now().strftime("%Y-%m-%dT00:00:00")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        
        params = {
            "pid": pid,
            "checkDate": check_date
        }
        
        try:
            response = requests.get(
                check_url, 
                params=params, 
                headers=headers, 
                verify=False,
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def send_claim(self, claim_data: NHSOClaimDetail, token: str) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        try:
            if not claim_data.hcode: claim_data.hcode = self.hcode
            if not claim_data.sourceId: claim_data.sourceId = self.source_id
            if not claim_data.transactionId: claim_data.transactionId = self.generate_transaction_id()

            payload = claim_data.model_dump() if hasattr(claim_data, "model_dump") else claim_data.dict()
            safe_payload = {k: ("x"*8 if k == "pid" else v) for k, v in payload.items()}
            logger.debug(f"[NHSO] POST {self.url} payload={json.dumps(safe_payload, ensure_ascii=False)}")

            response = requests.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=30,
                verify=False
            )
            logger.debug(f"[NHSO] HTTP {response.status_code} body={response.text[:500]}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[NHSO] RequestException: {e}\n{traceback.format_exc()}")
            return {"error": f"สปสช. API Error: {str(e)}", "status_code": getattr(e.response, 'status_code', None)}
        except Exception as e:
            logger.error(f"[NHSO] Unexpected error: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}

    def generate_transaction_id(self) -> str:
        unique_no = datetime.now().strftime("%Y%m%d%H%M%S") + str(uuid.uuid4().hex[:6]).upper()
        return f"{self.hcode}{unique_no}"

    @staticmethod
    def datetime_to_ms(dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    @staticmethod
    def get_now_ms() -> int:
        return int(time.time() * 1000)
    
    def map_nhso_inscl(self, pttype: str) -> str:
        """
        Map HOSxP pttype to NHSO standard codes.
        Adjust these pairs to match your hospital's pttype table.
        """
        mapping = {
            "10": "UCS",  # ตัวอย่าง: 10 คือ บัตรทอง
            "20": "OFC",  # ตัวอย่าง: 20 คือ ข้าราชการ
            "30": "SSS",  # ตัวอย่าง: 30 คือ ประกันสังคม
            "40": "LGO",  # ตัวอย่าง: 40 คือ อปท.
            "01": "UCS",
            # เพิ่มรายการ mapping ของโรงพยาบาลคุณที่นี่
        }
        # หากไม่พบใน mapping ให้ส่งค่าเดิมไป หรือส่ง OTH (กรณีจ่ายเงินเอง/อื่นๆ)
        return mapping.get(pttype, "OTH")

    def fetch_data_from_db(self, vn: str) -> Optional[NHSOClaimDetail]:
        db = SessionLocal()
        try:
            # SQL Query เดิม
            query = text("""
                SELECT
                    o.hn, p.cid AS pid, o.vn AS visitNumber, o.pttype AS mainInsclCode,
                    v.income AS totalAmount, v.uc_money AS privilegeAmount, v.rcpt_money AS paidAmount,
                    o.hcode, o.vstdate, o.vsttime, o.main_dep AS depCode
                FROM ovst o
                LEFT JOIN patient p ON p.hn = o.hn
                LEFT JOIN vn_stat v ON v.vn = o.vn
                WHERE o.vn = :vn
            """)
            
            result = db.execute(query, {"vn": vn}).fetchone()
            if not result: return None
            
            res = result._asdict()
            
            # แปลงรหัสสิทธิจาก HOSxP เป็นรหัส สปสช.
            hosxp_pttype = str(res.get('mainInsclCode') or "")
            nhso_inscl = self.map_nhso_inscl(hosxp_pttype)
            
            # Combine Date and Time
            v_date = res.get('vstdate')
            v_time = res.get('vsttime')
            if isinstance(v_time, timedelta): v_time = (datetime.min + v_time).time()
            if not isinstance(v_time, dt_time): v_time = dt_time(0, 0)
            dt_obj = datetime.combine(v_date, v_time) if v_date else datetime.now()
            
            return NHSOClaimDetail(
                hcode=str(res.get('hcode') or self.hcode),
                department=Department(code=str(res.get('depCode') or ""), name=None),
                mainInsclCode=nhso_inscl, # ใช้รหัสที่แปลงแล้ว
                serviceDateTime=self.datetime_to_ms(dt_obj),
                invoiceDateTime=self.get_now_ms(),
                transactionId=self.generate_transaction_id(),
                totalAmount=float(res.get('totalAmount') or 0),
                paidAmount=float(res.get('paidAmount') or 0),
                privilegeAmount=float(res.get('privilegeAmount') or 0),
                claimServiceCode="PG0060001",
                pid=str(res.get('pid') or ""),
                sourceId=self.source_id,
                visitNumber=str(res.get('visitNumber')),
                recorderPid=self.recorder_pid or "1234567890123",
                mobile="",
                tel="",
                reservedId="",
                latitude=0.0,
                longitude=0.0
            )
        except Exception as e:
            logger.error(f"[DB] fetch_data_from_db VN={vn} error: {e}\n{traceback.format_exc()}")
            raise e
        finally:
            db.close()

    def get_claim_log(self, vn: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            q = text("""
                SELECT transaction_id, authen_code FROM nhso_claim_log
                WHERE vn=:vn AND status='success' ORDER BY created_at DESC LIMIT 1
            """)
            row = db.execute(q, {"vn": vn}).fetchone()
            if not row:
                return None
            res = row._asdict() if hasattr(row, '_asdict') else {"transaction_id": row[0], "authen_code": row[1]}
            return {
                "transaction_id": res.get("transaction_id"),
                "authen_code": res.get("authen_code") or "-"
            }
        except Exception as e:
            print(f"Error getting claim log: {e}")
            return None
        finally:
            db.close()

    def get_transaction_id(self, vn: str) -> Optional[str]:
        """ดึงเลข transaction_id ล่าสุดที่สำเร็จของ VN นี้"""
        db = SessionLocal()
        try:
            q = text("SELECT transaction_id FROM nhso_claim_log "
                     "WHERE vn=:vn AND status='success' "
                     "ORDER BY created_at DESC LIMIT 1")
            row = db.execute(q, {"vn": vn}).fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Error getting transaction_id: {e}")
            return None
        finally:
            db.close()

    def get_kiosk_visits(self, cid: str) -> list[NHSOClaimDetail]:
        """Fetch all visits for today by CID for Kiosk."""
        db = SessionLocal()
        try:
            query = text("""
                SELECT
                    o.vn, o.hn, o.pttype, o.hcode, o.main_dep,
                    o.vstdate, o.vsttime,
                    v.income, v.rcpt_money, v.uc_money, v.cid
                FROM vn_stat v
                JOIN ovst o ON o.vn = v.vn
                WHERE v.cid = :cid
                  AND v.vstdate = CURDATE()
                ORDER BY o.vsttime DESC
            """)
            
            results = db.execute(query, {"cid": cid}).fetchall()
            if not results:
                return []
                
            visits = []
            for row in results:
                res = row._asdict()
                vn = res.get('vn')
                
                # Map amounts as requested
                total_amount = float(res.get('income') or 0)
                paid_amount = float(res.get('rcpt_money') or 0)
                privilege_amount = round(total_amount - paid_amount, 3)
                
                # Map NHSO inscl code
                hosxp_pttype = str(res.get('pttype') or "")
                nhso_inscl = self.map_nhso_inscl(hosxp_pttype)
                
                # DateTime handling
                v_date = res.get('vstdate')
                v_time = res.get('vsttime')
                if isinstance(v_time, timedelta): v_time = (datetime.min + v_time).time()
                if not isinstance(v_time, dt_time): v_time = dt_time(0, 0)
                dt_obj = datetime.combine(v_date, v_time) if v_date else datetime.now()
                
                visits.append(NHSOClaimDetail(
                    hcode=str(res.get('hcode') or self.hcode),
                    department=Department(code=str(res.get('main_dep') or ""), name=None),
                    mainInsclCode=nhso_inscl,
                    serviceDateTime=self.datetime_to_ms(dt_obj),
                    invoiceDateTime=self.get_now_ms(),
                    transactionId=self.generate_transaction_id(),
                    totalAmount=total_amount,
                    paidAmount=paid_amount,
                    privilegeAmount=privilege_amount,
                    claimServiceCode="PG0060001",
                    pid=str(res.get('cid') or ""),
                    sourceId=self.source_id,
                    visitNumber=str(vn),
                    recorderPid=self.recorder_pid or "1234567890123"
                ))
            return visits
        except Exception as e:
            logger.error(f"[DB] get_kiosk_visits error: {e}\n{traceback.format_exc()}")
            return []
        finally:
            db.close()
