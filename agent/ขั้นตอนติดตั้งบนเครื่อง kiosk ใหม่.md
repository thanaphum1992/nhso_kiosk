# ขั้นตอนติดตั้งบนเครื่อง kiosk ใหม่

1. Copy โฟลเดอร์ `agent\` ไปวางที่เครื่อง client เช่น `C:\nhso_agent\`
2. สร้าง/แก้ไฟล์ `config.ini` แล้วตั้ง `server_url = http://SERVER_IP:8222`
3. Double-click `build_agent.bat` 1 ครั้ง เพื่อ download Embedded Python และติดตั้ง package
4. Double-click `Card_reader_agent.bat` เพื่อเปิดหน้า kiosk และเริ่มอ่านบัตร

หมายเหตุ: ถ้า `client_id` ใน `config.ini` ว่าง ระบบจะใช้ชื่อเครื่อง Windows อัตโนมัติ และหน้า kiosk จะเปิดด้วย `?client_id=%COMPUTERNAME%`
