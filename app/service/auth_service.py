"""
Auth Service — AD LDAP Authentication + JWT Token
===================================================
- authenticate ผ่าน Active Directory (LDAP NTLM bind) แบบรองรับหลาย Domain
- ตรวจสอบ Domain Admins group membership ตามแต่ละ Domain
- สร้าง / verify JWT token
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta

import jwt
from ldap3 import Server, Connection, ServerPool, FIRST, SUBTREE, NTLM
from ldap3.core.exceptions import LDAPException, LDAPBindError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
_JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
_JWT_EXPIRE_HOURS = float(os.getenv("JWT_EXPIRE_HOURS", "8"))
_JWT_ALGORITHM = "HS256"

# โครงสร้างสำหรับเก็บ config ของแต่ละ Domain
_DEFAULT_DOMAINS_CONFIG = {
    "aapico.com": {
        "ntlm_domain": "aapico",
        "hosts": [h.strip() for h in os.getenv("AD_HOSTS", "10.10.10.253,10.10.10.250").split(",")],
        "base_dn": os.getenv("AD_BASE_DN", "DC=aapico,DC=com"),
        "svc_user": os.getenv("AD_USER", "aapico\\msa.mcp"),
        "svc_pass": os.getenv("AD_PASSWORD", "it@apico4U"),
        "required_group": "Domain Admins"
    }
}

def get_domains_config() -> dict:
    """โหลด Domain Configurations จาก env หรือ fallback เป็น default"""
    config_env = os.getenv("DOMAINS_CONFIG")
    if config_env:
        try:
            parsed = json.loads(config_env)
            # แปลง hosts ที่เป็น String คั่นด้วย comma ให้เป็น List
            for d, item in parsed.items():
                if isinstance(item.get("hosts"), str):
                    item["hosts"] = [h.strip() for h in item["hosts"].split(",")]
            return parsed
        except Exception as e:
            logger.error("Failed to parse DOMAINS_CONFIG JSON: %s", e)
    return _DEFAULT_DOMAINS_CONFIG


def _build_server_pool(hosts: list) -> ServerPool:
    """สร้าง ServerPool สำหรับ LDAP connection (failover) ตามรายชื่อ hosts"""
    servers = []
    for host in hosts:
        servers.append(Server(host, use_ssl=False, connect_timeout=3))
        servers.append(Server(host, use_ssl=True, connect_timeout=3))
    return ServerPool(servers, pool_strategy=FIRST, active=True, exhaust=True)


def authenticate_ad(username: str, password: str) -> dict:
    """
    Authenticate user กับ Active Directory ด้วย NTLM bind (รองรับ username@domain.com และ sAMAccountName ทั่วไป)

    ขั้นตอน:
      1. แยก username และ domain (ถ้าพิมพ์แค่ name จะ fallback เป็น domain แรกใน config)
      2. NTLM bind ด้วย user credentials ของ domain นั้นๆ
      3. ใช้ service account ของ domain นั้นๆ query user info + group membership
      4. ตรวจความเป็นสมาชิกใน group ที่กำหนดของ domain นั้นๆ

    Returns:
        dict ที่มี username, display_name, first_name, last_name, email, groups
    """
    # ── Step 1: แยก username และ domain ──
    username_str = username.strip()
    if "@" in username_str:
        sam_account_name, domain_key = username_str.split("@", 1)
        domain_key = domain_key.lower().strip()
    else:
        sam_account_name = username_str
        # fallback เป็น domain แรกใน config
        config = get_domains_config()
        domain_key = list(config.keys())[0] if config else "aapico.com"

    config = get_domains_config()
    if domain_key not in config:
        supported = ", ".join(config.keys())
        raise ValueError(f"Domain '{domain_key}' is not supported. Supported: {supported}")

    dom_cfg = config[domain_key]
    hosts = dom_cfg.get("hosts", [])
    base_dn = dom_cfg.get("base_dn", "")
    ntlm_domain = dom_cfg.get("ntlm_domain", "")
    svc_user = dom_cfg.get("svc_user", "")
    svc_pass = dom_cfg.get("svc_pass", "")
    required_group = dom_cfg.get("required_group", "Domain Admins")

    pool = _build_server_pool(hosts)

    # ── Step 2: Bind ด้วย user credentials เพื่อ verify password ──
    try:
        user_bind = f"{ntlm_domain}\\{sam_account_name}"
        conn = Connection(
            pool,
            user=user_bind,
            password=password,
            authentication=NTLM,
            auto_bind=True,
            read_only=True,
        )
        conn.unbind()
    except LDAPBindError:
        raise ValueError("Invalid username or password")
    except LDAPException as e:
        logger.error("LDAP bind error on domain %s: %s", domain_key, e)
        raise ValueError("Authentication service unavailable")
    except Exception as e:
        logger.error("Unexpected auth error on domain %s: %s", domain_key, e)
        raise ValueError("Authentication service unavailable")

    # ── Step 3: ใช้ service account query user info + groups ──
    try:
        svc_conn = Connection(
            pool,
            user=svc_user,
            password=svc_pass,
            authentication=NTLM,
            auto_bind=True,
            read_only=True,
        )

        svc_conn.search(
            search_base=base_dn,
            search_filter=f"(&(objectClass=user)(objectCategory=person)(sAMAccountName={sam_account_name}))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName",
                "displayName",
                "mail",
                "memberOf",
                "givenName",
                "sn",
            ],
        )

        if not svc_conn.entries:
            svc_conn.unbind()
            raise ValueError("User not found in directory")

        entry = svc_conn.entries[0]
        display_name = str(entry.displayName) if entry.displayName else sam_account_name
        email = str(entry.mail) if entry.mail else ""
        first_name = str(entry.givenName) if entry.givenName else ""
        last_name = str(entry.sn) if entry.sn else ""
        member_of = entry.memberOf.values if entry.memberOf else []

        svc_conn.unbind()

    except ValueError:
        raise
    except Exception as e:
        logger.error("LDAP query error on domain %s: %s", domain_key, e)
        raise ValueError("Failed to retrieve user information")

    # ── Step 4: ตรวจ group membership ──
    is_admin = any(
        f"CN={required_group}," in str(group)
        for group in member_of
    )

    if not is_admin:
        raise ValueError(
            f"Access denied — your account is not a member of '{required_group}'"
        )

    # ── แปลง group DNs ──
    groups = []
    for dn in member_of:
        dn_str = str(dn)
        if dn_str.startswith("CN="):
            groups.append(dn_str.split(",")[0].replace("CN=", ""))

    return {
        "username": sam_account_name,
        "domain": domain_key,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "groups": groups,
    }


def get_supported_domains() -> list:
    """คืนค่าลิสต์รายชื่อ Domain ทั้งหมดที่ถูกตั้งค่าไว้"""
    return list(get_domains_config().keys())


def create_token(username: str, display_name: str, first_name: str = "", last_name: str = "", email: str = "", domain: str = "") -> str:
    """สร้าง JWT token"""
    payload = {
        "sub": username,
        "domain": domain,
        "name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired — please login again")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
