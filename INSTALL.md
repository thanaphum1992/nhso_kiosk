# คู่มือติดตั้งระบบ NHSO Kiosk (ปิดสิทธิ์ด้วยบัตรประชาชน)

คู่มือนี้ครอบคลุมการติดตั้ง **Server** (Docker) และ **NHSO Kiosk Agent** (โปรแกรมปิดสิทธิ์บนเครื่อง kiosk)

---

## สารบัญ

- [ภาพรวมระบบ](#ภาพรวมระบบ)
- [ส่วนที่ 1: ติดตั้ง Server (Docker)](#ส่วนที่-1-ติดตั้ง-server-docker)
  - [ความต้องการของระบบ](#ความต้องการของระบบ-server)
  - [ขั้นตอนการติดตั้ง](#ขั้นตอนการติดตั้ง-server)
  - [ตั้งค่าฐานข้อมูล](#ตั้งค่าฐานข้อมูล)
  - [ตั้งค่าผ่านหน้า Admin](#ตั้งค่าผ่านหน้า-admin)
- [ส่วนที่ 2: ติดตั้งโปรแกรมปิดสิทธิ์ (NHSO Kiosk Agent)](#ส่วนที่-2-ติดตั้งโปรแกรมปิดสิทธิ์-nhso-kiosk-agent)
  - [ความต้องการของระบบ](#ความต้องการของระบบ-kiosk)
  - [ติดตั้ง Smart Card Agent](#ติดตั้ง-smart-card-agent-port-8189)
  - [ติดตั้ง NHSO Kiosk Agent](#ติดตั้ง-nhso-kiosk-agent)
  - [ตั้งค่าในหน้าโปรแกรม](#ตั้งค่าในหน้าโปรแกรม)
  - [เริ่มใช้งาน](#เริ่มใช้งาน-agent)
  - [หน้าจอโปรแกรม (Tabs)](#หน้าจอโปรแกรม-tabs)
- [ส่วนที่ 3: ติดตั้งแบบ Desktop App (ทางเลือก)](#ส่วนที่-3-ติดตั้งแบบ-desktop-app-ทางเลือก)
- [การตรวจสอบและแก้ไขปัญหา](#การตรวจสอบและแก้ไขปัญหา)
- [คำสั่งที่ใช้บ่อย](#คำสั่งที่ใช้บ่อย)
- [สรุปขั้นตอนติดตั้ง (Quick Start)](#สรุปขั้นตอนติดตั้ง-quick-start)

---

## ภาพรวมระบบ

ระบบประกอบด้วย 2 ส่วนหลัก:

| ส่วน | ที่ติดตั้ง | หน้าที่ |
|---|---|---|
| **Server** | Linux / Docker | Backend API, เชื่อมต่อฐานข้อมูล HOSxP, ส่งเคลมไป สปสช. |
| **NHSO Kiosk Agent** | Windows (เครื่อง kiosk) | อ่านบัตรประชาชน, ส่งข้อมูลไป Server, เปิดหน้า kiosk |

```
เครื่อง kiosk (Windows)                       Server (Docker)
┌──────────────────────────┐                 ┌───────────────────────┐
│  Smart Card Agent (สปสช.)│                 │   FastAPI Backend     │
│  (port 8189)              │                 │   (port 8222→8000)    │
│         │                 │                 │         │             │
│  NHSO Kiosk Agent (GUI)───┼── HTTP POST ────┼──► /api/v1/kiosk/     │
│  (อ่านบัตร → ส่ง CID)     │                 │     remote-insert     │
│         │                 │                 │         │             │
│  Chrome/Edge (default)    │                 │   HOSxP DB ◄─────┤    │
│  (เปิด /kiosk)            │                 │   NHSO API ──────►    │
└──────────────────────────┘                 └───────────────────────┘
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
git clone https://github.com/thanaphum1992/nhso_kiosk.git nhso_kiosk
cd nhso_kiosk
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

# ===== ฐานข้อมูล HOSxP (แยกตัวแปรเพื่อความปลอดภัย) =====
DB_ENGINE=mysql+pymysql
DB_USER=your_db_username
DB_PASS=your_db_password
DB_HOST=192.168.x.x                        # ห้ามเป็น localhost — ต้องเป็น IP ของ MySQL server จริง
DB_PORT=3306
DB_NAME=hospink

# ===== Options =====
UPDATE_HOSXP_AUTHEN_CODE=true              # เขียน authen_code กลับไป HOSxP หลังเคลมสำเร็จ
KIOSK_AUTO_RESET_SEC=8                     # เวลารีเซ็ตหน้าจออัตโนมัติ (วินาที)
```

ค่าที่เหลือ (NHSO Token, Hospital Code, Source ID, NHSO Mode, ชื่อ/เบอร์โรงพยาบาล) **ตั้งผ่านหน้า Admin หลัง container ขึ้นแล้ว** ไม่ต้องใส่ใน `.env`

> **สำคัญ — `DB_HOST` ห้ามเป็น `localhost`:** เพราะ `localhost` ในมุมมองของ container หมายถึงตัว container เอง ไม่ใช่เครื่อง host หรือ MySQL server จริง ถ้าตั้งผิดจะเจอ error `Can't connect to MySQL server on 'localhost'` และระบบจะเข้าใจผิดว่า "ไม่พบ visit" ทั้งที่จริงคือต่อ DB ไม่ได้

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
3. ตั้งค่า Database (Engine/User/Pass/Host/Port/Name) แล้วกด **Test Connection**
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

-- จำเป็นทั้งคู่เมื่อเปิด UPDATE_HOSXP_AUTHEN_CODE=true:
-- UPDATE (auth_code) สำหรับเขียนค่ากลับ, SELECT (vn, pttype) เพราะ query ใช้ JOIN กับ ovst
GRANT UPDATE (auth_code), SELECT (vn, pttype) ON hospink.visit_pttype TO 'nhso_kiosk'@'%';

FLUSH PRIVILEGES;
```

> **หมายเหตุ:** ถ้า grant แค่ `UPDATE (auth_code)` โดยไม่มี `SELECT (vn, pttype)` ระบบจะส่งเคลมสำเร็จปกติ แต่จะเขียน authen_code กลับ HOSxP ไม่ได้ (เจอ error `SELECT command denied ... for column 'vn'` ใน log) — ต้อง grant ทั้งสองอย่างพร้อมกัน

**ตรวจสอบสิทธิ์ที่มีอยู่จริง** (รันจากในตัว container เพื่อเช็คโดยไม่ต้องรู้รหัสผ่าน):

```bash
docker exec nhso-kiosk python -c "
from app.db.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
for r in db.execute(text('SHOW GRANTS FOR CURRENT_USER')).fetchall():
    print(r[0])
db.close()
"
```

### ตั้งค่าผ่านหน้า Admin

| URL | หน้าที่ |
|---|---|
| `http://SERVER_IP:8222/kiosk` | หน้าจอ kiosk สำหรับผู้ป่วย |
| `http://SERVER_IP:8222/admin` | หน้าตั้งค่าระบบ (ต้อง login) |
| `http://SERVER_IP:8222/api/v1/kiosk/status` | API ตรวจสถานะ |

**สิ่งที่ควรทำหลังติดตั้ง:**

1. เปิด `/admin` แล้ว login ด้วย default credentials
2. **เปลี่ยนรหัสผ่านทันที** — ระบบจะบังคับเปลี่ยนหากรหัสยังเป็นค่าเริ่มต้น
3. ตั้งค่า Database (User/Pass/Host/Port/Name) แล้วกด Test Connection
4. กด Run DB Setup เพื่อสร้างตาราง
5. ตั้งค่า NHSO Token, Hospital Code, Source ID, Recorder PID
6. เลือก NHSO Mode (PRD = ส่งจริง / TEST = ทดสอบ)
7. กด Save — ค่าจะเขียนลง `.env` บนเครื่อง server จริง และมีผลทันที (ไม่ต้อง restart container)

---

## ส่วนที่ 2: ติดตั้งโปรแกรมปิดสิทธิ์ (NHSO Kiosk Agent)

ส่วนนี้ทำบน **เครื่อง kiosk (Windows)** ที่จะเสียบบัตรประชาชน

### ความต้องการของระบบ kiosk

| รายการ | ขั้นต่ำ |
|---|---|
| OS | Windows 10 / 11 (64-bit) |
| Browser | Google Chrome หรือ Microsoft Edge (ตั้งเป็น default browser) |
| Network | เข้าถึง Server IP:8222 ได้ |
| Hardware | เครื่องอ่านบัตรสมาร์ทการ์ด (PC/SC compatible) |
| USB | พอร์ต USB สำหรับเครื่องอ่านบัตร |

### ติดตั้ง Smart Card Agent (port 8189)

Smart Card Agent ของ สปสช. (NHSO) เป็นบริการอ่านบัตรประจำตัวประชาชนที่ NHSO Kiosk Agent เรียกใช้ผ่าน port 8189

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

### ติดตั้ง NHSO Kiosk Agent

โปรแกรมปิดสิทธิ์เป็น **ไฟล์ .exe ไฟล์เดียว** ไม่ต้องติดตั้ง ไม่ต้องพึ่ง Python บนเครื่อง

#### 1. Copy ไฟล์โปรแกรม

Copy ไฟล์ `NHSO_Kiosk_Agent_GUI.exe` (จากโฟลเดอร์ `agent_card_reader\dist\` ในเครื่อง build) ไปไว้ที่เครื่อง kiosk เช่น `C:\nhso_agent\NHSO_Kiosk_Agent_GUI.exe`

> เก็บไว้ในโฟลเดอร์ของตัวเอง (อย่าไว้บน Desktop ปนกับไฟล์อื่น) เพราะโปรแกรมจะสร้าง `config.ini` และ `agent.log` ไว้ **ข้างๆ ตัว .exe เอง**

#### 2. เปิดโปรแกรมครั้งแรก

Double-click `NHSO_Kiosk_Agent_GUI.exe` — โปรแกรมจะ:

1. สร้าง `config.ini` อัตโนมัติ (ถ้ายังไม่มี) พร้อมค่าเริ่มต้น
2. เปิดหน้าต่างโปรแกรม พร้อม 3 แท็บ: **ตั้งค่า**, **สถานะ**, **Log**

### ตั้งค่าในหน้าโปรแกรม

ไปที่แท็บ **⚙ ตั้งค่า** แล้วกรอกค่าต่อไปนี้:

| ช่อง | คำอธิบาย | ค่าเริ่มต้น |
|---|---|---|
| Server URL (kiosk) | URL ของ Server พร้อม port `8222` | `http://localhost:8222` |
| Smart Card Agent URL | URL ของ Smart Card Agent สปสช. | `http://localhost:8189` |
| Client ID (ชื่อเครื่อง) | ชื่อเฉพาะเครื่อง kiosk — **เว้นว่าง** จะใช้ชื่อเครื่อง Windows อัตโนมัติ | ชื่อเครื่อง |
| Dep Code (รหัสแผนก) | รหัสแผนกที่ต้องการกรอง (เว้นว่าง = ทุกแผนก) | ว่าง |
| Poll Interval (วินาที) | ความถี่ตรวจสอบว่ามีบัตรเสียบไหม | `0.8` |
| Settle Delay (วินาที) | เวลารอหลังตรวจพบบัตร ก่อนเริ่มอ่านจริง (รอให้ชิปสัมผัสแนบสนิท) | `1.5` |

แก้ **Server URL** ให้เป็น IP ของ server จริง เช่น `http://192.168.30.200:8222` แล้วกด **💾 บันทึกค่า**

> ถ้า Agent กำลังทำงานอยู่ตอนกดบันทึก โปรแกรมจะ **restart ตัวเองอัตโนมัติ** เพื่อใช้ค่าตั้งใหม่ทันที ไม่ต้องกด หยุด/เริ่ม เอง

### เริ่มใช้งาน Agent

กดปุ่มด้านล่างของหน้าต่าง:

1. **▶ เริ่มอ่านบัตร** — เริ่ม polling เครื่องอ่านบัตรทุก `poll_interval_sec` วินาที
2. **🌐 เปิด Kiosk Browser** — เปิดหน้า `http://SERVER_IP:8222/kiosk?client_id=...` ด้วย browser เริ่มต้นของเครื่อง (ต้องตั้ง Chrome/Edge เป็น default browser ไว้ก่อน)
3. **⏹ หยุด** — หยุด agent (ไม่ปิดโปรแกรม)

### การทำงานของ Agent

```
1. Agent ตรวจว่ามีบัตรเสียบอยู่หรือไม่ (ทุก poll_interval_sec วินาที)
2. เมื่อพบบัตร → รอ card_settle_delay_sec วินาที (settle delay) → อ่านข้อมูลบัตร
3. อ่าน CID + ชื่อ → POST ไป Server ที่ /api/v1/kiosk/remote-insert
4. Server รับข้อมูล → ค้นหา visit วันนี้ → ส่งเคลม สปสช. → เขียน authen_code กลับ HOSxP → ส่งผลกลับ
5. หน้าจอ kiosk แสดงผลผ่าน SSE stream
6. เมื่อดึงบัตรออก → รีเซ็ตหน้าจอรอผู้ป่วยคนถัดไป
```

### หน้าจอโปรแกรม (Tabs)

**⚙ ตั้งค่า** — ตามหัวข้อด้านบน

**📊 สถานะ** — แสดงสถานะแบบ real-time (อัปเดตทุก 5 วินาที หรือกด "ตรวจสอบสถานะเครื่องอ่านบัตร" เพื่อเช็คทันที):

| รายการ | ความหมาย |
|---|---|
| แถบบนขวา (● Smart Card: ...) | 🟢 เชื่อมต่อแล้ว = ต่อ Smart Card Agent ได้ + พบเครื่องอ่านจริง / 🟠 ไม่พบเครื่องอ่านบัตร = ต่อ service ได้แต่ไม่มีเครื่องอ่านเสียบ / 🔴 ขาดการเชื่อมต่อ = ต่อ Smart Card Agent ไม่ได้เลย |
| เครื่องอ่านบัตร | ชื่อรุ่นเครื่องอ่านที่ตรวจพบ |
| สถานะบัตร | มีบัตรเสียบอยู่ / ไม่มีบัตร |
| บัตรล่าสุด | เลขบัตรแบบ mask (เช่น `*********2118`) + เวลา |
| Server ตอบล่าสุด | status ที่ server ตอบกลับ (success / already_claimed / no_visit / nhso_error) + visit number |
| จำนวนบัตรที่ส่งแล้ว | นับจำนวนบัตรที่ส่งไป server สำเร็จตั้งแต่เริ่ม agent |

**📋 Log** — log การทำงานแบบละเอียด (อ่านบัตร, ส่ง server, error) เก็บไฟล์ไว้ที่ `agent.log` ข้างๆ ตัว .exe ด้วย

### ตั้งค่า client_id สำหรับหลายเครื่อง

เมื่อมี kiosk หลายเครื่องเชื่อมกับ server ตัวเดียวกัน แต่ละเครื่องต้องมี `client_id` ที่ไม่ซ้ำกัน เพราะ server ใช้ `client_id` เพื่อ**ส่งผลลัพธ์กลับไปแสดงที่จอที่ถูกต้องเท่านั้น** ถ้าไม่ตั้งให้ไม่ซ้ำ ข้อมูลผู้ป่วยอาจไปแสดงผิดจอ

**เครื่อง A** — ตั้งค่า Client ID = `ER-01` → browser จะเปิด `http://SERVER_IP:8222/kiosk?client_id=ER-01`

**เครื่อง B** — ตั้งค่า Client ID = `OPD-02` → browser จะเปิด `http://SERVER_IP:8222/kiosk?client_id=OPD-02`

> **สำคัญ:** `client_id` ในหน้าตั้งค่าต้องตรงกับ `?client_id=` ที่เปิดใน browser เสมอ — ปุ่ม "เปิด Kiosk Browser" จัดการให้อัตโนมัติจากค่าที่บันทึกไว้

### การตั้งค่า dep_code (กรองแผนก)

ถ้าต้องการให้ kiosk ส่งเคลมเฉพาะ visit ของแผนกใดแผนกหนึ่ง ใส่รหัสแผนกในช่อง **Dep Code**:

- ถ้ามี visit ของแผนกนั้น → ส่งเคลมเฉพาะ visit นั้น
- ถ้าไม่มี visit ของแผนกนั้น → fallback ส่งเคลม visit ล่าสุดของทุกแผนก
- ถ้าเว้นว่าง → ส่งเคลมทุก visit วันนี้

---

## ส่วนที่ 3: ติดตั้งแบบ Desktop App (ทางเลือก)

สำหรับกรณีที่ต้องการติดตั้งเป็นโปรแกรม Desktop บนเครื่องเดียว (Server + Kiosk รวมกัน ไม่ต้องใช้ Docker) — ใช้ Electron ครอบ Backend เดียวกัน

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

จะได้ไฟล์ติดตั้ง `.exe` ในโฟลเดอร์ `dist_electron\` (ครั้งแรกจะดาวน์โหลด Electron binary ~100MB+ ใช้เวลาสักครู่)

---

## การตรวจสอบและแก้ไขปัญหา

### ตรวจสอบ Server

| อาการ | ตรวจสอบ | วิธีแก้ |
|---|---|---|
| Container ไม่ start | `docker compose logs` | ดู log ว่ามี error อะไร |
| Healthcheck fail | `curl http://localhost:8222/api/v1/kiosk/status` | ตรวจว่า DB config ถูกต้อง |
| เข้า admin ไม่ได้ | ลองเข้า `/admin` | ใช้ default `admin` / `changeme` แล้วเปลี่ยนรหัส |
| "ไม่พบ visit" ทั้งที่มี visit จริง | `docker logs nhso-kiosk \| grep '\[DB\]'` | ถ้าเจอ `Can't connect to MySQL server on 'localhost'` แปลว่า `DB_HOST` ยังตั้งเป็น `localhost` อยู่ — ต้องเปลี่ยนเป็น IP จริงของ MySQL |
| ส่งเคลมสำเร็จ แต่ HOSxP ไม่มี authen_code | `docker logs nhso-kiosk \| grep visit_pttype` | ถ้าเจอ `SELECT command denied ... column 'vn'` ต้อง grant `SELECT (vn, pttype)` เพิ่ม (ดู [สิทธิ์ DB User](#สิทธิ์-db-user-แนะนำ)) |
| ตั้งค่าใน Admin แล้วหายหลัง restart | เช็คว่า `docker-compose.yml` มี `- ./.env:/app/.env` ใน `volumes:` | ถ้าไม่มี ให้เพิ่มแล้ว `docker compose up -d --build` ใหม่ — ไม่งั้นค่าที่ Save จะเขียนลงไฟล์ในตัว container ไม่ใช่ไฟล์บน host |
| DB connect ไม่ได้ | ทดสอบผ่าน admin → Test Connection | ตรวจ user/pass/host/port, firewall |

### ตรวจสอบ NHSO Kiosk Agent

| อาการ | ตรวจสอบ | วิธีแก้ |
|---|---|---|
| แถบบนขึ้น 🔴 ขาดการเชื่อมต่อ | เปิด `http://localhost:8189` | เริ่ม Smart Card Agent ของ สปสช. |
| แถบบนขึ้น 🟠 ไม่พบเครื่องอ่านบัตร | เช็คว่าเครื่องอ่านเสียบ USB แน่นหรือยัง | เสียบใหม่ / ลองพอร์ต USB อื่น / ติดตั้ง driver |
| `Cannot connect to server` / POST failed | `ping SERVER_IP` | ตรวจ Server URL ในแท็บตั้งค่า, firewall port 8222 |
| อ่านบัตรไม่ได้ | ทดสอบ `http://localhost:8189/api/smartcard/read-card-only` | ตรวจ driver เครื่องอ่านบัตร, เสียบบัตรให้แน่น |
| กด "เปิด Kiosk Browser" แล้วไม่มีอะไรเกิดขึ้น | ดูแท็บ Log จะมี error message ชัดเจน | ตั้ง Chrome หรือ Edge เป็น default browser ของเครื่อง |
| แก้ Server URL แล้วยังเจอปัญหาเดิม | เช็คว่ากด "💾 บันทึกค่า" แล้ว agent restart จริงไหม (ดูใน Log) | ถ้า agent กำลังทำงานอยู่ตอนบันทึก โปรแกรมจะ restart ให้อัตโนมัติ — รอสัก 1-2 วินาทีแล้วลองใหม่ |
| ส่งซ้ำ (duplicate) | ดู log ใน `agent.log` | ระบบมี `_process_lock` + เช็ค CID ซ้ำป้องกันอยู่แล้ว — ถ้ายังมีปัญหา ลด `poll_interval_sec` |
| Copy/Paste ในช่องตั้งค่าไม่ได้ | อัปเดตเป็นเวอร์ชันล่าสุด | เวอร์ชันเก่ามีบั๊กนี้ — build ใหม่แล้วแก้ |

### ดู Log

**Server log:**
```bash
# ดู log แบบ realtime
docker compose logs -f nhso-kiosk

# ดู log ไฟล์
cat logs/nhso_kiosk.log
```

**Agent log:** ดูได้ 2 ทาง — แท็บ **📋 Log** ในตัวโปรแกรม (real-time) หรือไฟล์ `agent.log` ที่อยู่ข้างๆ `NHSO_Kiosk_Agent_GUI.exe`

---

## คำสั่งที่ใช้บ่อย

### Server (Docker)

```bash
# ดูสถานะ container
docker compose ps

# ดู log แบบ realtime
docker compose logs -f nhso-kiosk

# Restart container (หลังแก้ .env ด้วยมือ ไม่ใช่ผ่าน Admin)
docker compose restart

# Rebuild (หลังแก้โค้ด)
docker compose up -d --build

# หยุด container
docker compose down

# หยุดและลบทุกอย่าง
docker compose down -v
```

### NHSO Kiosk Agent (Windows)

ไม่มีคำสั่งพิเศษ — double-click `NHSO_Kiosk_Agent_GUI.exe` แล้วกดปุ่มในหน้าโปรแกรม (▶ เริ่มอ่านบัตร / ⏹ หยุด / 🌐 เปิด Kiosk Browser)

### API endpoints สำหรับทดสอบ

```bash
# ตรวจสถานะ
curl http://SERVER_IP:8222/api/v1/kiosk/status

# Mock card (เฉพาะเมื่อ CARD_READER_MOCK=true)
curl -X POST http://SERVER_IP:8222/api/v1/kiosk/dev/mock-card \
  -H "Content-Type: application/json" \
  -d '{"cid":"1234567890123","name_th":"ทดสอบ ระบบ"}'

# ส่งเคลมจาก CID โดยตรง (ต้องมี Bearer token จริงจาก NHSO_TOKEN — token ปลอมจะได้ 401)
curl -X POST http://SERVER_IP:8222/api/v1/kiosk/claim-by-cid \
  -H "Authorization: Bearer YOUR_NHSO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cid":"1234567890123"}'
```

---

## สรุปขั้นตอนติดตั้ง (Quick Start)

```
1. Server
   ├── clone repo → cp .env.example .env → ตั้งค่า DB_HOST เป็น IP จริง (ห้าม localhost)
   ├── docker compose up -d --build
   ├── เปิด /admin → เปลี่ยนรหัส → ตั้ง DB → Run DB Setup
   ├── grant สิทธิ์ DB user ให้ครบ (รวม SELECT (vn, pttype) บน visit_pttype)
   ├── ตั้งค่า NHSO Token, Hospital Code, Source ID, NHSO Mode → Save
   └── curl :8222/api/v1/kiosk/status → ต้องได้ JSON

2. เครื่อง Kiosk
   ├── ติดตั้ง Smart Card Agent ของ สปสช. → เปิด port 8189
   ├── ตั้ง Chrome/Edge เป็น default browser
   ├── Copy NHSO_Kiosk_Agent_GUI.exe → C:\nhso_agent\
   ├── เปิดโปรแกรม → แท็บตั้งค่า → ใส่ Server URL = http://SERVER_IP:8222
   ├── ใส่ Client ID เฉพาะเครื่อง (ถ้ามีหลาย kiosk) → กด บันทึกค่า
   └── กด ▶ เริ่มอ่านบัตร → 🌐 เปิด Kiosk Browser → พร้อมใช้งาน
```
