import os
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader
from helper.converttopdf import html_to_pdf
from app.service.vocher_wifi import (
    create_voucher_endpoint,
    get_access_token,
    get_network_group_id,
    get_all_network_groups,
    get_all_profiles,
)
from app.routers.auth import get_current_user

# Jinja2 template setup
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "component")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# Create Router
SOS = APIRouter(
    prefix="/SOS",
    tags=["SOS"]
)

# --- Data Models (Pydantic) ---
class TicketData(BaseModel):
    voucher_code: str
    profile_name: str
    concurrent_devices: int = 1
    period: str = "1Days"
    maximum_download_rate: str = "20Mbps"

class VoucherRequest(BaseModel):
    groupname: str = "AH"
    profile_name: str = "AAPICO_Day"
    quantity: int = 1
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = None

# ==========================================
# Voucher Ticket Generator
# ==========================================

@SOS.post("/generate-ticket", response_class=HTMLResponse)
async def generate_ticket(tickets: List[TicketData], user: dict = Depends(get_current_user)):
    """
    สร้าง HTML Voucher Ticket จาก JSON
    - รับ List ของ TicketData
    - Render เป็น HTML พร้อมปริ้น
    - ไม่มีการบันทึกข้อมูล (stateless)
    """
    if not tickets:
        raise HTTPException(status_code=400, detail="กรุณาส่ง ticket อย่างน้อย 1 รายการ")

    try:
        template = jinja_env.get_template("voucher_template.html")
        html_content = template.render(tickets=[t.model_dump() for t in tickets])
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template render error: {str(e)}")


@SOS.post("/generate-ticket/pdf")
async def generate_ticket_pdf(tickets: List[TicketData], user: dict = Depends(get_current_user)):
    """
    สร้าง PDF Voucher Ticket จาก JSON
    - รับ List ของ TicketData
    - Render เป็น HTML → แปลงเป็น PDF ผ่าน Chromium headless
    - ส่งกลับเป็นไฟล์ PDF ดาวน์โหลดได้
    """
    if not tickets:
        raise HTTPException(status_code=400, detail="กรุณาส่ง ticket อย่างน้อย 1 รายการ")

    try:
        # 1) Render HTML จาก Jinja2 template
        template = jinja_env.get_template("voucher_template.html")
        html_content = template.render(tickets=[t.model_dump() for t in tickets])

        # 2) แปลง HTML → PDF ด้วย Chromium headless
        pdf_bytes = html_to_pdf(html_content)

        # 3) ส่ง PDF กลับเป็น downloadable file
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=voucher.pdf"
            },
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Browser not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@SOS.get(
    "/generate-ticket/print",
    response_class=HTMLResponse,
    summary="🖨️ Generate & Print Voucher via Query Parameters",
)
async def print_voucher_via_query(
    groupname: str = "AH",
    profile_name: str = "AAPICO_Day",
    quantity: int = 1,
):
    """
    Serve หน้า voucher_auto_print.html ที่จะทำงานอัตโนมัติ:
    1. อ่าน query params จาก URL
    2. เรียก POST /generate-voucher (Ruijie Cloud API)
    3. เรียก POST /generate-ticket (render HTML)
    4. Replace หน้าปัจจุบันด้วย voucher print layout
    5. ลบ query params ออกจาก URL เพื่อป้องกัน refresh ซ้ำ
    """
    try:
        template = jinja_env.get_template("voucher_auto_print.html")
        html_content = template.render()
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template render error: {str(e)}")


@SOS.get("/generate-ticket/preview", response_class=HTMLResponse)
async def generate_ticket_preview():
    """
    หน้า Form สำหรับทดสอบ generate-ticket
    - วาง JSON → กด Generate → เปิด HTML ใน Tab ใหม่
    """
    try:
        template = jinja_env.get_template("vocher_portal_application.html")
        html_content = template.render()
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template render error: {str(e)}")


# ==========================================
# WiFi Voucher Generator (Ruijie Cloud API)
# ==========================================

@SOS.post("/generate-voucher")
async def generate_voucher(request: VoucherRequest, user: dict = Depends(get_current_user)):
    """
    สร้าง WiFi Voucher ผ่าน Ruijie Cloud API
    - เรียก create_voucher_endpoint เพื่อสร้าง voucher
    - แปลง response ให้เป็น TicketData format
    """
    result = create_voucher_endpoint(
        groupname=request.groupname,
        profile_name=request.profile_name,
        quantity=request.quantity,
        first_name=request.first_name,
        last_name=request.last_name,
        email=request.email,
        phone=request.phone,
        comment=request.comment
    )
    return result


@SOS.get(
    "/wifi/groups",
    summary="📡 List all Ruijie Network Groups",
)
async def list_wifi_groups(user: dict = Depends(get_current_user)):
    """
    ดึง Network Groups ทั้งหมดจาก Ruijie Cloud
    """
    access_token = get_access_token()
    groups = get_all_network_groups(access_token)
    return {
        "status": "success",
        "count": len(groups),
        "data": groups,
    }


@SOS.get(
    "/wifi/groups/{groupname}/profiles",
    summary="📋 List WiFi Profiles of a Group",
)
async def list_wifi_profiles(groupname: str, user: dict = Depends(get_current_user)):
    """
    ดึง WiFi Profile ทั้งหมดของ Group ที่ระบุ
    1. ดึง Access Token
    2. หา Group ID จากชื่อ
    3. ดึง Profile List ทั้งหมด
    """
    access_token = get_access_token()
    group_id = get_network_group_id(access_token=access_token, name=groupname)
    profiles = get_all_profiles(access_token=access_token, group_id=group_id)
    return {
        "status": "success",
        "groupname": groupname.upper(),
        "count": len(profiles),
        "data": profiles,
    }
