# 🌐 Cloud-Based Network Monitoring System

> Real-time monitoring of servers, websites, and network devices — with a beautiful dashboard, latency graphs, uptime tracking, and alert notifications.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Browser (Dashboard)                 │
│              frontend/index.html                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ Login UI │  │ Device   │  │ Charts (Chart.js)  │ │
│  │  (JWT)   │  │  Table   │  │ Latency / Uptime   │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
└───────────────────────┬──────────────────────────────┘
                        │ REST API (HTTP/JSON)
┌───────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                     │
│                    app.py                            │
│  ┌─────────────┐  ┌────────────┐  ┌───────────────┐ │
│  │  auth.py    │  │ monitor.py │  │  alerts.py    │ │
│  │  (JWT auth) │  │ (ping/HTTP)│  │ (log + email) │ │
│  └─────────────┘  └────┬───────┘  └───────────────┘ │
│                        │                             │
│              ┌─────────▼────────┐                   │
│              │   database.py    │                   │
│              │ (SQLite via      │                   │
│              │  data/monitor.db)│                   │
│              └──────────────────┘                   │
└──────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
cloud ess proj/
├── app.py           ← FastAPI app + background monitoring loop
├── monitor.py       ← Ping & HTTP check functions
├── database.py      ← SQLite setup and all DB operations
├── auth.py          ← JWT authentication
├── alerts.py        ← File logging + optional email alerts
├── requirements.txt ← Python dependencies
├── .env             ← Credentials (admin user, SMTP, secret key)
├── data/
│   ├── monitor.db   ← SQLite database (auto-created)
│   └── alerts.log   ← Alert log file (auto-created)
└── frontend/
    └── index.html   ← Self-contained dashboard (no build step!)
```

---

## 🚀 Local Setup

### 1. Prerequisites
- Python 3.10+
- `pip`
- A modern browser

### 2. Install dependencies

```bash
cd "cloud ess proj"
pip install -r requirements.txt
```

### 3. Configure environment (optional)

Edit `.env` to change admin credentials or enable email alerts:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=supersecretkey123456789

# Optional email alerts
SMTP_USER=your@gmail.com
SMTP_PASS=your_app_password
ALERT_EMAIL=alerts@example.com
```

### 4. Start the backend

```bash
python app.py
```

The backend will:
- Auto-create `data/monitor.db` with 4 sample devices
- Start checking all devices every 10 seconds
- Serve the API at `http://localhost:8000`

Interactive API docs: **http://localhost:8000/docs**

### 5. Open the dashboard

Simply open `frontend/index.html` in your browser.

> **Default login:** `admin` / `admin123`

No Node.js required — the frontend is a single HTML file.

---

## 📡 Pre-seeded Sample Devices

| Name | Host | Type |
|------|------|------|
| Google | https://google.com | HTTP |
| GitHub | https://github.com | HTTP |
| Cloudflare DNS | 8.8.8.8 | Ping |
| OpenDNS | 208.67.222.222 | Ping |

---

## 🔌 REST API Reference

All endpoints (except `/login` and `/health`) require a **Bearer token**.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/login` | Authenticate, get JWT token |
| `GET`  | `/devices` | List all devices with current status |
| `POST` | `/devices` | Add a new device |
| `DELETE` | `/devices/{id}` | Remove a device |
| `GET`  | `/devices/{id}/logs` | Get historical logs for charts |
| `GET`  | `/health` | Health check (no auth) |

### Example: Add a device

```bash
# Get token first
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -d "username=admin&password=admin123" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Add device
curl -X POST http://localhost:8000/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Server", "host": "192.168.1.1", "type": "ping"}'
```

---

## ☁️ Deploying to the Cloud (Render.com — Free)

1. Push this project to a GitHub repository
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your repo
4. Set:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `python app.py`
5. Add environment variables from `.env` in Render's dashboard
6. Deploy! Render gives you a public URL like `https://netmonitor-xyz.onrender.com`
7. Update `const API = '...'` in `frontend/index.html` to your Render URL

> The SQLite database will reset on each deploy. For persistence, swap `database.py` to use **PostgreSQL** (Render provides a free PG instance) or **Firebase**.

---

## 🔔 Alert System

When a device changes status (online → offline or vice versa):
- A log entry is written to `data/alerts.log`
- An email is sent if `SMTP_USER`, `SMTP_PASS`, and `ALERT_EMAIL` are set in `.env`

To use Gmail SMTP, enable **2FA** and create an [App Password](https://support.google.com/accounts/answer/185833).

---

## ✨ Features

- ✅ **Real-time monitoring** — ping (ICMP + TCP fallback) and HTTP checks every 10 seconds
- 📊 **Latency history charts** — line graph for the last 60 checks per device
- 🎯 **Uptime percentage** — calculated over the last 100 checks
- 🔐 **JWT authentication** — secure login page with token-based sessions
- 🔔 **Alert system** — file log + optional email notifications on status change
- 📱 **Responsive design** — works on desktop and mobile
- ⚡ **No build step** — frontend is a single HTML file

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, FastAPI, Uvicorn |
| Networking | ping3, socket, requests |
| Database | SQLite (built-in) |
| Auth | JWT (python-jose + passlib) |
| Frontend | Vanilla HTML/JS/CSS |
| Charts | Chart.js 4 (CDN) |
| Deploy | Render / Railway / AWS EC2 |
