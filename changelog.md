# Changelog

บันทึกการเปลี่ยนแปลงของโปรเจกต์ NHSO Right Close Kiosk  
รูปแบบอ้างอิง [Keep a Changelog](https://keepachangelog.com/th/1.1.0/)

---

## [Unreleased]

### Added
- **Backend — sync `authen_code` กลับ HOSxP**  
  หลัง claim สำเร็จ ระบบจะ `UPDATE visit_pttype.auth_code` โดยเชื่อม `vn` ผ่าน `ovst.pttype` (แถวสิทธิหลัก)  
  - ไฟล์: `app/services/nhso_api.py` — method `update_visit_pttype_auth_code()`  
  - ไฟล์: `app/api/endpoints/kiosk.py` — เรียกหลัง claim สำเร็จใน `_process_card_async` และ `claim-by-cid`  
  - ตัวแปร `.env`: `UPDATE_VISIT_PTTYPE_AUTHEN=true` (default เปิด)  
  - ต้อง `GRANT UPDATE (auth_code) ON visit_pttype` ให้ DB user ก่อนใช้งาน
- **Local Agent — อ่านบัตรผ่าน Smart Card Agent (port 8189)**  
  เปลี่ยนจาก `pythaiidcard` เป็นการ poll `http://localhost:8189/api/smartcard/terminals` แล้วเรียก `read-card-only`  
  - ไฟล์: `agent_อ่านบัตร/local_agent.py`, `local_agent.py` (wrapper)
- **Local Agent — retry และ session handling**  
  รองรับ retry เมื่ออ่านบัตรจาก 8189 หรือ POST ไป server ล้มเหลว โดยไม่ต้องเสียบบัตรใหม่  
  - ค่า config: `RETRY_FAIL_SEC`, `MAX_READ_ATTEMPTS`, `MAX_POST_ATTEMPTS`
- **เอกสารและสคริปต์ทดสอบ agent**  
  - `agent_อ่านบัตร/test_retry_mock.py`, `test_send_once.py`, `test_agent_logic.py`  
  - `agent_อ่านบัตร/ไฟล์ที่ต้อง copy ไปเครื่อง kiosk.md`

### Changed
- **`agent_อ่านบัตร/build_agent.bat`** — ติดตั้งแค่ `requests` (ไม่ใช้ `pyscard` / `pythaiidcard`)
- **`agent_อ่านบัตร/Card_reader_agent.spec`** — ลบ hidden imports ของ pyscard/pythaiidcard
- **`agent_อ่านบัตร/Card_reader_agent.bat`** — เพิ่ม `smartcard_agent_url`, `poll_interval_sec`, `card_settle_delay_sec` ใน config เริ่มต้น และตรวจว่ามี `local_agent.py`
- **`.env.example`** — เพิ่ม `UPDATE_VISIT_PTTYPE_AUTHEN`

### Fixed
- **Local Agent — ไม่ retry หลังอ่านบัตร/POST ล้มเหลว**  
  เดิมตั้ง `_card_present=True` แม้ล้มเหลว ทำให้ต้องถอดบัตรแล้วเสียบใหม่
- **Local Agent — POST ล้มเหลวแล้วไม่ลองส่งซ้ำ**  
  เพิ่ม retry loop ใน `_post_to_server()`
- **`Card_reader_agent.bat`** — config เริ่มต้นขาด `smartcard_agent_url` และค่า poll interval

### Database (ต้องรันที่ server โรงพยาบาล)
```sql
-- สิทธิ DB user สำหรับ kiosk (ตัวอย่าง user: nhso_kiosk)
GRANT SELECT ON hospink.ovst TO 'nhso_kiosk'@'%';
GRANT SELECT ON hospink.patient TO 'nhso_kiosk'@'%';
GRANT SELECT ON hospink.vn_stat TO 'nhso_kiosk'@'%';
GRANT SELECT, INSERT ON hospink.nhso_claim_log TO 'nhso_kiosk'@'%';
GRANT UPDATE (auth_code) ON hospink.visit_pttype TO 'nhso_kiosk'@'%';
FLUSH PRIVILEGES;
```

### Deploy notes
- **Backend (Docker):** `docker compose up -d --build` หลังอัปเดตโค้ด
- **Kiosk client:** copy โฟลเดอร์ `agent_อ่านบัตร/` ไปเครื่อง kiosk — ต้องมี Smart Card Agent รันที่ port 8189
- **คอลัมน์ชื่อไม่เหมือนกัน:** `nhso_claim_log.authen_code` (log) vs `visit_pttype.auth_code` (HOSxP)

---

## [1.0.0] — สถาปัตยกรรม Desktop App

ดูรายละเอียดเพิ่มเติมใน `migration_summary.txt`

### Changed
- เปลี่ยนจาก Web-served UI (FastAPI + Jinja2) เป็น Electron Desktop App
- Python ทำหน้าที่เป็น Local API Server เท่านั้น
- หน้าจอย้ายไป `renderer/` และสื่อสารผ่าน IPC

### Fixed
- บัคใน `main.js` 6 จุด (cwd, port, loadFile path, IPC race, admin window ซ้ำ, electron-is-dev)

---

## วิธีเขียน changelog ครั้งถัดไป

เมื่อมีการแก้ไขโค้ดหรือข้อมูล ให้เพิ่มรายการใต้ `[Unreleased]` ในหมวดที่เหมาะสม:

| หมวด | ใช้เมื่อ |
|------|----------|
| `Added` | ฟีเจอร์ใหม่ |
| `Changed` | เปลี่ยนพฤติกรรมเดิม |
| `Fixed` | แก้บัค |
| `Removed` | ลบฟีเจอร์/ไฟล์ |
| `Database` | SQL migration / GRANT |
| `Deploy notes` | ขั้นตอน deploy ที่ต้องทำเพิ่ม |

เมื่อ release ให้ย้าย `[Unreleased]` ไปเป็นหัวข้อ `[x.y.z] — วันที่` แล้วเปิด `[Unreleased]` ใหม่
