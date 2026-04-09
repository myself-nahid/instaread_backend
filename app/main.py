import os
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
os.makedirs("static/profile_pictures", exist_ok=True)
app = FastAPI(
    title="InstaRead AI Backend",
    openapi_url=f"/api/v1/openapi.json"
)
app.mount("/static", StaticFiles(directory="static"), name="static")
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://10.10.12.59:5173",
    "http://10.10.12.59:5173/",
    "http://localhost:5173/"
]

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the QandelShield"}