# คู่มือติดตั้ง NHSO Authen Kiosk

เอกสารนี้อ้างอิงโครงสร้างปัจจุบันของ repo `nhso_claim/` สำหรับ deploy server ด้วย Docker และใช้งาน Local Agent บนเครื่อง Windows ที่ต่อเครื่องอ่านบัตร

## ภาพรวมการ deploy

ระบบแบ่งเป็น 2 ส่วนหลัก:

| ส่วน | โฟลเดอร์ | หน้าที่ |
|---|---|---|
| Server | `nhso_claim/` | FastAPI web/API, เชื่อม HOSxP, ส่งข้อมูลไป NHSO, แสดงหน้า kiosk/admin |
| Local Agent | `nhso_claim/agent/` | รันบน Windows client, อ่านบัตรจากเครื่องตัวเอง, ส่งข้อมูลไป server พร้อม `client_id` |

ไฟล์ที่ต้องสร้างเองหลัง clone 

| ไฟล์/โฟลเดอร์ | ....... |
|---|---|
| `.env` | มีรหัสผ่าน DB, NHSO token, admin password |
| `agent/config.ini` | config เฉพาะเครื่อง client |
| `agent/python/` | Embedded Python และ package ที่ติดตั้งจาก `build_agent.bat` |
| `logs/`, `*.log` | log runtime |

## ติดตั้ง Server ด้วย Docker

1. Clone หรือ copy repo ไปที่ server

```bash
cd /opt
git clone https://github.com/thanaphum1992/nhso_authen_kiosk.git nhso_claim
cd nhso_claim
```

2. สร้าง `.env` จาก `.env.example`

```bash
cp .env.example .env
nano .env
```

ค่าหลักที่ต้องตรวจ:

```env
HOSXP_DB_URL=mysql+pymysql://user:password@DB_HOST:3306/hospink
NHSO_MODE=PRD
NHSO_TOKEN='xxxxxx-xxxxxx-xxxxxx-xxxx"  #token ปิดสิทธิ
RECORDER_PID=123456789012322222         #CID เจ้าของ TOKEN
HOSPITAL_CODE=XXXXX                     #รหัสโรงพยาบาล
KIOSK_HOSPITAL_NAME=ชื่อโรงพยาบาล         # diskplay แสดงหน้า kiosk เสียบบัตร
KIOSK_HOSPITAL_PHONE=0-XXXX-XXXX
```

3. Build และ start container

```bash
docker compose up -d --build
```

4. เปิดใช้งานผ่าน port:8222

| หน้า/API | URL |
|---|---|
| Kiosk | `http://SERVER_IP:8222/kiosk` |
| Admin | `http://SERVER_IP:8222/admin` |
| Status | `http://SERVER_IP:8222/api/v1/kiosk/status` |

หมายเหตุ: ใน container ในแอปรันที่ port `8000` แต่ `docker-compose.yml` map ออกมาที่ Port `8222`  client เข้าใช้งาน http://SERVER_IP:8222

## Database

ในหน้า Admin สามารถทดสอบ connection และสั่ง setup ตารางได้ หรือสร้างตารางเองใน database HOSxP:

Database สร้าง แยกสำหรับ เก็บ log การขอ เลข ENDPOINT (โปรแกรมจะเช็ค VN ที่ข้อเเล้วจากคารางนี้)
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

## ติดตั้ง Local Agent บนเครื่อง Windows Client

ใช้เมื่อเครื่องอ่านบัตรอยู่คนละเครื่องกับ server หรือมีหลายเครื่องเสียบบัตรพร้อมกัน ระบบจะจับคู่ผลลัพธ์ด้วย `client_id` เพื่อไม่ให้หน้า kiosk ของเครื่องอื่นรับข้อมูลผิดเครื่อง

1. Copy โฟลเดอร์ `agent/` ไปไว้ที่เครื่อง client เช่น

```text
C:\nhso_agent\
```

2. สร้างไฟล์ `config.ini` ในโฟลเดอร์เดียวกัน

```ini
[agent]
server_url = http://SERVER_IP:8222
client_id =
dep_code =
```

ความหมาย:

| ค่า | รายละเอียด |
|---|---|
| `server_url` | URL server ใช้ port `8222` ตาม `docker-compose.yml` |
| `client_id` | ถ้าว่าง ระบบจะใช้ชื่อเครื่อง Windows และบันทึกลง `config.ini` อัตโนมัติ |
| `dep_code` | ถ้าตั้งค่า จะเลือก visit เฉพาะแผนกนั้นก่อนส่งเคลม |

3. รัน `build_agent.bat` 1 ครั้ง เพื่อติดตั้ง Embedded Python และ packages

```bat
build_agent.bat
```

หลังติดตั้งเสร็จ script จะลบไฟล์ติดตั้งชั่วคราว เช่น `python-embed.zip`, `get-pip.py`, `__pycache__`

4. ใช้งานประจำวันด้วย `Card_reader_agent.bat`

```bat
Card_reader_agent.bat
```

ไฟล์นี้จะ:

- อ่าน `server_url` จาก `config.ini`
- เปิด browser ไปที่ `http://SERVER_IP:8222/kiosk?client_id=%COMPUTERNAME%`
- start `local_agent.py`
- ถ้ายังไม่มี `agent/python/python.exe` จะเรียก `build_agent.bat` ให้อัตโนมัติ

## การจับคู่หลายเครื่อง

ระบบปัจจุบันส่ง event เฉพาะ subscriber ที่มี `client_id` ตรงกัน:

```text
เครื่อง A: agent client_id = KIOSK-A -> browser /kiosk?client_id=KIOSK-A
เครื่อง B: agent client_id = KIOSK-B -> browser /kiosk?client_id=KIOSK-B
```

ถ้าตั้ง `client_id` เองใน `config.ini` ต้องเปิด browser ด้วยค่าเดียวกันทุกตัวอักษร เช่น:

```text
config.ini: client_id = ER-01
browser:    http://SERVER_IP:8222/kiosk?client_id=ER-01
```



## คำสั่งที่ใช้บ่อย

```bash
# ดูสถานะ container
docker compose ps

# ดู log server
docker compose logs -f nhso-kiosk

# restart หลังแก้ .env
docker compose restart

# rebuild ใหม่
docker compose up -d --build
```

## ตรวจระบบหลังติดตั้ง

1. เปิด `http://SERVER_IP:8222/api/v1/kiosk/status` แล้วต้องได้ JSON status
2. เปิด `http://SERVER_IP:8222/admin` และ login ด้วย `ADMIN_USERNAME` / `ADMIN_PASSWORD`
3. ที่เครื่อง client เปิด `Card_reader_agent.bat`
4. เสียบบัตรที่เครื่อง client นั้น แล้วผลต้องแสดงเฉพาะหน้า kiosk ที่มี `client_id` เดียวกัน
