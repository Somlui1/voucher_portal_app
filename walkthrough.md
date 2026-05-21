# Walkthrough — โครงสร้างและการใช้งานโครงการ Voucher Portal (Standalone)

ยินดีต้อนรับสู่โครงการ **Voucher Portal** ที่ได้รับการแยกโครงสร้างออกมาเป็นอิสระ (Standalone Project) จากโครงการหลัก โดยระบบนี้ได้รับการปรับลดความซับซ้อน ปราศจากฐานข้อมูล (Stateless), ระบบ NLP, หรือระบบคำนวณ SLA อื่นๆ เหลือเฉพาะส่วนที่เกี่ยวข้องกับการพิสูจน์ตัวตนผ่าน Active Directory (LDAP) และการสร้าง/สั่งพิมพ์คูปองอินเทอร์เน็ต WiFi จาก Ruijie Cloud API เท่านั้น

---

## 📁 โครงสร้างโฟลเดอร์ของโครงการ

โครงการใหม่จะอยู่ที่โฟลเดอร์ `voucher_portal_app/` มีโครงสร้างดังนี้:

```text
voucher_portal_app/
├── .env                  # ไฟล์ตั้งค่าตัวแปรสภาพแวดล้อม (Credentials)
├── requirements.txt      # รายการ Python dependencies ที่จำเป็นเท่านั้น
├── walkthrough.md        # คู่มือการใช้งานระบบและการติดตั้งนี้ (ภาษาไทย)
├── helper/
│   └── converttopdf.py   # ฟังก์ชันแปลง HTML → PDF ด้วย Chromium / Chrome / Edge headless
└── app/
    ├── __init__.py
    ├── main.py           # ตัวเริ่มต้นแอป FastAPI และลงทะเบียน Router
    ├── server.py         # สคริปต์สำหรับรัน Uvicorn server (มีระบบ HTTPS fallback)
    ├── component/        # โฟลเดอร์เก็บ HTML Templates สำหรับแสดงผลและพิมพ์คูปอง
    │   ├── vocher_portal_application.html  # หน้าจอเว็บหลัก (Single Page UI)
    │   ├── voucher_template.html          # รูปแบบคูปองสำหรับพิมพ์ (Print layout)
    │   └── voucher_auto_print.html        # หน้าสำหรับส่งพิมพ์อัตโนมัติผ่านลิงก์
    ├── routers/
    │   ├── __init__.py
    │   ├── auth.py       # API Endpoints สำหรับ Login & ตรวจสอบ JWT Token
    │   └── SOS.py        # API Endpoints สำหรับระบบสร้างคูปอง WiFi (Ruijie API)
    └── service/
        ├── __init__.py
        ├── auth_service.py   # โค้ดส่วนเชื่อมต่อ Active Directory ด้วย LDAP และการจัดการ JWT
        └── vocher_wifi.py    # โค้ดติดต่อ Ruijie Cloud API เพื่อดึงข้อมูลกลุ่ม / โปรไฟล์ และสร้าง Voucher
```

---

## 🛠️ ขั้นตอนการติดตั้งและการใช้งาน

### 1. การติดตั้ง Dependencies
เปิด Terminal ในโฟลเดอร์ `voucher_portal_app` แล้วใช้คำสั่งเพื่อสร้าง Virtual Environment และติดตั้ง Packages ที่กำหนดไว้ใน `requirements.txt`:

```bash
# สร้าง virtual environment (หากยังไม่มี)
python -m venv .venv

# เปิดใช้งาน virtual environment (Windows)
.venv\Scripts\activate

# ติดตั้ง dependencies
pip install -r requirements.txt
```

ตัวไลบรารีที่จำเป็นมีเพียง:
- `fastapi` และ `uvicorn` สำหรับรับส่งคำขอและรันเว็บเซิร์ฟเวอร์
- `requests` สำหรับเรียก API ของ Ruijie Cloud
- `jinja2` สำหรับจัดการ HTML Templates
- `ldap3` สำหรับดึงข้อมูลและยืนยันตัวตนกับ Active Directory
- `PyJWT` สำหรับสร้างและตรวจสอบความถูกต้องของสิทธิ์การเข้าถึง (JWT Tokens)
- `python-dotenv` สำหรับโหลดการตั้งค่าจากไฟล์ `.env`

