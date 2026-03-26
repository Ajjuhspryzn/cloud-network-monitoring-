"""
monitor.py — Network check functions (ping + HTTP) and background monitoring loop.
"""

from typing import Optional, Tuple
import time
import asyncio
import logging
import requests
from datetime import datetime

# ping3 wraps ICMP ping; requires admin on Windows
try:
    import ping3
    PING_AVAILABLE = True
except ImportError:
    PING_AVAILABLE = False

import database as db
from alerts import fire_alert

logger = logging.getLogger("monitor")

# Previous status cache so we only alert on *changes*
_prev_status: dict[int, str] = {}


# ── Individual checks ────────────────────────────────────────────────────────

def ping_device(host: str, timeout: int = 3) -> Tuple[str, Optional[float]]:
    """
    ICMP ping a host.
    Returns ('online', latency_ms) or ('offline', None).
    Falls back to TCP port 80 probe if ping3 unavailable or ping blocked.
    """
    if PING_AVAILABLE:
        try:
            latency = ping3.ping(host, timeout=timeout, unit="ms")
            if latency is not None and latency is not False:
                return "online", round(float(latency), 2)
        except Exception:
            pass

    # Fallback: TCP connect to port 80
    import socket
    start = time.time()
    try:
        with socket.create_connection((host, 80), timeout=timeout):
            latency_ms = round((time.time() - start) * 1000, 2)
            return "online", latency_ms
    except Exception:
        pass

    return "offline", None


def check_http(url: str, timeout: int = 5) -> Tuple[str, Optional[float]]:
    """
    HTTP GET check.
    Returns ('online', latency_ms) or ('offline', None).
    """
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        start = time.time()
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        latency_ms = round((time.time() - start) * 1000, 2)
        if resp.status_code < 500:
            return "online", latency_ms
        return "offline", latency_ms
    except requests.RequestException:
        return "offline", None


# ── Single device check ──────────────────────────────────────────────────────

def check_device(device: dict) -> dict:
    """
    Run the appropriate check for a device and persist the result.
    Returns a result dict with status, latency_ms, checked_at.
    """
    device_id = device["id"]
    host = device["host"]
    dev_type = device.get("type", "http")

    if dev_type == "ping":
        status, latency_ms = ping_device(host)
    else:
        status, latency_ms = check_http(host)

    # Persist to DB
    db.insert_log(device_id, status, latency_ms)

    # Fire alerts only on status change
    prev = _prev_status.get(device_id)
    if prev is not None and prev != status:
        fire_alert(device["name"], host, status)
    _prev_status[device_id] = status

    result = {
        "device_id": device_id,
        "name": device["name"],
        "host": host,
        "type": dev_type,
        "status": status,
        "latency_ms": latency_ms,
        "checked_at": datetime.utcnow().isoformat(),
    }
    logger.info(
        "[%s] %s (%s) — %s, %.1f ms",
        result["checked_at"][:19],
        device["name"],
        host,
        status,
        latency_ms or 0,
    )
    return result


# ── Background monitoring loop ───────────────────────────────────────────────

async def monitoring_loop(interval: int = 10):
    """
    Async loop that checks every tracked device every `interval` seconds.
    Run this as an asyncio background task from FastAPI's lifespan.
    """
    logger.info("Monitoring loop started (interval=%ds)", interval)
    while True:
        devices = db.get_devices()
        tasks = [asyncio.to_thread(check_device, dev) for dev in devices]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(interval)
