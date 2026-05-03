# NHSO Connect Kiosk — Project Structure

> คู่มือโครงสร้างโปรเจกต์สำหรับนักพัฒนาและผู้ดูแลระบบ

---

## ภาพรวมโฟลเดอร์

```
nhso_claim/                         ← root โปรเจกต์ (Docker / Server version)
│
├── app/                            ← Python FastAPI application
│   ├── main.py                     ← entry point, route /, /kiosk, lifespan
│   ├── api/
│   │   ├── api.py                  ← รวม router ทั้งหมดไว้ที่เดียว
│   │   └── endpoints/
│   │       ├── claim.py            ← API: ส่งเคลม, ตรวจสิทธิ์, fetch-and-send
│   │       ├── config.py           ← API: อ่าน/บันทึก config, test DB, change password
│   │       └── kiosk.py            ← API: SSE stream, card reader, remote-insert, TTS
│   ├── core/
│   │   ├── config_manager.py       ← อ่าน/เขียน .env ด้วย python-dotenv
│   │   └── logger.py               ← rotating file logger (nhso_kiosk.log)
│   ├── db/
│   │   └── database.py             ← SQLAlchemy engine, SessionLocal, get_db()
│   ├── models/
│   │   └── claim.py                ← Pydantic models: NHSOClaimDetail, Department
│   ├── services/
│   │   ├── nhso_api.py             ← NHSOService: send_claim, check_privilege, log_claim
│   │   ├── card_reader.py          ← ThaiCardReader: PC/SC reader (pyscard + pythaiidcard)
│   │   └── card_mock.py            ← MockCardReader: สำหรับ dev/test
│   └── templates/
│       ├── kiosk.html              ← หน้าจอ Kiosk (Tailwind + SSE + TTS)
│       └── index.html              ← หน้า Admin Config (Tailwind + Fetch API)
│
├── renderer/                       ← Electron renderer (Desktop App version เท่านั้น)
│   ├── kiosk.html                  ← Kiosk UI สำหรับ Electron (ใช้ IPC แทน SSE โดยตรง)
│   ├── admin.html                  ← Admin UI สำหรับ Electron
│   └── icon.png                    ← ไอคอน tray
│
├── main.js                         ← Electron main process (Desktop App version)
├── preload.js                      ← Electron preload / contextBridge
├── local_agent.py                  ← Local Agent: อ่านบัตร → ส่ง remote-insert API
│
├── Dockerfile                      ← build Python app เป็น Docker image
├── docker-compose.yml              ← deploy config: port, volume, logging, env
├── requirements.txt                ← Python dependencies
├── .env                            ← secrets จริง (ห้าม commit)
├── .env.example                    ← template สำหรับสร้าง .env ใหม่
├── .dockerignore                   ← ไฟล์ที่ไม่ copy เข้า image
├── package.json                    ← Electron / electron-builder config
│
├── logs/                           ← สร้างอัตโนมัติเมื่อ deploy (mount จาก container)
│   └── nhso_kiosk.log              ← app log (rotate 5 MB × 3 ไฟล์)
│
├── INSTALL.md                      ← คู่มือติดตั้ง (Windows / Linux+Docker / Native)
├── STRUCTURE.md                    ← ไฟล์นี้
└── migration_summary.txt           ← บันทึกการเปลี่ยนสถาปัตยกรรม Electron
```

---

## หน้าที่ของแต่ละไฟล์หลัก

### `app/main.py`
Entry point ของ FastAPI app

| Route | หน้าที่ |
|---|---|
| `GET /` | redirect ไป `/kiosk` |
| `GET /kiosk` | render `kiosk.html` พร้อม hospital_name, client_id |
| `GET /admin/config` | render `index.html` (ต้อง Basic Auth) |
| `GET /api/v1/...` | delegate ไปยัง api_router |

lifespan: start/stop card reader เมื่อ server เริ่ม/หยุด

---

### `app/api/endpoints/claim.py`
API สำหรับเจ้าหน้าที่ / HIS

| Endpoint | หน้าที่ |
|---|---|
| `POST /api/v1/claim/send-detail` | รับ JSON แล้วส่งเคลมไป NHSO โดยตรง |
| `GET /api/v1/claim/check-privilege/{pid}` | ตรวจสิทธิ์ผู้ป่วยจาก NHSO |
| `GET /api/v1/claim/fetch-and-send/{vn}` | ดึงข้อมูลจาก HOSxP แล้วส่งเคลม |

---

### `app/api/endpoints/kiosk.py`
API สำหรับ Kiosk flow

