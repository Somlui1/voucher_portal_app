import os
import requests
from dotenv import load_dotenv
from fastapi import HTTPException

# 1. โหลดค่าตัวแปรจากไฟล์ .env
load_dotenv()


def get_access_token() -> str:

    app_id = os.getenv("Ruijie_APP_ID")
    app_secret = os.getenv("Ruijie_APP_SECRET")
    
    if not all([app_id, app_secret]):
        # ส่ง Error กลับไปหา Client ทันทีถ้า .env ไม่ครบ
        raise HTTPException(status_code=500, detail={"step": "1_get_access_token", "error": "ไม่พบข้อมูล Credentials ในไฟล์ .env"})
        
    url = "https://cloud-as.ruijienetworks.com/service/api/oauth20/client/access_token"
    params = {"token": "d63dss0a81e4415a889ac5b78fsc904a"}
    headers = {"Content-Type": "application/json"}
    payload = {"appid": app_id, "secret": app_secret}
    
    try:
        response = requests.post(url, params=params, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        if response_data.get("code") != 0:
            raise HTTPException(status_code=400, detail={"step": "1_get_access_token", "error": "Ruijie API Error", "ruijie_msg": response_data})
            
        return response_data.get("accessToken")
        
    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "1_get_access_token", "error": "ไม่สามารถติดต่อ Ruijie Server ได้", "server_msg": error_detail})


def get_network_group_id(access_token: str, name: str) -> int:
    name = name.upper()
    url = "https://cloud-as.ruijienetworks.com/service/api/group/single/tree"
    headers = {"Content-Type": "application/json"}
    params = {"depth": "BUILDING", "access_token": access_token}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # ดึงข้อมูลจาก JSON
        groups_data = response.json().get("groups", {})
        subgroups_1 = groups_data.get("subGroups", [])
        if not subgroups_1:
            raise HTTPException(status_code=404, detail={"step": "2_get_network_group", "error": "ไม่พบข้อมูล SubGroups ระดับแรกจาก Ruijie"})
            
        subgroups_2 = subgroups_1[0].get("subGroups", [])
        for i in subgroups_2:
            if i.get("name") == name:
                return i.get("groupId")
                
        # ถ้าวนลูปจนจบแล้วไม่เจอชื่อที่ตรงกัน
        raise HTTPException(status_code=404, detail={"step": "2_get_network_group", "error": f"ไม่พบ Network Group ที่ชื่อ '{name}'"})
        
    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "2_get_network_group", "error": "เกิดข้อผิดพลาดในการดึง Network Group", "server_msg": error_detail})


def get_profile_list_exact(access_token: str, group_id: int, profile_name: str) -> dict:
    url = f"https://cloud-as.ruijienetworks.com/service/api/intl/usergroup/list/{group_id}"
    headers = {"Content-Type": "application/json"}
    params = {"pageIndex": 0, "pageSize": 999999, "access_token": access_token}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        profile_list = response.json().get("data", [])
        if not profile_list:
            raise HTTPException(status_code=404, detail={"step": "3_get_profile", "error": f"Network Group ID {group_id} ไม่มี Profile List (List ว่าง)"})
            
        for profile in profile_list:
            if profile_name == profile.get("name"):
                return profile
                
        raise HTTPException(status_code=404, detail={"step": "3_get_profile", "error": f"ไม่พบ Profile ที่ชื่อ '{profile_name}' ใน Group นี้"})

    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "3_get_profile", "error": "เกิดข้อผิดพลาดในการดึง Profile List", "server_msg": error_detail})


def get_all_network_groups(access_token: str) -> list:
    """
    ดึง Network Groups ทั้งหมดจาก Ruijie Cloud API
    Returns: list ของ dict {name, groupId}
    """
    url = "https://cloud-as.ruijienetworks.com/service/api/group/single/tree"
    headers = {"Content-Type": "application/json"}
    params = {"depth": "BUILDING", "access_token": access_token}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        groups_data = response.json().get("groups", {})
        subgroups_1 = groups_data.get("subGroups", [])
        if not subgroups_1:
            raise HTTPException(status_code=404, detail={"step": "list_groups", "error": "ไม่พบข้อมูล SubGroups จาก Ruijie"})

        subgroups_2 = subgroups_1[0].get("subGroups", [])
        result = []
        for g in subgroups_2:
            result.append({
                "name": g.get("name", ""),
                "groupId": g.get("groupId"),
            })

        return result

    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "list_groups", "error": "เกิดข้อผิดพลาดในการดึง Network Groups", "server_msg": error_detail})


