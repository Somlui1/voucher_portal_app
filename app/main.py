import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from .routers.SOS import SOS
from .routers.auth import router as auth_router

app = FastAPI(
    title="AAPICO Voucher Portal API",
    description="Backend API for the AAPICO Wifi Voucher Portal",
    version="1.0.0"
)

# Jinja2 template setup for root route
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "component")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include only the relevant routers for the Voucher Portal
app.include_router(auth_router)
app.include_router(SOS)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    เสิร์ฟหน้าจอหลัก (Voucher Portal UI) เมื่อเข้าสู่ Root Path (/)
    """
    template = jinja_env.get_template("vocher_portal_application.html")
    html_content = template.render()
    return HTMLResponse(content=html_content)
