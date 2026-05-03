# NHSO Authen Kiosk - Project Structure

เอกสารนี้อ้างอิงโครงสร้าง repo ปัจจุบันของ `nhso_claim/`

## โครงสร้างไฟล์

```text
nhso_claim/
├── app/
│   ├── main.py                       # FastAPI entry point: /, /kiosk, /admin
│   ├── api/
│   │   ├── api.py                    # รวม router ภายใต้ /api/v1
│   │   └── endpoints/
│   │       ├── claim.py              # API ส่งเคลม/ตรวจสิทธิ/fetch VN
│   │       ├── config.py             # API config/admin/test DB/setup DB
│   │       └── kiosk.py              # API kiosk/SSE/remote card/TTS
│   ├── core/
│   │   ├── auth.py                   # Basic Auth สำหรับหน้า admin
│   │   ├── config_manager.py         # อ่าน/เขียน .env
│   │   └── logger.py                 # rotating file logger
│   ├── db/
│   │   └── database.py               # SQLAlchemy engine/session
│   ├── models/
│   │   └── claim.py                  # Pydantic models
│   ├── services/
│   │   ├── card_mock.py              # mock card reader สำหรับ dev
│   │   ├── card_reader.py            # PC/SC card reader ฝั่ง server
│   │   └── nhso_api.py               # HOSxP query + NHSO API + claim log
│   └── templates/
│       ├── index.html                # หน้า Admin
│       └── kiosk.html                # หน้า Kiosk web
├── agent/
│   ├── local_agent.py                # Windows Local Agent อ่านบัตรและ POST ไป server
│   ├── build_agent.bat               # setup Embedded Python + packages
│   ├── Card_reader_agent.bat         # เปิด kiosk browser + start agent
│   ├── .gitignore                    # กัน config/runtime/log ของ agent
│   └── ขั้นตอนติดตั้งบนเครื่อง kiosk ใหม่.md
├── renderer/
│   ├── admin.html                    # Electron renderer
│   ├── kiosk.html                    # Electron renderer
│   └── icon.png
├── main.js                           # Electron main process
├── preload.js                        # Electron preload
├── package.json
├── package-lock.json
├── local_agent.py                    # legacy/local copy ของ agent
├── Dockerfile
├── docker-compose.yml                # service nhso-kiosk, host port 8222
├── requirements.txt
├── .env.example
├── .dockerignore
├── .gitignore
├── .gitattributes
├── INSTALL.md
├── STRUCTURE.md
└── migration_summary.txt
```

## ไฟล์ runtime ที่ไม่ควร commit

| Path | เหตุผล |
|---|---|
| `.env` | secrets จริงของ server |
| `logs/`, `*.log` | runtime logs |
| `agent/config.ini` | config เฉพาะเครื่อง client |
| `agent/python/` | Embedded Python และ packages ที่ build แล้ว |
| `node_modules/` | dependency generated จาก npm |
| `__pycache__/`, `*.pyc` | Python cache |

## Server routes

| Route | หน้าที่ |
|---|---|
| `GET /` | redirect ไป `/kiosk` |
| `GET /kiosk` | แสดงหน้า kiosk |
| `GET /admin` | แสดงหน้า admin config และป้องกันด้วย Basic Auth |

## API routes

Base path คือ `/api/v1`

### Claim

| Endpoint | หน้าที่ |
|---|---|
| `POST /api/v1/claim/send-detail` | ส่ง claim detail ไป NHSO โดยตรง |
| `GET /api/v1/claim/check-privilege/{pid}` | ตรวจสิทธิจาก NHSO |
| `GET /api/v1/claim/fetch-and-send/{vn}` | ดึงข้อมูลจาก HOSxP ตาม VN แล้วส่งเคลม |

### Config

| Endpoint | หน้าที่ |
|---|---|
| `GET /api/v1/config/` | อ่าน config ปัจจุบันจาก `.env` |
| `POST /api/v1/config/update` | บันทึก config ลง `.env` |
| `POST /api/v1/config/change-password` | เปลี่ยน admin password |
| `POST /api/v1/config/test-db` | ทดสอบ DB connection |
| `POST /api/v1/config/run-db-setup` | สร้าง/ปรับตาราง `nhso_claim_log` |

### Kiosk

| Endpoint | หน้าที่ |
|---|---|
| `GET /api/v1/kiosk/status` | ตรวจสถานะระบบ |
| `GET /api/v1/kiosk/stream?client_id=...` | SSE stream เฉพาะ client |
| `POST /api/v1/kiosk/remote-insert` | รับข้อมูลบัตรจาก Local Agent |
| `POST /api/v1/kiosk/dev/mock-card` | mock card สำหรับ dev เมื่อเปิด mock mode |
| `GET /api/v1/kiosk/tts` | Thai text-to-speech |
| `POST /api/v1/kiosk/claim-by-cid` | สั่งเคลมจาก CID โดยตรง |

## Flow หลายเครื่อง

```text
Windows Client
  └─ Card_reader_agent.bat
      ├─ เปิด browser: /kiosk?client_id=%COMPUTERNAME%
      └─ local_agent.py อ่านบัตร
          └─ POST /api/v1/kiosk/remote-insert
                { cid, name_th, client_id, dep_code }

FastAPI Server
  └─ kiosk.py
      ├─ query HOSxP visit วันนี้ตาม CID
      ├─ ถ้ามี dep_code จะเลือก visit ของแผนกนั้นก่อน
      ├─ ตรวจสิทธิ/ส่งเคลม NHSO
      ├─ บันทึก nhso_claim_log
      └─ broadcast SSE ไปเฉพาะ browser ที่ client_id ตรงกัน
```

จุดสำคัญคือ `client_id` ของ agent และ URL หน้า kiosk ต้องตรงกัน เพื่อป้องกันกรณีหลายเครื่องเสียบบัตรพร้อมกันแล้วข้อมูลไปแสดงผิดจอ

## Docker deploy

`docker-compose.yml` กำหนด service:

| ค่า | ปัจจุบัน |
|---|---|
| service | `nhso-kiosk` |
| container | `nhso-kiosk` |
| port | `8222:8000` |
| env file | `.env` |
| log volume | `./logs:/app/logs` |
| restart | `unless-stopped` |

URL ใช้งานจากภายนอกจึงเป็น `http://SERVER_IP:8222/...` ส่วน healthcheck ใน container ใช้ `localhost:8000` ได้ถูกต้องแล้ว