def get_all_profiles(access_token: str, group_id: int) -> list:
    """
    ดึง WiFi Profile ทั้งหมดของ Network Group ที่ระบุ
    Returns: list ของ profile dict
    """
    url = f"https://cloud-as.ruijienetworks.com/service/api/intl/usergroup/list/{group_id}"
    headers = {"Content-Type": "application/json"}
    params = {"pageIndex": 0, "pageSize": 999999, "access_token": access_token}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        profile_list = response.json().get("data", [])
        result = []
        for p in profile_list:
            period_minutes = p.get("timePeriod", 0)
            period_day = period_minutes / 60 / 24 if period_minutes else 0
            download_kbps = p.get("downloadRateLimit", 0)
            mbps_rate = download_kbps / 1024 if download_kbps else 0

            result.append({
                "name": p.get("name", ""),
                "id": p.get("id"),
                "authProfileId": p.get("authProfileId"),
                "concurrent_devices": p.get("noOfDevice", 1),
                "period": f"{round(period_day, 1)}Day",
                "maximum_download_rate": f"{round(mbps_rate, 1)}Mbps",
            })

        return result

    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "list_profiles", "error": "เกิดข้อผิดพลาดในการดึง Profile List", "server_msg": error_detail})


def generate_vocher(
    access_token: str, 
    group_id: int, 
    profile_id: str, 
    quantity: int, 
    user_group_id: int,
    first_name: str = None,
    last_name: str = None,
    email: str = None,
    phone: str = None,
    comment: str = None
) -> dict:
    url = f"https://cloud-as.ruijienetworks.com/service/api/open/auth/voucher/create/{group_id}"
    headers = {"Content-Type": "application/json"}
    query_params = {"access_token": access_token}
    payload = {
        "quantity": quantity,
        "profile": str(profile_id), # แปลงเป็น string ป้องกัน Error 
        "userGroupId": user_group_id,
    }

    if first_name is not None:
        payload["firstName"] = first_name
    if last_name is not None:
        payload["lastName"] = last_name
    if email is not None:
        payload["email"] = email
    if phone is not None:
        payload["phone"] = phone
    if comment is not None:
        payload["comment"] = comment
    
    try:
        response = requests.post(url, headers=headers, params=query_params, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # ตรวจสอบ Code ภายในของ Ruijie ว่าสำเร็จจริงๆ หรือไม่
        if result.get("code") != 0:
            raise HTTPException(status_code=400, detail={"step": "4_generate_voucher", "error": "Ruijie ปฏิเสธการสร้าง Voucher", "ruijie_msg": result})
            
        return result
        
    except requests.exceptions.RequestException as e:
        error_detail = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=502, detail={"step": "4_generate_voucher", "error": "เกิดข้อผิดพลาดขณะสร้าง Voucher", "server_msg": error_detail})


def create_voucher_endpoint(
        groupname: str, profile_name: str, quantity: int,
        first_name: str = None, last_name: str = None,
        email: str = None, phone: str = None, comment: str = None
    ):
        """
        API สำหรับสร้าง Voucher โดยส่ง Parameter ผ่าน Query URL
        """

        response = {
            "voucher_code": "",
            "profile_name": "",
            "concurrent_devices": 1,
            "period": "1Days",
            "maximum_download_rate": "20Mbps",
            "logo_url": ""
        }


        # Step 1: ดึง Access Token
        access_token = get_access_token()
        # Step 2: หา Network Group ID
        network_group_id = get_network_group_id(access_token=access_token, name=groupname)
        # Step 3: หาข้อมูล Profile
        profile = get_profile_list_exact(access_token=access_token, group_id=network_group_id, profile_name=profile_name)
        
        # เตรียมตัวแปรเพื่อใช้สร้าง Voucher (และเช็คว่าได้มาครบไหม)
        profile_id = profile.get("authProfileId")
        user_group_id = profile.get("id")
        
        if not profile_id or not user_group_id:
            raise HTTPException(status_code=500, detail={"step": "3_get_profile", "error": "Profile ที่ได้มาไม่มีฟิลด์ 'authProfileId' หรือ 'id'"})
        
        # Step 4: สร้าง Voucher
        voucher_result = generate_vocher(
            access_token=access_token,
            group_id=network_group_id,
            profile_id=profile_id,
            quantity=quantity,
            user_group_id=user_group_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            comment=comment
        )
         
        list_ticket = []
        for ticket in voucher_result.get("voucherData", {}).get("list", []):
            # คำนวณค่าต่างๆ เตรียมไว้
            period_day = profile.get("timePeriod", 0) // 60 // 24
            mbps_rate = profile.get("downloadRateLimit", 0) // 1024
            response = {
                "voucher_code": ticket.get("codeNo"),
                "profile_name": profile.get("name"),
                "concurrent_devices": profile.get("noOfDevice"),
                "period_hours": str(round(period_day, 1)) + 'Day', 
                "maximum_download_rate_mbps": str(round(mbps_rate, 1)) + 'Mbps',
            }
            list_ticket.append(response)

        return {
            "data": list_ticket
        }
