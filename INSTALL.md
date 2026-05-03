# คู่มือติดตั้ง NHSO Connect Kiosk

> สำหรับผู้ดูแลระบบโรงพยาบาล  
> เวอร์ชัน 2.0 — Kiosk Edition

---

## เลือกวิธีติดตั้ง

| วิธี | เหมาะกับ | หน้านี้ |
|---|---|---|
| **Windows (Native)** | ติดตั้งบน Windows โดยตรง | [ข้ามไป](#windows-native) |
| **Linux + Docker** ⭐ แนะนำ | Ubuntu/Debian — portable, ย้ายเครื่องง่าย | [ข้ามไป](#linux--docker) |
| **Linux (Native)** | ไม่ต้องการ Docker | [ข้ามไป](#linux-native) |

---

## ความต้องการของระบบ

| รายการ | ขั้นต่ำ |
|---|---|
| OS | Windows 10/11 หรือ Ubuntu 22.04 LTS / Debian 12 |
| RAM | 2 GB ขึ้นไป |
| Network | เชื่อมต่อ HOSxP DB + Internet (NHSO API, Google TTS) |
| Card Reader | PC/SC Smart Card Reader (รองรับ ISO 7816) |

---

---

# Windows (Native)

## ขั้นตอนที่ 1 — เตรียมไฟล์โปรแกรม

รับไฟล์โปรแกรมจากผู้พัฒนา (ไม่ผ่าน Git) เช่น USB หรือ shared folder  
แตกไฟล์ไปที่ `C:\nhso_kiosk\`

```
C:\nhso_kiosk\
├── app\
├── requirements.txt
├── .env.example        ← ตัวอย่าง config (ไม่มีรหัสผ่านจริง)
└── INSTALL.md
```

> **สำคัญ:** ไฟล์ `.env` (ที่มีรหัสผ่านจริง) จะ**ไม่ถูกส่งมาด้วย**  
> ต้องสร้างใหม่ตามขั้นตอนด้านล่าง

---

## ขั้นตอนที่ 2 — ติดตั้ง Python Dependencies

เปิด Command Prompt ในฐานะ Administrator แล้วรัน:

```bat
cd C:\nhso_kiosk
pip install -r requirements.txt
```

---

## ขั้นตอนที่ 3 — เปิดใช้งาน Smart Card Service

1. กด `Win + R` → พิมพ์ `services.msc`
2. หา **Smart Card** → คลิกขวา → Properties
3. Startup type: **Automatic**
4. กด **Start** → OK

---

## ขั้นตอนที่ 4 — สร้างไฟล์ `.env`

> ไฟล์นี้เก็บ credential ทั้งหมด **ห้ามส่งต่อหรืออัปโหลดที่ใดทั้งสิ้น**

สร้างไฟล์ใหม่ชื่อ `.env` ที่ `C:\nhso_kiosk\.env` แล้วกรอกข้อมูล:

```env
# ========== Database HOSxP ==========
HOSXP_DB_URL=mysql+pymysql://ชื่อผู้ใช้:รหัสผ่าน@IP_เครื่องServer:3306/hospink

# ========== NHSO API ==========
NHSO_MODE=PRD
NHSO_PRD_URL=https://nhsoapi.nhso.go.th/nhsoendpoint/api/nhso-claim-detail
NHSO_TEST_URL=https://test.nhso.go.th/nhsoendpoint/api/nhso-claim-detail
HOSPITAL_CODE=รหัสสถานพยาบาล_5_หลัก
SOURCE_ID=รหัส_SOURCE_จาก_สปสช.
NHSO_TOKEN=eyJhbGci...  (Bearer Token จาก สปสช.)
RECORDER_PID=เลขบัตรประชาชนเจ้าหน้าที่ผู้บันทึก

# ========== Kiosk ==========
KIOSK_MODE=true
CARD_READER_MOCK=false
CARD_READER_NAME=
KIOSK_AUTO_RESET_SEC=8
KIOSK_HOSPITAL_NAME=โรงพยาบาล...
KIOSK_HOSPITAL_PHONE=0-XXXX-XXXX
```

### วิธีดูชื่อ Card Reader (CARD_READER_NAME)

เสียบ card reader แล้วรันคำสั่ง:

```bat
python -c "from smartcard.System import readers; print(readers())"
```

ตัวอย่างผลลัพธ์: `['Feitian SCR301 0']`  
→ ใส่ชื่อนั้นใน `CARD_READER_NAME=Feitian SCR301 0`  
(หรือเว้นว่างเพื่อให้ระบบเลือก reader แรกที่พบ)

---

## ขั้นตอนที่ 5 — สร้างตาราง Database

เชื่อมต่อ MariaDB แล้วรัน SQL นี้ใน database `hospink`:

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

> หากสร้างตารางไปแล้วก่อนหน้า ให้รัน ALTER เพิ่ม column:
>
> ```sql
> ALTER TABLE nhso_claim_log ADD COLUMN authen_code VARCHAR(50) AFTER transaction_id;
> ALTER TABLE nhso_claim_log ADD COLUMN dep_code VARCHAR(20) AFTER inscl_code;
> ```

---

## ขั้นตอนที่ 6 — รันระบบ

```bat
cd C:\nhso_kiosk
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ใช้ `--workers 1` เท่านั้น เพราะ card reader queue เป็น in-memory

เปิด browser แล้วไปที่:
- **หน้า Kiosk:** `http://localhost:8000/kiosk`
- **ตรวจสอบสถานะ:** `http://localhost:8000/api/v1/kiosk/status`

---

## ขั้นตอนที่ 7 — ตั้งให้รันอัตโนมัติเมื่อเปิดเครื่อง

สร้างไฟล์ `start_kiosk.bat`:

```bat
@echo off
cd C:\nhso_kiosk
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

สร้างไฟล์ `start_browser.bat` (รันบน**เครื่อง Kiosk ที่ต่อจอ**):

```bat
@echo off
REM รอให้ server พร้อมก่อน
timeout /t 5 /nobreak
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --kiosk --noerrdialogs --disable-infobars ^
  "http://IP_SERVER:8000/kiosk?client_id=%COMPUTERNAME%"
```

> `%COMPUTERNAME%` จะถูกแทนที่ด้วยชื่อเครื่องอัตโนมัติ ตรงกับที่ Local Agent ส่งไป

จากนั้นตั้ง Task Scheduler ให้รัน **ทั้งสองไฟล์** เมื่อเปิดเครื่อง:
1. `Win + R` → `taskschd.msc`
2. Create Basic Task → ตั้งชื่อ "NHSO Kiosk"
3. Trigger: **When the computer starts**
4. Action: **Start a program** → เลือก `start_kiosk.bat`
5. ติ๊ก "Run with highest privileges"
6. (ถ้าเครื่องนี้ต่อจอด้วย) ทำซ้ำขั้นตอนเดิมสำหรับ `start_browser.bat`

---

## Admin Config Page

หน้า config ถูกย้ายและป้องกันด้วย Basic Auth:

```
http://SERVER_IP:8000/admin/config
```

ตั้ง username/password ใน `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ตั้งรหัสผ่านที่แข็งแรง
```

> **สำคัญ:** เปลี่ยน `ADMIN_PASSWORD` จาก `changeme` ทันทีก่อนใช้งานจริง

---

## การรักษาความปลอดภัย Credential

### สิ่งที่ต้องทำ

| รายการ | วิธีการ |
|---|---|
| จำกัดสิทธิ์อ่านไฟล์ `.env` | คลิกขวา `.env` → Properties → Security → ให้สิทธิ์เฉพาะ Administrator |
| ไม่ส่ง `.env` ผ่าน Email/Line | ส่งด้วย USB หรือ RDP เท่านั้น |
| ไม่ commit ขึ้น Git | ไฟล์ `.gitignore` ป้องกันแล้ว |
| เปลี่ยน NHSO_TOKEN เมื่อหมดอายุ | แก้ที่ `.env` แล้ว restart server |
| ใช้ DB user เฉพาะ (ไม่ใช้ root) | สร้าง user ที่มีสิทธิ์ SELECT บน `ovst`, `vn_stat`, `patient` และ INSERT/SELECT บน `nhso_claim_log` เท่านั้น |

### สร้าง DB User สำหรับระบบนี้โดยเฉพาะ

```sql
-- รันใน MariaDB ด้วย root
CREATE USER 'nhso_kiosk'@'IP_เครื่อง_kiosk' IDENTIFIED BY 'รหัสผ่านแข็งแรง';

GRANT SELECT ON hospink.ovst         TO 'nhso_kiosk'@'IP_เครื่อง_kiosk';
GRANT SELECT ON hospink.vn_stat      TO 'nhso_kiosk'@'IP_เครื่อง_kiosk';
GRANT SELECT ON hospink.patient      TO 'nhso_kiosk'@'IP_เครื่อง_kiosk';
GRANT SELECT, INSERT ON hospink.nhso_claim_log TO 'nhso_kiosk'@'IP_เครื่อง_kiosk';

FLUSH PRIVILEGES;
```

จากนั้นใส่ใน `.env`:
```env
HOSXP_DB_URL=mysql+pymysql://nhso_kiosk:รหัสผ่านแข็งแรง@IP_Server:3306/hospink
```

---

## การตรวจสอบ pttype Mapping

ตรวจสอบรหัสสิทธิ์ในฐานข้อมูลโรงพยาบาล:

```sql
SELECT pttype, COUNT(*) as จำนวน
FROM ovst
WHERE vstdate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY pttype
ORDER BY จำนวน DESC;
```

นำผลลัพธ์ไปแก้ไข mapping ใน `app/services/nhso_api.py` บรรทัด `map_nhso_inscl`:

```python
mapping = {
    "XX": "UCS",   # บัตรทอง — ใส่ pttype จริงของโรงพยาบาล
    "XX": "OFC",   # ข้าราชการ
    "XX": "SSS",   # ประกันสังคม
    "XX": "LGO",   # อปท.
}
```

---

## แก้ไข NHSO Token เมื่อหมดอายุ

1. เปิดไฟล์ `C:\nhso_kiosk\.env`
2. แก้ไขบรรทัด `NHSO_TOKEN=eyJ...` ใส่ token ใหม่
3. บันทึกไฟล์
4. Restart server (ปิด window แล้วรัน `start_kiosk.bat` ใหม่)

> ไม่ต้องแก้ไข source code ใดๆ

---

## Checklist ก่อน Go Live

- [ ] เปลี่ยน `NHSO_MODE=PRD`
- [ ] ใส่ `NHSO_TOKEN` ที่ยังไม่หมดอายุ
- [ ] ตรวจสอบ `pttype mapping` ถูกต้อง
- [ ] ทดสอบ `/api/v1/kiosk/status` แสดง `reader_available: true`
- [ ] ทดสอบเสียบบัตรจริง 1 ใบ (mode TEST ก่อน)
- [ ] ตรวจสอบ `nhso_claim_log` มีข้อมูลบันทึก
- [ ] จำกัดสิทธิ์ไฟล์ `.env`
- [ ] ตั้ง Task Scheduler รันอัตโนมัติ

---

---

# Linux + Docker

> ⭐ แนะนำสำหรับการ deploy จริง — portable, restart อัตโนมัติ, ย้ายเครื่องง่าย  
> **หลักการ:** pcscd daemon อยู่บน host, แอปอยู่ใน container, คุยกันผ่าน Unix socket

## ขั้นตอนที่ 1 — ติดตั้ง pcscd บน Host

```bash
sudo apt update
sudo apt install -y pcscd pcsc-tools
sudo systemctl enable pcscd
sudo systemctl start pcscd

# ทดสอบว่า reader เจอไหม (เสียบ card reader ก่อน)
pcsc_scan
```

## ขั้นตอนที่ 2 — ติดตั้ง Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

## ขั้นตอนที่ 3 — วางไฟล์โปรแกรม

```bash
sudo mkdir -p /opt/nhso_kiosk
cd /opt/nhso_kiosk
# copy ไฟล์โปรแกรมทั้งหมดมาไว้ที่นี่
```

## ขั้นตอนที่ 4 — สร้างไฟล์ `.env`

```bash
cp .env.example .env
nano .env   # กรอกข้อมูลจริง
chmod 600 .env   # จำกัดสิทธิ์อ่านเฉพาะ owner
```

เนื้อหา `.env`:

```env
HOSXP_DB_URL=mysql+pymysql://nhso_kiosk:password@192.168.x.x:3306/hospink
NHSO_MODE=PRD
NHSO_PRD_URL=https://nhsoapi.nhso.go.th/nhsoendpoint/api/nhso-claim-detail
HOSPITAL_CODE=XXXXX
SOURCE_ID=XXXXX
NHSO_TOKEN=eyJ...
RECORDER_PID=1234567890123
KIOSK_MODE=true
CARD_READER_MOCK=false
CARD_READER_NAME=
KIOSK_AUTO_RESET_SEC=8
KIOSK_HOSPITAL_NAME=โรงพยาบาล...
KIOSK_HOSPITAL_PHONE=0-XXXX-XXXX
```

## ขั้นตอนที่ 5 — สร้างตาราง Database

เชื่อมต่อ MariaDB แล้วรัน SQL เดียวกับหัวข้อ Windows ด้านบน

## ขั้นตอนที่ 6 — Build และ Run

```bash
cd /opt/nhso_kiosk

# Build image
docker compose build

# Run (background)
docker compose up -d

# ดู log
docker compose logs -f
```

## ขั้นตอนที่ 7 — ตั้ง kiosk browser เปิดอัตโนมัติ

ถ้าเครื่อง Linux ต่อจอแสดงผลสำหรับ kiosk:

```bash
# ติดตั้ง Chromium
sudo apt install -y chromium-browser

# สร้าง autostart (ใส่ computer name ใน URL อัตโนมัติ)
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/nhso-kiosk.desktop << EOF
[Desktop Entry]
Type=Application
Name=NHSO Kiosk
Exec=bash -c 'sleep 5 && chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run "http://localhost:8000/kiosk?client_id=$(hostname)"'
X-GNOME-Autostart-enabled=true
EOF
```

> `$(hostname)` จะถูกแทนที่ด้วยชื่อเครื่องอัตโนมัติ ตรงกับที่ Local Agent ส่งไป

## คำสั่งที่ใช้บ่อย

```bash
# ดูสถานะ container
docker compose ps

# restart (เช่น หลังแก้ .env)
docker compose restart

# อัปเดตโปรแกรมเวอร์ชันใหม่
docker compose down
docker compose build --no-cache
docker compose up -d

# ดู log แบบ real-time
docker compose logs -f nhso-kiosk
```

---

# Linux (Native)

> สำหรับกรณีที่ไม่ต้องการใช้ Docker

## ขั้นตอนที่ 1 — ติดตั้ง Dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
    pcscd pcsc-tools libpcsclite1 libpcsclite-dev \
    build-essential unixodbc-dev

sudo systemctl enable pcscd && sudo systemctl start pcscd
```

## ขั้นตอนที่ 2 — ติดตั้ง Python Packages

```bash
cd /opt/nhso_kiosk
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ขั้นตอนที่ 3 — สร้าง `.env` และ Database

เหมือนกับขั้นตอนใน Linux + Docker ด้านบน

## ขั้นตอนที่ 4 — ตั้ง systemd Service

```bash
sudo nano /etc/systemd/system/nhso-kiosk.service
```

```ini
[Unit]
Description=NHSO Kiosk
After=network.target pcscd.service
Wants=pcscd.service

[Service]
WorkingDirectory=/opt/nhso_kiosk
ExecStart=/opt/nhso_kiosk/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
User=www-data
EnvironmentFile=/opt/nhso_kiosk/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable nhso-kiosk
sudo systemctl start nhso-kiosk

# ตรวจสอบสถานะ
sudo systemctl status nhso-kiosk
```

## แก้ไข Token เมื่อหมดอายุ (Linux)

```bash
nano /opt/nhso_kiosk/.env   # แก้ NHSO_TOKEN

# Docker
docker compose restart

# Native
sudo systemctl restart nhso-kiosk
```

---

## Local Agent — กรณีหลายเครื่อง Kiosk

> ใช้เมื่อ **เครื่องอ่านบัตร** อยู่คนละเครื่องกับ **Server** (Docker)  
> Agent รันบน Windows PC ที่ต่อ card reader แล้วส่งข้อมูลไป Server ผ่าน HTTP

### วางไฟล์

```
C:\nhso_agent\
├── local_agent.py
├── config.ini
└── run_agent.bat
```

### config.ini

```ini
[agent]
server_url = http://192.168.33.103:8000
; client_id: ถ้าว่าง จะใช้ Computer Name ของเครื่องนี้โดยอัตโนมัติ
; ให้ตรงกับ ?client_id= ใน URL ของ browser หน้า kiosk บนเครื่องเดียวกัน
client_id =
```

> ดู Computer Name ของเครื่อง: `Win + R` → พิมพ์ `cmd` → รัน `hostname`

### การจับคู่ Agent กับหน้าจอ Kiosk

Agent ส่ง `client_id` (Computer Name) ไปกับทุก request → Server ส่ง SSE event ไปเฉพาะ browser ที่ใช้ `client_id` เดียวกัน

**ตั้ง URL browser ของเครื่อง Kiosk ให้ตรงกับ Computer Name:**

```
http://192.168.33.103:8000/kiosk?client_id=KIOSK-PC-01
```

> แทนที่ `KIOSK-PC-01` ด้วยชื่อเครื่องจริง (ผลจากคำสั่ง `hostname`)

**ถ้าแต่ละเครื่องมี IP ต่างกัน** (ไม่ได้อยู่หลัง NAT): ปล่อย `client_id =` ว่างได้ ระบบจะใช้ Computer Name อัตโนมัติ และ browser เปิดได้เลยโดยไม่ต้อง `?client_id=`

> **สรุป:** `client_id` ใน config.ini และ URL ของ browser **ต้องตรงกันทุกตัวอักษร**

### run_agent.bat

```bat
@echo off
cd /d C:\nhso_agent
python local_agent.py
pause
```

ตั้ง Task Scheduler ให้รัน `run_agent.bat` เมื่อเปิดเครื่อง (เหมือนขั้นตอนที่ 7 ของ Windows)

### ติดตั้ง Dependencies บนเครื่อง Agent

```bat
pip install requests pythaiidcard pyscard
```

---

## การดู Log ระบบ

ระบบเก็บ log 2 ชั้น ทำงานอัตโนมัติหลัง deploy:

| ชั้น | ที่เก็บ | เนื้อหา |
|---|---|---|
| **Docker stdout** | Docker json-file driver | uvicorn start/stop, HTTP request, print() |
| **App log** (`nhso_kiosk.log`) | `/opt/nhso_kiosk/logs/` บน host | DEBUG/INFO/ERROR ละเอียด ทุก API call |

### โครงสร้างไฟล์ log

```
/opt/nhso_kiosk/
└── logs/
    ├── nhso_kiosk.log        ← log ล่าสุด
    ├── nhso_kiosk.log.1      ← rotate อัตโนมัติ เมื่อครบ 5 MB
    └── nhso_kiosk.log.2      ← เก็บย้อนหลัง 3 ไฟล์ (รวมสูงสุด ~15 MB)
```

Docker stdout จำกัด **50 MB** (10 MB × 5 ไฟล์) — Docker จัดการเองอัตโนมัติ

### คำสั่งดู log

```bash
# ── Docker stdout (real-time) ──────────────────────────────────────
# ดู log ทั้งหมด แบบ real-time
docker compose logs -f nhso-kiosk

# ดู 100 บรรทัดล่าสุด แล้วหยุด
docker compose logs --tail=100 nhso-kiosk

# ── App log (file บน host) ─────────────────────────────────────────
# ดู real-time
tail -f /opt/nhso_kiosk/logs/nhso_kiosk.log

# ดู 50 บรรทัดล่าสุด
tail -n 50 /opt/nhso_kiosk/logs/nhso_kiosk.log

# กรองเฉพาะ ERROR
grep "\[ERROR\]" /opt/nhso_kiosk/logs/nhso_kiosk.log

# กรองเฉพาะผล NHSO API (success/fail)
grep "\[NHSO\]" /opt/nhso_kiosk/logs/nhso_kiosk.log

# กรองตามวันที่ เช่น วันที่ 3 พ.ค.
grep "^2026-05-03" /opt/nhso_kiosk/logs/nhso_kiosk.log

# ── ดูทั้งสองพร้อมกัน ──────────────────────────────────────────────
# (ต้องติดตั้ง multitail: sudo apt install multitail)
multitail /opt/nhso_kiosk/logs/nhso_kiosk.log \
  -l "docker compose -f /opt/nhso_kiosk/docker-compose.yml logs -f nhso-kiosk"
```

### อ่าน log อย่างไร

ตัวอย่าง log บรรทัดปกติ:

```
2026-05-03 09:15:32 [INFO]  nhso_kiosk: [CardReader] Mock mode started
2026-05-03 09:15:45 [INFO]  nhso_kiosk: [Card] Processing CID=***3456 name=นาย ทดสอบ ระบบ
2026-05-03 09:15:46 [INFO]  nhso_kiosk: [NHSO] VN=6605030001 response: {"responseCode":"200",...}
2026-05-03 09:15:46 [INFO]  nhso_kiosk: [NHSO] VN=6605030001 SUCCESS — authen=ABC12345
```

ตัวอย่าง log เมื่อเกิด error:

```
2026-05-03 09:20:11 [ERROR] nhso_kiosk: [NHSO] VN=6605030002 FAILED — error={"dataError":"..."}
2026-05-03 09:20:11 [ERROR] nhso_kiosk: [NHSO] RequestException: HTTPSConnectionPool...
```

### ตรวจสอบ log folder หลัง deploy ครั้งแรก

```bash
# ตรวจว่าโฟลเดอร์ logs ถูกสร้างและ mount ถูกต้อง
ls -la /opt/nhso_kiosk/logs/

# ถ้าโฟลเดอร์ยังไม่มี ให้สร้างก่อน แล้ว rebuild
mkdir -p /opt/nhso_kiosk/logs
docker compose up -d --build
```

### Native (ไม่ใช้ Docker)

App log อยู่ที่ตำแหน่งเดียวกัน `/opt/nhso_kiosk/nhso_kiosk.log`

```bash
# ดู real-time
tail -f /opt/nhso_kiosk/nhso_kiosk.log

# ดูผ่าน systemd journal (stdout เท่านั้น)
journalctl -u nhso-kiosk -f
```

---

## ติดต่อผู้พัฒนา

หากพบปัญหาระหว่างติดตั้ง ติดต่อทีมพัฒนาพร้อมแนบ:
1. Log: `docker compose logs` หรือ `journalctl -u nhso-kiosk`
2. ผลลัพธ์จาก `http://IP:8000/api/v1/kiosk/status`
3. ข้อความ error ที่ปรากฏ (ไม่ต้องส่ง `.env`)
