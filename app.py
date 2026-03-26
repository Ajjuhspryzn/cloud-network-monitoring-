"""
app.py — FastAPI application entry point.
Uses FastAPI 0.103.2 + Pydantic v1 for Python 3.9 compatibility.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database as db
from monitor import monitoring_loop
from auth import authenticate_user, create_access_token, get_current_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ── Lifespan: init DB + start background monitor ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(monitoring_loop(interval=10))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cloud Network Monitor API",
    description="Real-time network device monitoring with ping & HTTP checks.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic v1 schemas ───────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str
    host: str
    type: str = "http"


class DeviceCreated(BaseModel):
    id: int
    name: str
    host: str
    type: str

    class Config:
        orm_mode = True


class DeviceOut(BaseModel):
    id: int
    name: str
    host: str
    type: str
    added_at: str
    status: str = "unknown"
    latency_ms: Optional[float] = None
    checked_at: Optional[str] = None
    uptime_pct: float = 0.0

    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    detail: str


class LogEntry(BaseModel):
    id: int
    device_id: int
    status: str
    latency_ms: Optional[float] = None
    checked_at: str

    class Config:
        orm_mode = True


class DeviceLogsResponse(BaseModel):
    device: DeviceCreated
    logs: List[LogEntry]
    uptime_pct: float


# ── Auth endpoint ─────────────────────────────────────────────────────────────

@app.post("/login", response_model=TokenResponse, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate with username/password and receive a JWT token."""
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": form_data.username})
    return TokenResponse(access_token=token)


# ── Device endpoints ──────────────────────────────────────────────────────────

@app.get("/devices", response_model=List[DeviceOut], tags=["Devices"])
def list_devices(_: str = Depends(get_current_user)):
    """Return all devices with their latest monitoring status."""
    devices = db.get_devices()
    result = []
    for dev in devices:
        latest = db.get_latest_status(dev["id"])
        uptime = db.compute_uptime(dev["id"])
        result.append(DeviceOut(
            id=dev["id"],
            name=dev["name"],
            host=dev["host"],
            type=dev["type"],
            added_at=dev["added_at"],
            status=latest["status"] if latest else "unknown",
            latency_ms=latest["latency_ms"] if latest else None,
            checked_at=latest["checked_at"] if latest else None,
            uptime_pct=uptime,
        ))
    return result


@app.post("/devices", response_model=DeviceCreated, status_code=201, tags=["Devices"])
def create_device(body: DeviceCreate, _: str = Depends(get_current_user)):
    """Add a new device to monitor."""
    if body.type not in ("http", "ping"):
        raise HTTPException(400, detail="type must be 'http' or 'ping'")
    device = db.add_device(body.name, body.host, body.type)
    return DeviceCreated(**device)


@app.delete("/devices/{device_id}", response_model=MessageResponse, tags=["Devices"])
def delete_device(device_id: int, _: str = Depends(get_current_user)):
    """Remove a device from monitoring."""
    if not db.remove_device(device_id):
        raise HTTPException(404, detail="Device not found")
    return MessageResponse(detail="Device removed")


@app.get("/devices/{device_id}/logs", response_model=DeviceLogsResponse, tags=["Devices"])
def device_logs(device_id: int, limit: int = 60, _: str = Depends(get_current_user)):
    """Return recent monitoring logs for a specific device (for charts)."""
    device = db.get_device(device_id)
    if not device:
        raise HTTPException(404, detail="Device not found")
    logs = db.get_logs(device_id, limit=limit)
    uptime = db.compute_uptime(device_id)
    log_entries = [LogEntry(**l) for l in logs]
    device_info = DeviceCreated(
        id=device["id"], name=device["name"],
        host=device["host"], type=device["type"]
    )
    return DeviceLogsResponse(device=device_info, logs=log_entries, uptime_pct=uptime)


# ── System endpoints (no auth required) ──────────────────────────────────────

@app.get("/", tags=["System"])
def serve_frontend():
    """Serve the frontend dashboard."""
    return FileResponse("frontend/index.html")

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "Cloud Network Monitor"}


# ── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
