<div align="center">
  <h1>🍀 Food Ordering Platform & POS System</h1>
  <p><i>A robust, zero-trust full-stack ecosystem for modern food service management.</i></p>

  <p>
    <img src="https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=flat-square&logo=react" alt="React">
    <img src="https://img.shields.io/badge/Backend-Flask-000000?style=flat-square&logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/Database-MySQL%208-4479A1?style=flat-square&logo=mysql" alt="MySQL">
    <img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=flat-square&logo=redis" alt="Redis">
    <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat-square&logo=docker" alt="Docker">
    <img src="https://img.shields.io/badge/License-Proprietary-lightgrey?style=flat-square" alt="License">
  </p>
</div>

---

A complete ecosystem for food service management — a **Customer Storefront** (B2C/B2B), a **Point of Sale (POS)** system, a **Kitchen Display System (KDS)**, and a full **Admin Dashboard**, all backed by a single hardened Flask API.

## ✨ Key Features

### 🛒 Customer Storefront
- Dynamic menus with rich product detail pages
- Guest checkout, secure cart management, and online payments via Razorpay
- Digital wallet, loyalty points, and coupon catalog
- Real-time order tracking from kitchen to delivery

### 🧾 Point of Sale (POS) & Kitchen
- Touch-friendly order entry with QR code generation for walk-ins
- Staff clock-in/out tracking, shift management, and PIN-secured POS lock screens
- Kitchen Display System (KDS) with real-time order sync and ticket management
- Multi-outlet stock depletion and raw material batch tracking

### 🛡️ Enterprise-Grade Security
- Zero-trust JWT auth with token versioning (instant global revocation on password change) and Redis-backed blocklisting
- Rate limiting on sensitive endpoints (e.g. 5 login attempts/min) backed by Redis
- Multi-layered input sanitization — parameterized ORM queries, HTML escaping, and strict payload validation
- Secure file uploads validated by MIME type (`python-magic`), not just file extension
- HMAC-verified, timing-safe Razorpay webhook signatures
- Role-based access control (admin / staff / customer) enforced at the route level

## 🏗️ Architecture & Tech Stack

| Component | Technology |
|---|---|
| **Backend API** | Python, Flask, SQLAlchemy, Alembic (migrations), Flask-JWT-Extended, APScheduler |
| **Frontend (Customer)** | React (Vite), Tailwind CSS, Context API |
| **Frontend (Admin)** | React (Vite), Tailwind CSS, Chart.js |
| **Database & Cache** | MySQL 8.0, Redis (token blocklist & rate limits) |
| **Infrastructure** | Docker, Docker Compose, Gunicorn, Nginx (reverse proxy / TLS) |

## 🌐 Production Deployment

| Layer | Provider | Notes |
|---|---|---|
| Backend API | Oracle Cloud Infrastructure (A1 Ampere / Compute VM) | Runs behind Gunicorn + Nginx reverse proxy with TLS |
| Customer Frontend | Netlify | Static Vite build, own subdomain |
| Admin Frontend | Netlify | Static Vite build, separate site/subdomain from customer frontend |
| Database | MySQL 8 (self-hosted on the same VM or a managed instance) | Automated backups via `backup.py` |
| Cache / Rate Limiting | Redis (containerized) | Co-located with backend |

**Required environment configuration for this split:**
- Set `VITE_API_URL` on both Netlify sites to the backend's public HTTPS URL (build-time variable — must be set in Netlify's site settings, not just a local `.env`)
- Add both Netlify domains to `CORS_ORIGINS` on the backend
- Terminate TLS at Nginx/Caddy in front of Gunicorn — never expose the Flask/Gunicorn port directly to the internet
- Restrict the Oracle Cloud Security List/NSG to only the ports actually needed (443, and 22 restricted to your own IP)

## 🚀 Getting Started (Docker — Recommended)

The easiest way to run the entire stack (backend, frontends, MySQL, Redis) locally is Docker Compose.

**1. Clone & configure**
```bash
git clone <your-repository-url>
cd food
cp .env.example .env
# edit .env with your own secrets — never commit this file
```

**2. Launch the stack**
```bash
docker compose up --build -d
```

**3. Apply migrations & (optionally) seed data**
```bash
docker compose exec backend flask db upgrade
```
> Seeding of default admin/staff accounts is automatically disabled when `FLASK_ENV=production` and `ALLOW_SEED=0`.

**4. Access the services**
| Service | URL |
|---|---|
| Backend API | `http://localhost:5000` |
| Customer Frontend | `http://localhost:5173` (or your configured port) |
| Admin Frontend | `http://localhost:5174` (or your configured port) |

## 📁 Project Structure

```
food/
├── backend/              # Flask API (models, auth, orders, payments, admin)
├── frontend-customer/    # Customer-facing React app (Vite)
├── frontend-admin/       # Admin/POS/KDS React app (Vite)
├── docker-compose.yml
└── .env.example
```

## 🔐 Before You Deploy — Security Checklist

- [ ] Rotate `SECRET_KEY`, `JWT_SECRET_KEY`, and mail credentials — never reuse values that were ever committed or shared outside the team
- [ ] Confirm `backend/.env` is git-ignored and was **never** committed to version control history
- [ ] Confirm `FLASK_ENV=production` disables debug mode and default account seeding
- [ ] Confirm `CORS_ORIGINS` is set to your exact production domains, not a wildcard
- [ ] Set up automated database backups (`backend/backup.py`) on a schedule, pointed at durable storage
- [ ] Remove one-off developer/maintenance scripts (`fix_*.py`, `reset*.py`, `migrate_mysql.py`, `test_*.py`) from any production deployment image
- [ ] Set up uptime monitoring for the backend (e.g. UptimeRobot) since it's a single VM with no auto-failover

## 📄 License

Proprietary — all rights reserved. Not licensed for redistribution without written permission.
