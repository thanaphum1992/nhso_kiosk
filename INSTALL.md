# คู่มือติดตั้งระบบ NHSO Authen Kiosk

คู่มือนี้ครอบคลุมการติดตั้ง **Server** (Docker) และ **Local Agent อ่านบัตร** บนเครื่อง kiosk

---

## สารบัญ

- [ภาพรวมระบบ](#ภาพรวมระบบ)
- [ส่วนที่ 1: ติดตั้ง Server (Docker)](#ส่วนที่-1-ติดตั้ง-server-docker)
  - [ความต้องการของระบบ](#ความต้องการของระบบ-server)
  - [ขั้นตอนการติดตั้ง](#ขั้นตอนการติดตั้ง-server)
  - [ตั้งค่าฐานข้อมูล](#ตั้งค่าฐานข้อมูล)
  - [ตั้งค่าผ่านหน้า Admin](#ตั้งค่าผ่านหน้า-admin)
- [ส่วนที่ 2: ติดตั้งตัวอ่านบัตร (Local Agent)](#ส่วนที่-2-ติดตั้งตัวอ่านบัตร-local-agent)
  - [ความต้องการของระบบ](#ความต้องการของระบบ-kiosk)
  - [ติดตั้ง Smart Card Agent](#ติดตั้ง-smart-card-agent-port-8189)
  - [ติดตั้ง NHSO Local Agent](#ติดตั้ง-nhso-local-agent)
  - [ตั้งค่า config.ini](#ตั้งค่า-configini)
  - [เริ่มใช้งาน](#เริ่มใช้งาน-agent)
- [ส่วนที่ 3: ติดตั้งแบบ Desktop App (ทางเลือก)](#ส่วนที่-3-ติดตั้งแบบ-desktop-app-ทางเลือก)
- [การตรวจสอบและแก้ไขปัญหา](#การตรวจสอบและแก้ไขปัญหา)
- [คำสั่งที่ใช้บ่อย](#คำสั่งที่ใช้บ่อย)

---

## ภาพรวมระบบ

ระบบประกอบด้วย 2 ส่วนหลัก:

| ส่วน | ที่ติดตั้ง | หน้าที่ |
|---|---|---|
| **Server** | Linux / Docker | Backend API, เชื่อมต่อฐานข้อมูล HOSxP, ส่งเคลมไป สปสช. |
| **Local Agent** | Windows (เครื่อง kiosk) | อ่านบัตรประชาชน, ส่งข้อมูลไป Server, เปิดหน้า kiosk |

```
เครื่อง kiosk (Windows)                  Server (Docker)
┌────────────────────────┐              ┌───────────────────────┐
│  NHSO SmartCard Agent │              │   FastAPI Backend     │
│  (port 8189)           │              │   (port 8000)         │
│         │              │              │         │             │
│  local_agent.py ───────┼── HTTP POST ─┼──► /api/v1/kiosk/     │
│  (อ่านบัตร → ส่ง CID)  │              │     remote-insert     │
│         │              │              │         │             │
│  Chrome/Edge           │              │   HOSxP DB ◄─────┤    │
│  (เปิด /kiosk)         │              │   NHSO API ──────►    │
└────────────────────────┘              └───────────────────────┘
```

---

## ส่วนที่ 1: ติดตั้ง Server (Docker)

### ความต้องการของระบบ Server

| รายการ | ขั้นต่ำ |
|---|---|
| OS | Linux (Ubuntu 20.04+), Windows (Docker Desktop) |
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| RAM | 2 GB |
| Network | เข้าถึงฐานข้อมูล HOSxP (MySQL) และอินเทอร์เน็ต (NHSO API) |

### ขั้นตอนการติดตั้ง Server

#### 1. Clone repository

```bash
git clone https://github.com/thanaphum1992/nhso_authen_kiosk.git nhso_claim
cd nhso_claim
```

#### 2. สร้างไฟล์ `.env` จากตัวอย่าง

```bash
cp .env.example .env
nano .env
```

ตั้งค่าตัวแปรที่สำคัญ:

```env
# ===== Admin =====
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme                    # เปลี่ยนรหัสผ่านทันทีหลังติดตั้ง

# ===== ฐานข้อมูล HOSxP =====
HOSXP_DB_URL=mysql+pymysql://user:password@DB_HOST:3306/hospink
UPDATE_VISIT_PTTYPE_AUTHEN=true            # เขียน auth_code กลับไป HOSxP

# ===== NHSO API =====
NHSO_MODE=PRD                              # PRD = ส่งจริง, TEST = ทดสอบ
NHSO_TOKEN='xxxxxx-xxxxxx-xxxxxx-xxxx'     # Token ที่ได้รับจาก สปสช.
HOSPITAL_CODE=XXXXX                         # รหัสสถานพยาบาล
SOURCE_ID=XXXXX                             # Source ID
RECORDER_PID=1234567890123                  # เลขบัตรผู้บันทึก

# ===== หน้า Kiosk =====
KIOSK_HOSPITAL_NAME=โรงพยาบาลตัวอย่าง       # ชื่อโรงพยาบาลที่แสดงบนหน้าจอ
KIOSK_HOSPITAL_PHONE=0-XXXX-XXXX           # เบอร์โทรศัพท์
KIOSK_AUTO_RESET_SEC=8                     # เวลารีเซ็ตหน้าจออัตโนมัติ (วินาที)
```

#### 3. Build และ start container

```bash
docker compose up -d --build
```

รอให้ container พร้อมใช้งาน (ประมาณ 15-30 วินาที)

#### 4. ตรวจสอบสถานะ

```bash
docker compose ps
curl http://localhost:8222/api/v1/kiosk/status
```

ควรได้ JSON กลับมา:

```json
{
  "reader_available": false,
  "reader_name": "none",
  "monitoring": false,
  "mode": "PRD",
  "kiosk_mode": true,
  "healthy": true
}
```

### ตั้งค่าฐานข้อมูล

ระบบต้องใช้ตาราง `nhso_claim_log` สำหรับบันทึกผลการส่งเคลม

#### วิธีที่ 1: สร้างผ่านหน้า Admin (แนะนำ)

1. เปิด `http://SERVER_IP:8222/admin`
2. Login ด้วยชื่อผู้ใช้ `admin` และรหัสผ่านที่ตั้งใน `.env`
3. ตั้งค่า Database URL แล้วกด **Test Connection**
4. กด **Run DB Setup** เพื่อสร้างตารางอัตโนมัติ

#### วิธีที่ 2: สร้างตารางด้วยตนเอง

```sql
CREATE TABLE IF NOT EXISTS nhso_claim_log (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    vn               VARCHAR(13)   NOT NULL,
    vstdate          DATE,
    cid_hash         VARCHAR(64),
    status           VARCHAR(20),
    transaction_id   VARCHAR(50),
    authen_code      VARCHAR(50),
    nhso_status_code VARCHAR(10),
    nhso_response    JSON,
    total_amount     DOUBLE        DEFAULT 0,
    paid_amount      DOUBLE        DEFAULT 0,
    privilege_amount DOUBLE        DEFAULT 0,
    inscl_code       VARCHAR(10),
    dep_code         VARCHAR(20),
    error_message    TEXT,
    api_mode         VARCHAR(5),
    created_at       DATETIME      DEFAULT NOW(),
    INDEX idx_vn (vn),
    INDEX idx_created (created_at)
);
```

#### สิทธิ์ DB User (แนะนำ)

สร้าง DB user เฉพาะสำหรับ kiosk และให้สิทธิ์เท่าที่จำเป็น:

```sql
-- สร้าง user สำหรับ kiosk (ตัวอย่าง: nhso_kiosk)
GRANT SELECT ON hospink.ovst TO 'nhso_kiosk'@'%';
GRANT SELECT ON hospink.patient TO 'nhso_kiosk'@'%';
GRANT SELECT ON hospink.vn_stat TO 'nhso_kiosk'@'%';
GRANT SELECT, INSERT ON hospink.nhso_claim_log TO 'nhso_kiosk'@'%';
GRANT UPDATE (auth_code) ON hospink.visit_pttype TO 'nhso_kiosk'@'%';
FLUSH PRIVILEGES;
```

> **หมายเหตุ:** `GRANT UPDATE (auth_code)` ใช้เฉพาะเมื่อเปิด `UPDATE_VISIT_PTTYPE_AUTHEN=true`

### ตั้งค่าผ่านหน้า Admin

| URL | หน้าที่ |
|---|---|
| `http://SERVER_IP:8222/kiosk` | หน้าจอ kiosk สำหรับผู้ป่วย |
| `http://SERVER_IP:8222/admin` | หน้าตั้งค่าระบบ (ต้อง login) |
| `http://SERVER_IP:8222/api/v1/kiosk/status` | API ตรวจสถานะ |

**สิ่งที่ควรทำหลังติดตั้ง:**

1. เปิด `/admin` แล้ว login ด้วย default credentials
2. **เปลี่ยนรหัสผ่านทันที** — ระบบจะบังคับเปลี่ยนหากรหัสยังเป็นค่าเริ่มต้น
3. ตั้งค่า Database URL แล้วทดสอบ connection
4. กด Run DB Setup เพื่อสร้างตาราง
5. ตั้งค่า NHSO Token, Hospital Code, Source ID
6. เลือก NHSO Mode (PRD = ส่งจริง / TEST = ทดสอบ)
7. กด Save

---

## ส่วนที่ 2: ติดตั้งตัวอ่านบัตร (Local Agent)

ส่วนนี้ทำบน **เครื่อง kiosk (Windows)** ที่จะเสียบบัตรประชาชน

### ความต้องการของระบบ kiosk

| รายการ | ขั้นต่ำ |
|---|---|
| OS | Windows 10 / 11 (64-bit) |
| Browser | Google Chrome หรือ Microsoft Edge |
| Network | เข้าถึง Server IP:8222 ได้ |
| Hardware | เครื่องอ่านบัตรสมาร์ทการ์ด (PC/SC compatible) |
| USB | พอร์ต USB สำหรับเครื่องอ่านบัตร |

### ติดตั้ง Smart Card Agent (port 8189)

Smart Card Agent ของ สปสช. (NHSO) เป็นบริการอ่านบัตรประจำตัวประชาชนที่ NHSO Local Agent เรียกใช้ผ่าน port 8189

1. ดาวน์โหลด **Smart Card Agent ของ สปสช.** (v1.2.3 for Windows Production):
   - ลิงก์ดาวน์โหลด: <https://www.nhso.go.th/th/communicate-th/new/2024-10-30-15-39-50/56726-1-agent-version-1-2-3-for-windows-production/file>
   - ติดตั้งตามคู่มือที่มาพร้อมกับไฟล์ดาวน์โหลด
2. เชื่อมต่อเครื่องอ่านบัตรเข้ากับเครื่อง kiosk ผ่าน USB
3. ติดตั้ง Driver ของเครื่องอ่านบัตร (ถ้าจำเป็น)
4. เปิด Smart Card Agent ของ สปสช.
5. ตรวจสอบว่าทำงานอยู่:
   - เปิด browser ไปที่ `http://localhost:8189`
   - ถ้าเห็นหน้า Swagger / API = **พร้อมใช้งาน**
6. ทดสอบอ่านบัตร:
   ```
   http://localhost:8189/api/smartcard/read-card-only?readImageFlag=false
   ```
   ควรได้ JSON ที่มีข้อมูล `pid`, `fname`, `lname` กลับมา

### ติดตั้ง NHSO Local Agent

#### 1. Copy โฟลเดอร์ agent

Copy โฟลเดอร์ `agent_อ่านบัตร` ทั้งหมดไปไว้ที่เครื่อง kiosk เช่น `C:\nhso_agent\`

ไฟล์ที่จำเป็น:

| ไฟล์ | หน้าที่ |
|---|---|
| `local_agent.py` | โปรแกรมหลัก — อ่านบัตรและส่งข้อมูลไป Server |
| `Card_reader_agent.bat` | เปิด browser kiosk + เริ่ม local_agent.py |
| `build_agent.bat` | ดาวน์โหลด Embedded Python + ติดตั้ง packages |
| `config.ini` | ไฟล์ตั้งค่า (สร้างอัตโนมัติครั้งแรก) |
| `python\` | Embedded Python (สร้างโดย build_agent.bat) |

> **สำคัญ:** Copy โฟลเดอร์ **ทั้งหมด** ไม่ใช่แค่ `dist\Card_reader_agent\`

#### 2. ตั้งค่า config.ini

เปิด `config.ini` ในโฟลเดอร์ agent (ถ้ายังไม่มี จะถูกสร้างอัตโนมัติเมื่อเปิด `Card_reader_agent.bat` ครั้งแรก)

```ini
[agent]
server_url = http://192.168.30.200:8222
smartcard_agent_url = http://localhost:8189
client_id =
dep_code =
poll_interval_sec = 0.8
card_settle_delay_sec = 1.5
```

**คำอธิบายแต่ละค่า:**

| ค่า | คำอธิบาย | ค่าเริ่มต้น |
|---|---|---|
| `server_url` | URL ของ Server พร้อม port `8222` | `http://localhost:8222` |
| `smartcard_agent_url` | URL ของ Smart Card Agent สปสช. | `http://localhost:8189` |
| `client_id` | ชื่อเฉพาะเครื่อง kiosk — **เว้นว่าง** จะใช้ชื่อเครื่อง Windows อัตโนมัติ | ชื่อเครื่อง |
| `dep_code` | รหัสแผนกที่ต้องการกรอง (เว้นว่าง = ทุกแผนก) | ว่าง |
| `poll_interval_sec` | ความถี่ตรวจสอบบัตร (วินาที) | `0.8` |
| `card_settle_delay_sec` | เวลารอก่อนอ่านหลังเสียบบัตร (วินาที) | `1.5` |

#### 3. Build Embedded Python

Double-click `build_agent.bat` — script จะทำสิ่งต่อไปนี้:

1. ดาวน์โหลด Python 3.13.3 Embeddable Package
2. Extract ไปที่โฟลเดอร์ `python\`
3. เปิดใช้งาน `site-packages` ในไฟล์ `._pth`
4. ติดตั้ง `pip`
5. ติดตั้ง package `requests`

รอจนเห็นข้อความ `Setup complete.`

#### 4. เริ่มใช้งาน Agent

Double-click `Card_reader_agent.bat` — จะทำสิ่งต่อไปนี้:

1. **สร้าง config.ini** (ถ้ายังไม่มี) พร้อมค่าเริ่มต้น
2. **ตรวจสอบ Embedded Python** — ถ้าไม่มีจะเรียก `build_agent.bat` อัตโนมัติ
3. **เปิด browser** ไปที่ `http://SERVER_IP:8222/kiosk?client_id=DESKTOP-XXXX` (Chrome/Edge)
4. **เริ่ม local_agent.py** — อ่านบัตรแบบ polling ทุก 0.8 วินาที

### การทำงานของ Agent

```
1. local_agent.py ตรวจว่ามีบัตรเสียบอยู่หรือไม่ (ทุก 0.8 วินาที)
2. เมื่อพบบัตร → รอ 1.5 วินาที (settle delay) → อ่านข้อมูลบัตร
3. อ่าน CID + ชื่อ → POST ไป Server ที่ /api/v1/kiosk/remote-insert
4. Server รับข้อมูล → ค้นหา visit วันนี้ → ส่งเคลม สปสช. → ส่งผลกลับ
5. หน้าจอ kiosk แสดงผลผ่าน SSE stream
6. เมื่อดึงบัตรออก → รีเซ็ตหน้าจอรอผู้ป่วยคนถัดไป
```

### ตั้งค่า client_id สำหรับหลายเครื่อง

เมื่อมี kiosk หลายเครื่อง แต่ละเครื่องต้องมี `client_id` ที่ไม่ซ้ำกัน เพื่อป้องกันข้อมูลบัตรแสดงผิดจอ

**เครื่อง A:**
```ini
# config.ini
client_id = ER-01
```
Browser จะเปิด: `http://SERVER_IP:8222/kiosk?client_id=ER-01`

**เครื่อง B:**
```ini
# config.ini
client_id = OPD-02
```
Browser จะเปิด: `http://SERVER_IP:8222/kiosk?client_id=OPD-02`

> **สำคัญ:** `client_id` ใน `config.ini` ต้องตรงกับ `?client_id=` ใน URL เสมอ — `Card_reader_agent.bat` จัดการให้อัตโนมัติ

### การตั้งค่า dep_code (กรองแผนก)

ถ้าต้องการให้ kiosk ส่งเคลมเฉพาะ visit ของแผนกใดแผนกหนึ่ง:

```ini
[agent]
dep_code = ER
```

- ถ้ามี visit ของแผนก `ER` → ส่งเคลมเฉพาะ visit นั้น
- ถ้าไม่มี visit ของแผนก `ER` → fallback ส่งเคลม visit ล่าสุดของทุกแผนก
- ถ้าเว้นว่าง → ส่งเคลมทุก visit วันนี้

---

## ส่วนที่ 3: ติดตั้งแบบ Desktop App (ทางเลือก)

สำหรับกรณีที่ต้องการติดตั้งเป็นโปรแกรม Desktop บนเครื่องเดียว (ไม่ต้องใช้ Docker)

### ความต้องการ

| รายการ | ขั้นต่ำ |
|---|---|
| OS | Windows 10/11 (64-bit) |
| Python | 3.11+ |
| Node.js | 18+ |
| Machine | เครื่องอ่านบัตร PC/SC (ต่อกับเครื่องเดียวกัน) |

### ขั้นตอน

#### 1. ติดตั้ง Backend dependencies

```bash
pip install -r requirements.txt
```

#### 2. ติดตั้ง Frontend dependencies

```bash
npm install
```

#### 3. สร้างไฟล์ `.env`

```bash
copy .env.example .env
```

แก้ไขค่าตาม [ขั้นตอนการตั้งค่า](#ตั้งค่าผ่านหน้า-admin)

#### 4. รันโปรแกรม (Development)

```bash
npm start
```

จะเปิด Electron window พร้อม Backend ที่รันอยู่ภายใน

#### 5. Build เป็น Installer

```bash
npm run dist
```

จะได้ไฟล์ติดตั้ง `.exe` ในโฟลเดอร์ `dist_electron\`

---

## การตรวจสอบและแก้ไขปัญหา

### ตรวจสอบ Server

| อาการ | ตรวจสอบ | วิธีแก้ |
|---|---|---|
| Container ไม่ start | `docker compose logs` | ดู log ว่ามี error อะไร |
| Healthcheck fail | `curl http://localhost:8222/api/v1/kiosk/status` | ตรวจว่า DB URL ถูกต้อง |
| เข้า admin ไม่ได้ | ลองเข้า `/admin` | ใช้ default `admin` / `changeme` แล้วเปลี่ยนรหัส |
| ส่งเคลม error | ดู log ใน `logs/nhso_kiosk.log` | ตรวจ NHSO Token และ Hospital Code |
| DB connect ไม่ได้ | ทดสอบผ่าน admin → Test Connection | ตรวจ HOSXP_DB_URL, firewall |

### ตรวจสอบ Local Agent

| อาการ | ตรวจสอบ | วิธีแก้ |
|---|---|---|
| `Smart Card Agent unreachable` | เปิด `http://localhost:8189` | เริ่ม Smart Card Agent ของ สปสช. |
| `Cannot connect to server` | `ping SERVER_IP` | ตรวจ server_url ใน config.ini, firewall |
| อ่านบัตรไม่ได้ | ทดสอบ `http://localhost:8189/api/smartcard/read-card-only` | ตรวจ driver เครื่องอ่านบัตร, เสียบบัตรให้แน่น |
| Browser ไม่เปิด | ดูใน `Card_reader_agent.bat` output | ติดตั้ง Chrome หรือ Edge |
| `python.exe not found` | รัน `build_agent.bat` อีกครั้ง | ตรวจอินเทอร์เน็ต, antivirus block |
| ส่งซ้ำ (duplicate) | ดู log ใน `agent.log` | ระบบมี `_process_lock` ป้องกันอยู่แล้ว — ถ้ายังมีปัญหา ลด `poll_interval_sec` |

### ดู Log

**Server log:**
```bash
# ดู log แบบ realtime
docker compose logs -f nhso-kiosk

# ดู log ไฟล์
cat logs/nhso_kiosk.log
```

**Agent log:**
```
C:\nhso_agent\agent.log
```

---

## คำสั่งที่ใช้บ่อย

### Server (Docker)

```bash
# ดูสถานะ container
docker compose ps

# ดู log แบบ realtime
docker compose logs -f nhso-kiosk

# Restart container (หลังแก้ .env)
docker compose restart

# Rebuild (หลังแก้โค้ด)
docker compose up -d --build

# หยุด container
docker compose down

# หยุดและลบทุกอย่าง
docker compose down -v
```

### Agent (Windows)

```bat
:: เริ่ม agent + เปิด browser
Card_reader_agent.bat

:: สร้าง / rebuild Embedded Python
build_agent.bat

:: หยุด agent
:: กด Ctrl+C ในหน้าต่าง terminal หรือปิดหน้าต่าง
```

### API endpoints สำหรับทดสอบ

```bash
# ตรวจสถานะ
curl http://SERVER_IP:8222/api/v1/kiosk/status

# Mock card (เฉพาะเมื่อ CARD_READER_MOCK=true)
curl -X POST http://SERVER_IP:8222/api/v1/kiosk/dev/mock-card \
  -H "Content-Type: application/json" \
  -d '{"cid":"1234567890123","name_th":"ทดสอบ ระบบ"}'

# ส่งเคลมจาก CID โดยตรง (ต้องมี Bearer token)
curl -X POST http://SERVER_IP:8222/api/v1/kiosk/claim-by-cid \
  -H "Authorization: Bearer YOUR_NHSO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cid":"1234567890123"}'
```

---

## สรุปขั้นตอนติดตั้ง (Quick Start)

```
1. Server
   ├── clone repo → cp .env.example .env → ตั้งค่า
   ├── docker compose up -d --build
   ├── เปิด /admin → เปลี่ยนรหัส → ตั้ง DB → Run DB Setup
   └── curl :8222/api/v1/kiosk/status → ต้องได้ JSON

2. เครื่อง Kiosk
   ├── ติดตั้ง Smart Card Agent → เปิด port 8189
   ├── Copy agent_อ่านบัตร → C:\nhso_agent\
   ├── แก้ config.ini → server_url = http://SERVER_IP:8222
   ├── Double-click build_agent.bat (ครั้งแรก)
   └── Double-click Card_reader_agent.bat → เริ่มใช้งาน
```
