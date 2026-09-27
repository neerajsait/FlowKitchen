<div align="center">
  <h1>🍀 Food Ordering Platform & POS System</h1>
  <p><i>A full-stack ecosystem for food service management — storefront, POS, kitchen display, and admin dashboard.</i></p>

  <p>
    <img src="https://img.shields.io/badge/Frontend-React%2019-61DAFB?style=flat-square&logo=react" alt="React">
    <img src="https://img.shields.io/badge/Backend-Flask-000000?style=flat-square&logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/Database-MySQL%208-4479A1?style=flat-square&logo=mysql" alt="MySQL">
    <img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=flat-square&logo=redis" alt="Redis">
    <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat-square&logo=docker" alt="Docker">
  </p>
</div>

---

A comprehensive full-stack application for food service businesses: a **Customer Storefront**, a **Point of Sale (POS)** system, a **Kitchen Display System (KDS)**, and a full **Admin Dashboard**.

## Table of Contents

- [Key Features](#-key-features)
- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started (Docker)](#-getting-started-docker---recommended)
- [Local Development](#-local-development-manual-setup)
- [Environment Variables](#-environment-variables)
- [Production Deployment](#-production-deployment)
- [Online Payments (Razorpay)](#-online-payments-razorpay)
- [Testing](#-testing)
- [Security Notes](#-security-notes)
- [License](#-license)

## ✨ Key Features

### Customer Storefront
- Dynamic menus with rich product detail pages
- Guest checkout, secure cart management, and online payments via Razorpay
- Digital wallet, loyalty points, and a coupon catalog
- Real-time order status tracking from kitchen to delivery

### Point of Sale (POS) & Kitchen
- Touch-friendly order entry with QR code generation for walk-ins
- Staff clock-in/out, shift management, and PIN-secured POS lock screens
- Kitchen Display System (KDS) with real-time order sync and ticket management
- Multi-outlet stock depletion and raw material batch tracking

### Security
- JWT auth with token versioning (instant global revocation on password change) and Redis-backed blocklisting
- Rate limiting on sensitive endpoints (login, OTP) backed by Redis
- ORM-parameterized queries, input sanitization, and HTML escaping against SQLi/XSS
- MIME-validated file uploads via `python-magic`
- Fernet-encrypted payment credentials, HMAC-verified payment webhooks

## 🏗 Architecture & Tech Stack

| Component | Technology |
|---|---|
| Backend API | Python, Flask, SQLAlchemy, Alembic, Flask-JWT-Extended, APScheduler |
| Frontend (Customer) | React 19 (Vite), Tailwind CSS |
| Frontend (Admin) | React 19 (Vite), Tailwind CSS, Recharts |
| Database & Cache | MySQL 8.0, Redis |
| Infrastructure | Docker, Docker Compose, Gunicorn |

## 📁 Project Structure

```
.
├── backend/              # Flask API (app.py, models.py, migrations, tests)
├── frontend-customer/    # Customer storefront (React + Vite)
├── frontend-admin/       # Admin dashboard + POS + KDS (React + Vite)
├── docker-compose.yml    # Full stack: backend, MySQL, Redis, both frontends
├── .env.example          # Environment variable template
└── BACKEND_AUTH.md       # Auth flow reference
```

> **Note:** one-off maintenance scripts (`fix_*.py`, `migrate_mysql.py`, `refactor*.py`, `remove_whatsapp.py`, `test_create_staff.py`) live at the repo root for historical reference. They are **not** part of the running application and should not be deployed — see [Security Notes](#-security-notes).

## 🚀 Getting Started (Docker — Recommended)

The fastest way to run the full stack (backend, both frontends, MySQL, Redis):

```bash
git clone <your-repository-url>
cd food

cp .env.example .env
# Edit .env with real secrets before starting

docker-compose up --build -d
```

| Service | URL |
|---|---|
| Customer Storefront | http://localhost:3000 |
| Admin Dashboard | http://localhost:3001 |
| Backend API | http://localhost:5000 |

## 🛠 Local Development (Manual Setup)

**Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Redis is required even in dev (rate limiting, token blocklist)
docker run --name my-redis -p 6379:6379 -d redis:alpine

# Defaults to local SQLite unless MYSQL_* / DATABASE_URL is set
flask db upgrade
flask run
```

**Frontends** (separate terminals)
```bash
cd frontend-admin && npm install && npm run dev
cd frontend-customer && npm install && npm run dev
```

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in real values. Key variables:

| Variable | Required | Purpose |
|---|---|---|
| `FLASK_ENV` | Yes | `production` enforces strict startup checks (fails closed if secrets are missing) |
| `SECRET_KEY` / `JWT_SECRET_KEY` | Yes | Cryptographically random strings — generate fresh per deployment, never reuse dev values |
| `PAYMENT_ENCRYPTION_KEY` | Yes (if using payments) | Fernet key encrypting stored payment credentials |
| `DATABASE_URL` or `MYSQL_*` | Yes | Production database connection |
| `REDIS_URL` | Yes | Token blocklist + rate limiting store |
| `FRONTEND_URL` / `CORS_ORIGINS` | Yes | Comma-separated list of allowed frontend origins |
| `VITE_API_URL` | Yes (frontend build-time) | Backend URL baked into the frontend build — must be set **before** `npm run build` |
| `MAIL_*`, `ADMIN_EMAIL` | Recommended | Transactional email (password resets, order notifications) |

⚠️ **Never commit or share a populated `.env` file.** If one has ever been shared (e.g. zipped and sent elsewhere), rotate every secret in it immediately.

## ⚙️ Production Deployment

This project targets a split deployment: **Flask backend on a VM** (e.g. Oracle Cloud), **both frontends on a static host** (e.g. Netlify).

### Backend (Oracle Cloud / any VM)
1. Provision an instance (e.g. `VM.Standard.A1.Flex`), open port 443 only (plus restricted SSH).
2. Run the backend behind **Gunicorn**, reverse-proxied through **Nginx or Caddy** for TLS termination — never expose Flask's dev server directly.
3. Set all required env vars (`FLASK_ENV=production` and everything in the table above). The app **refuses to start** in production mode if `SECRET_KEY`, `JWT_SECRET_KEY`, `REDIS_URL`, or `DATABASE_URL` are missing.
4. Point `CORS_ORIGINS` / `FRONTEND_URL` at your actual Netlify domains.
5. Schedule regular database backups to object storage.

### Frontends (Netlify)
1. Deploy `frontend-customer` and `frontend-admin` as **two separate Netlify sites**.
2. Set `VITE_API_URL` as a Netlify **build environment variable** pointing to your backend's public HTTPS URL — Vite bakes this in at build time, so a local `.env` value won't carry over.
3. Use distinct subdomains (e.g. `app.yourdomain.com`, `admin.yourdomain.com`).

### Docker Compose Hardening (if self-hosting the whole stack)
- Resource limits (`cpus`, `memory`) prevent runaway processes
- Healthchecks on MySQL, Redis, and backend ensure safe startup ordering
- Log rotation (10MB × 3 files) via the `json-file` driver
- Cross-process file locking so APScheduler jobs (daily reports, ticket cleanup) run exactly once across Gunicorn workers

## 💳 Online Payments (Razorpay)

Credentials are stored encrypted (Fernet, via `PAYMENT_ENCRYPTION_KEY`) in `StoreSetting` and managed from **Admin → Payment Gateway**.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/payments/razorpay/order` | JWT | Creates a Razorpay order, returns keys for checkout |
| `POST /api/payments/razorpay/verify` | JWT | Verifies HMAC signature, marks order paid (idempotent) |
| `POST /api/payments/razorpay/webhook` | Signature | Server-to-server fallback, marks orders paid even if the browser closes |

Every payment event is logged to `payment_transactions` for reconciliation.

## 🧪 Testing

```bash
cd backend
REDIS_URL=memory:// python -m unittest discover tests/ -v
```

`REDIS_URL=memory://` avoids polluting the real Redis cache during test runs.


## 📄 License

Add your license here (e.g. MIT, proprietary/all rights reserved) before distributing this project.