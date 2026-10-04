<div align="center">
  <h1>🍱 FoodPilot — Food Ordering Platform & POS</h1>
  <p><i>A full-stack system for a real food business: customer storefront, POS, kitchen display and admin dashboard.</i></p>

  <p>
    <img src="https://img.shields.io/badge/Frontend-React%2019-61DAFB?style=flat-square&logo=react" alt="React">
    <img src="https://img.shields.io/badge/Backend-Flask-000000?style=flat-square&logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/Database-MySQL%208-4479A1?style=flat-square&logo=mysql" alt="MySQL">
    <img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=flat-square&logo=redis" alt="Redis">
    <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat-square&logo=docker" alt="Docker">
    <img src="https://img.shields.io/badge/Cloud-Oracle%20Cloud-F80000?style=flat-square&logo=oracle&logoColor=white" alt="Oracle Cloud">
  </p>

  <p>
    <a href="https://foodpilot-customer.netlify.app/"><img src="https://img.shields.io/badge/Live-Customer%20App-22c55e?style=for-the-badge" alt="Customer App"></a>
    <a href="https://food-pilot.netlify.app/"><img src="https://img.shields.io/badge/Live-Admin%20%26%20Staff%20Portal-6366f1?style=for-the-badge" alt="Admin Portal"></a>
  </p>
</div>

---

## 🌐 Live Demo

| App | Link |
|---|---|
| Customer storefront | [foodpilot-customer.netlify.app](https://foodpilot-customer.netlify.app/) |
| Admin, POS & kitchen portal | [food-pilot.netlify.app](https://food-pilot.netlify.app/) |

The backend API runs on an **Oracle Cloud** VM. The two frontends are hosted on Netlify.

## ✨ Key Features

**Customer Storefront**
- Dynamic menus with product detail pages
- Guest checkout, cart and online payments via Razorpay
- Wallet, loyalty points and coupons
- Live order status tracking

**POS & Kitchen**
- Touch-friendly order entry with QR codes for walk-ins
- Staff clock-in/out, shifts and PIN-locked POS screens
- Kitchen Display System with real-time order sync
- Multi-outlet stock and raw material batch tracking

**Security**
- JWT auth with token versioning and Redis-backed blocklist
- Redis rate limiting on login and OTP endpoints
- Parameterized queries, input sanitization and HTML escaping
- MIME-validated file uploads
- Fernet-encrypted payment credentials and HMAC-verified webhooks

## 🏗 Tech Stack

| Component | Technology |
|---|---|
| Backend API | Python, Flask, SQLAlchemy, Alembic, Flask-JWT-Extended, APScheduler |
| Customer frontend | React 19 (Vite), Tailwind CSS |
| Admin frontend | React 19 (Vite), Tailwind CSS, Recharts |
| Database & cache | MySQL 8.0, Redis |
| Infrastructure | Docker, Docker Compose, Gunicorn, Oracle Cloud, Netlify |

## 📁 Project Structure

```
.
├── backend/              # Flask API (app.py, models.py, migrations, tests)
├── frontend-customer/    # Customer storefront (React + Vite)
├── frontend-admin/       # Admin dashboard + POS + KDS (React + Vite)
├── docker-compose.yml    # Backend, MySQL, Redis and both frontends
└── .env.example          # Environment variable template
```

## 🚀 Getting Started

### Docker (recommended)

```bash
git clone https://github.com/neerajsait/FoodPilot.git
cd FoodPilot

cp .env.example .env
# Fill in real secrets in .env

docker-compose up --build -d
```

| Service | URL |
|---|---|
| Customer storefront | http://localhost:3000 |
| Admin dashboard | http://localhost:3001 |
| Backend API | http://localhost:5000 |

### Manual setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Redis is required (rate limiting, token blocklist)
docker run --name my-redis -p 6379:6379 -d redis:alpine

flask db upgrade
flask run
```

```bash
# Frontends (separate terminals)
cd frontend-admin && npm install && npm run dev
cd frontend-customer && npm install && npm run dev
```

## 🔑 Environment Variables

Copy `.env.example` to `.env`. Never commit a populated `.env`.

| Variable | Purpose |
|---|---|
| `FLASK_ENV` | `production` enforces strict startup checks |
| `SECRET_KEY` / `JWT_SECRET_KEY` | Random secrets, unique per deployment |
| `PAYMENT_ENCRYPTION_KEY` | Fernet key for stored payment credentials |
| `DATABASE_URL` or `MYSQL_*` | Database connection |
| `REDIS_URL` | Token blocklist and rate limiting |
| `FRONTEND_URL` / `CORS_ORIGINS` | Allowed frontend origins |
| `VITE_API_URL` | Backend URL for the frontends, set before `npm run build` |
| `MAIL_*`, `ADMIN_EMAIL` | Password reset and order emails |

## ⚙️ Deployment

- **Backend:** runs on an Oracle Cloud VM behind Gunicorn and a reverse proxy (HTTPS only). In production mode it refuses to start if required secrets are missing.
- **Frontends:** two separate Netlify sites (customer and admin). Set `VITE_API_URL` as a Netlify build environment variable pointing to the backend's HTTPS URL.
- **CORS:** set `CORS_ORIGINS` / `FRONTEND_URL` to the Netlify domains.

## 💳 Online Payments (Razorpay)

Credentials are stored encrypted and managed from **Admin → Payment Gateway**.

| Endpoint | Purpose |
|---|---|
| `POST /api/payments/razorpay/order` | Create a Razorpay order |
| `POST /api/payments/razorpay/verify` | Verify the signature and mark the order paid |
| `POST /api/payments/razorpay/webhook` | Server-side fallback if the browser closes |

## 🧪 Testing

```bash
cd backend
REDIS_URL=memory:// python -m unittest discover tests/ -v
```

## 👨‍💻 Author

**Tiruveedhi Neeraj Venkata Sai** — [@neerajsait](https://github.com/neerajsait)
