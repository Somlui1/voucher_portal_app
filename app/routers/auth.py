"""
Auth Router — Login / Verify Endpoints
========================================
- POST /auth/login  → authenticate AD + return JWT
- GET  /auth/verify → verify token + return user info
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List

from app.service.auth_service import authenticate_ad, create_token, verify_token, get_supported_domains


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


# ── Models ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    status: str
    token: str
    username: str
    domain: str
    display_name: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    email: Optional[str] = ""


class VerifyResponse(BaseModel):
    status: str
    username: str
    domain: str
    display_name: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    email: Optional[str] = ""


class DomainsResponse(BaseModel):
    status: str
    domains: List[str]


# ── Dependency: Extract & verify token ─────────────────────────────────────────

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency — ดึง JWT จาก Authorization header แล้ว verify

    Usage:
        @router.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            ...
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # รองรับทั้ง "Bearer <token>" และ "<token>" ตรงๆ
    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]

    try:
        payload = verify_token(token)
        return payload
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/domains", response_model=DomainsResponse)
async def list_domains():
    """
    ดึงรายชื่อ Domains ทั้งหมดที่ตั้งค่าไว้ในระบบ
    """
    return DomainsResponse(
        status="success",
        domains=get_supported_domains()
    )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Login ผ่าน Active Directory

    - Verify username/password กับ AD (NTLM bind)
    - ตรวจสอบว่าเป็น Domain Admins
    - สร้าง JWT token ส่งกลับ
    """
    try:
        user_info = authenticate_ad(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    token = create_token(
        user_info["username"], 
        user_info["display_name"],
        user_info["first_name"],
        user_info["last_name"],
        user_info["email"],
        user_info["domain"]
    )

    return LoginResponse(
        status="success",
        token=token,
        username=user_info["username"],
        domain=user_info["domain"],
        display_name=user_info["display_name"],
        first_name=user_info["first_name"],
        last_name=user_info["last_name"],
        email=user_info["email"],
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify(user: dict = Depends(get_current_user)):
    """
    Verify JWT token — ใช้ตอนโหลดหน้าเพื่อเช็คว่า token ยังใช้ได้
    """
    return VerifyResponse(
        status="valid",
        username=user.get("sub", ""),
        domain=user.get("domain", ""),
        display_name=user.get("name", ""),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        email=user.get("email", ""),
    )
