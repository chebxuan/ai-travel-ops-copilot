"""FastAPI application for the current travel catalogue, quotes and enquiries."""
from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.core.paths import ROOT
from backend.app.routers.travel import create_travel_router

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("请设置环境变量 API_KEY，用于 API 认证")


def get_servers():
    public_url = os.getenv("PUBLIC_URL", "")
    if public_url:
        return [{"url": public_url, "description": "Public server"}]
    return [{"url": "http://localhost:8000", "description": "Local development"}]


app = FastAPI(
    title="AI Travel Ops Copilot API",
    description="Travel product catalogue, itinerary preview, sales estimates and enquiries",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    servers=get_servers(),
)


async def verify_api_key(x_api_key: str = Header(..., description="API 认证密钥")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")
    return x_api_key


app.include_router(create_travel_router(verify_api_key, API_KEY))
from backend.app.routers.operations import router as operations_router
app.include_router(operations_router)


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="running", version="2.1.0", timestamp=datetime.now().isoformat())


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version="2.1.0", timestamp=datetime.now().isoformat())


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "服务器内部错误", "timestamp": datetime.now().isoformat()},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
