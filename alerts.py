"""
alerts.py — Logging and optional email notifications when device status changes.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# File-based alert log
LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "alerts.log")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("alerts")

# Email config (optional — leave SMTP_USER blank to disable)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")


def _write_log(message: str):
    """Append a line to the alerts log file."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def _send_email(subject: str, body: str):
    """Send an email alert if SMTP is configured."""
    if not (SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        return  # Email not configured
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        logger.info("Email alert sent to %s", ALERT_EMAIL)
    except Exception as exc:
        logger.warning("Failed to send email alert: %s", exc)


def fire_alert(name: str, host: str, new_status: str):
    """
    Called whenever a device changes status.
    Logs to file and optionally sends email.
    """
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    emoji = "🔴 DOWN" if new_status == "offline" else "🟢 UP"
    message = f"[{ts}] {emoji} — {name} ({host}) is now {new_status.upper()}"

    logger.warning(message)
    _write_log(message)

    subject = f"[NetMonitor] {name} is {new_status.upper()}"
    body = (
        f"Device Status Change\n"
        f"--------------------\n"
        f"Name   : {name}\n"
        f"Host   : {host}\n"
        f"Status : {new_status.upper()}\n"
        f"Time   : {ts}\n"
    )
    _send_email(subject, body)