| Endpoint | หน้าที่ |
|---|---|
| `GET /api/v1/kiosk/status` | สถานะ card reader + NHSO mode |
| `GET /api/v1/kiosk/stream?client_id=` | SSE stream — ส่ง event บัตรไปยัง browser |
| `POST /api/v1/kiosk/remote-insert` | รับ CID จาก Local Agent แล้ว process + broadcast |
| `POST /api/v1/kiosk/dev/mock-card` | จำลองเสียบบัตร (เฉพาะ CARD_READER_MOCK=true) |
| `GET /api/v1/kiosk/tts?text=` | text-to-speech ภาษาไทย (gTTS) |
| `POST /api/v1/kiosk/claim-by-cid` | ส่งเคลมตาม CID โดยตรง (ไม่ผ่าน SSE) |

---

### `app/api/endpoints/config.py`
API สำหรับหน้า Admin

| Endpoint | หน้าที่ |
|---|---|
| `GET /api/v1/config/` | อ่านค่า config ปัจจุบันจาก .env |
| `POST /api/v1/config/update` | บันทึก config ลง .env |
| `POST /api/v1/config/test-db` | ทดสอบ DB connection |
| `POST /api/v1/config/change-password` | เปลี่ยนรหัสผ่าน Admin |

---

### `app/services/nhso_api.py`
Business logic หลัก — `NHSOService` class

| Method | หน้าที่ |
|---|---|
| `get_kiosk_visits(cid)` | query HOSxP: visit วันนี้ตาม CID |
| `send_claim(detail, token)` | POST ไป NHSO API |
| `check_privilege(pid, token)` | GET right-search จาก NHSO |
| `check_duplicate(vn)` | ตรวจ nhso_claim_log ว่าเคยส่งสำเร็จแล้วหรือไม่ |
| `log_claim(...)` | INSERT ผลการเคลมลง nhso_claim_log |
| `map_nhso_inscl(pttype)` | แปลง HOSxP pttype → NHSO inscl code |
| `fetch_data_from_db(vn)` | ดึงข้อมูล visit จาก VN (สำหรับ staff API) |

---

### `app/services/card_reader.py` / `card_mock.py`
| Class | หน้าที่ |
|---|---|
| `ThaiCardReader` | อ่านบัตรจริงผ่าน PC/SC (pyscard + pythaiidcard) |
| `MockCardReader` | จำลองการเสียบบัตรผ่าน `POST /dev/mock-card` |

ทั้งคู่ส่ง `CardEvent` เข้า queue → `kiosk.py` broadcast ต่อไปยัง SSE subscribers

---

### `local_agent.py`
รันบน Windows PC ที่ต่อ card reader (แยกจาก server)

```
เสียบบัตร → pyscard detect → pythaiidcard อ่าน CID + ชื่อ
    → POST /api/v1/kiosk/remote-insert {cid, name_th, client_id}
    → server process แล้ว broadcast SSE → browser แสดงผล
```

`client_id` ใช้ `socket.gethostname()` อัตโนมัติ (หรืออ่านจาก `config.ini`)

---

## Kiosk Flow (ภาพรวม)

```
[บัตรประชาชน]
      │
      ▼
[card_reader.py / local_agent.py]  — อ่าน CID + ชื่อ
      │
      ▼
[kiosk.py: _process_card_async()]
      ├─ get_kiosk_visits(cid)        — query HOSxP (vn_stat + ovst)
      ├─ check_privilege(cid, token)  — ตรวจสิทธิ์สดจาก NHSO
      ├─ check_duplicate(vn)          — กันส่งซ้ำ
      ├─ send_claim(detail, token)    — POST → NHSO API
      └─ log_claim(...)               — INSERT nhso_claim_log
      │
      ▼
[SSE broadcast → kiosk.html]        — แสดงผล success / error / already_claimed
      │
      ▼ (auto reset หลัง N วินาที)
[idle screen]
```

---

## Database Tables ที่ใช้

| Table | Database | หน้าที่ |
|---|---|---|
| `ovst` | hospink | ข้อมูล visit (vn, hn, vstdate, pttype, hcode) |
| `vn_stat` | hospink | สรุปการเงิน (income, rcpt_money, cid) |
| `patient` | hospink | ข้อมูลผู้ป่วย (hn → cid) |
| `nhso_claim_log` | hospink | **log การเคลม** — สร้างโดยระบบนี้ |

---

## โฟลเดอร์ Deploy แยกตามการใช้งาน

| โฟลเดอร์ | วัตถุประสงค์ |
|---|---|
| `nhso_claim/` | **Docker / Server** — FastAPI serve web + API บน Ubuntu |
| `renderer/ + main.js` | **Electron Desktop App** — Python เป็น local backend |
| `agent/` | **Local Agent** — รันบน Windows PC ที่ต่อ card reader |
