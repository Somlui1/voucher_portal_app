from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.SOS import SOS
from .routers.auth import router as auth_router

app = FastAPI(
    title="AAPICO Voucher Portal API",
    description="Backend API for the AAPICO Wifi Voucher Portal",
    version="1.0.0"
)

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
