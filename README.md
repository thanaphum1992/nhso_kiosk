1. Clone หรือ copy repo ไปที่ server

```bash
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
HOSPITAL_CODE=XXXXX                     #รหัสโรงพยาบาล
SOURCE_ID=XXXXX
RECORDER_PID=123456789012322222
KIOSK_HOSPITAL_NAME=ชื่อโรงพยาบาล         # diskplay แสดงหน้า kiosk เสียบบัตร
KIOSK_HOSPITAL_PHONE=0-XXXX-XXXX
```