---

### 2. การตั้งค่าระบบ (.env)
คัดลอกหรือปรับแต่งข้อมูลในไฟล์ `.env` เพื่อให้ระบบเชื่อมต่อไปยังเซิร์ฟเวอร์ต่างๆ ได้ถูกต้อง:

```env
# ข้อมูลเชื่อมต่อ Ruijie Cloud API
Ruijie_APP_ID=YOUR_RUIJIE_APP_ID
Ruijie_APP_SECRET=YOUR_RUIJIE_APP_SECRET

# ข้อมูลสำหรับเชื่อมต่อและดึงข้อมูลจาก Active Directory (AD)
AD_HOSTS=10.10.10.253,10.10.10.250
AD_USER="aapico\username_service"
AD_PASSWORD="password_service"
AD_BASE_DN="DC=aapico,DC=com"

# การตั้งค่าความปลอดภัยของ JWT Authentication
JWT_SECRET=aapico-voucher-secret-key-2026
JWT_EXPIRE_HOURS=8
```

---

### 3. การรันเซิร์ฟเวอร์ (Running the Application)
สามารถรันระบบได้ 2 วิธี:

#### วิธีที่ 1: รันผ่านสคริปต์ `server.py`
สคริปต์นี้ได้รับการออกแบบให้ตรวจสอบหาไฟล์ใบรับรอง SSL (`key.pem` และ `cert.pem`) โดยอัตโนมัติ หากไม่มีไฟล์ดังกล่าวในโฟลเดอร์แอป ระบบจะรันบนโปรโตคอล HTTP ปกติ:

```bash
python app/server.py
```

#### วิธีที่ 2: รันผ่านคำสั่ง Uvicorn โดยตรง
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

เมื่อเซิร์ฟเวอร์เริ่มทำงานแล้ว สามารถเปิดทดสอบและใช้งานแอปพลิเคชันได้ที่:
- **หน้าเว็บหลัก**: [http://localhost:8000/SOS/generate-ticket/preview](http://localhost:8000/SOS/generate-ticket/preview)
- **หน้าคู่มือ API (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 💡 จุดเด่นและการทำงานของโครงสร้างใหม่ (Refactored Highlights)

1. **ไม่มีการใช้งานฐานข้อมูล (Stateless Architecture)**: ระบบนี้ไม่ได้เชื่อมต่อกับ PostgreSQL หรือฐานข้อมูลภายนอกใดๆ ดังนั้นจึงไม่มีส่วนของ DB model หรือ cache ใดมารบกวนการทำโครงสร้างใหม่ ทำให้เบาขึ้น ติดตั้งง่าย และทำงานได้อย่างรวดเร็ว
2. **การลงทะเบียนเส้นทาง API ที่สะอาด**: มีการรวบรวมเฉพาะส่วนเชื่อมต่อ `/auth` และ `/SOS` ซึ่งสัมพันธ์กันกับตัวหน้าเว็บ frontend ตรงๆ และปิด endpoints ส่วนอื่นๆ (เช่น SLA calculations, holiday settings, และการแจ้งซ่อมของ Intranet)
3. **การจัดการ Path ของ Template**: ย้ายการอ้างอิงตำแหน่งโฟลเดอร์ component ต่างๆ ไปอยู่ในระดับเดียวกันกับ router ของตัวเอง ทำให้หมดกังวลเรื่องการหาไฟล์ HTML templates ไม่เจอ
4. **ระบบ PDF Generation ในตัว**: สามารถแปลงรูปเล่มคูปอง HTML ออกมาเป็น PDF ผ่าน Chromium หรือ Google Chrome/Microsoft Edge ในเครื่องของผู้ใช้งานได้อย่างรวดเร็ว

---

จัดทำโดยทีมพัฒนาเพื่อช่วยให้การโยกย้ายระบบเป็นไปอย่างรวดเร็วและปลอดภัย!
