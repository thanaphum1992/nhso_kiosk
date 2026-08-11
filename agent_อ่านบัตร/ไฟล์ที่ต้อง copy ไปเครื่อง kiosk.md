# ไฟล์ที่ต้อง copy ไปเครื่อง kiosk (เช่น `C:\agent\`)

Copy **ทั้งโฟลเดอร์** `agent_อ่านบัตร` จากโปรเจกต์ หรืออย่างน้อยไฟล์ด้านล่าง **ไว้โฟลเดอร์เดียวกัน**:

| ไฟล์/โฟลเดอร์ | จำเป็น |
|----------------|--------|
| `local_agent.py` | **ต้องมี** — สคริปต์อ่านบัตร + ส่ง server |
| `Card_reader_agent.bat` | เปิด kiosk + รัน agent |
| `build_agent.bat` | รันครั้งแรกถ้ายังไม่มี `python\` |
| `config.ini` | ตั้ง `server_url`, `smartcard_agent_url` |
| `python\` | หลังรัน `build_agent.bat` แล้ว |

## อย่า copy แค่นี้

- `dist\Card_reader_agent\` อย่างเดียว — ไม่มี `local_agent.py` ที่ root (ใช้กับ `.bat` ไม่ได้)
- แค่ `.bat` + `python\` โดยไม่มี `local_agent.py` → error แบบ `can't open file local_agent.py`

## config.ini ตัวอย่าง

```ini
[agent]
server_url = http://192.168.30.200:8222
smartcard_agent_url = http://localhost:8189
client_id =
dep_code =
```

`client_id` ว่าง = ใช้ชื่อเครื่อง Windows (`DESKTOP-VRDUHSU`) อัตโนมัติ

## ลำดับเปิดใช้งาน

1. Smart Card Agent → `http://localhost:8189`
2. Double-click `Card_reader_agent.bat`
