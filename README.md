<div align="center">
  <h1>🍀 Food Ordering Platform & POS System</h1>
  <p><i>A robust, zero-trust full-stack ecosystem for modern food service management.</i></p>
  
  <p>
    <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=flat-square&logo=react" alt="React"></a>
    <a href="https://flasi.palletsprojects.com/"><img src="https://img.shields.io/badge/Backend-Flask-000000?style=flat-square&logo=flask" alt="Flask"></a>
    <a href="https://www.mysql.com/"><img src="https://img.shields.io/badge/Database-MySQL%208-4479A1?style=flat-square&logo=mysql" alt="MySQL"></a>
    <a href="https://redis.io/"><img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=flat-square&logo=redis" alt="Redis"></a>
    <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat-square&logo=docker" alt="Docker"></a>
  </p>
</div>

---

A comprehensive full-stack application providing a complete ecosystem for food service management. It includes a **Customer Storefront (B2C/B2B)**, a **Point of Sale (POS)** system, a **Kitchen Display System (KDS)**, and a full **Admin Dashboard**.

## ✨ Key Features

### 👍 Customer Storefront
- **Dynamic Menus:** Browse menus with rich product detail pages.
- **Seamless Checkout:** Guest checkout, secure cart management, and online payment integrations (Razorpay).
- **Loyalty & Wallet:** Integrated digital wallet, loyalty points, and a comprehensive coupon catalog.
- **Order Tracking:** Real-time order status tracking from kitchen to delivery.

### 🊬 Point of Sale (POS) & Kitchen
- **Fast Order Entry:** Touch-friendly interface with QR code generation for walk-ins.
- **Staff Management:** Clock-in/out tracking, shift management, and secure POS lock screens via staff PINs.
- **Kitchen Display System (KDS):** Real-time order synchronization for the kitchen, status toggling, and ticket management.
- **Stock Tracking:** Multi-outlet stock depletion and raw material batch tracking.

### 🛡 Enterprise-Grade Security
- **Zero-Trust Architecture:** Strict JWT token validation, token versioning (instant global revocation on password change), and Redis-backed JWT blocklisting.
- **Brute-Force & Rate Limiting:** Dynamic endpoint rate-limiting (e.g., 5 login attempts/min) with Redis storage, protecting against credential stuffing and OTP spam.
- **Input Sanitization:** Multi-layered defense against SQLi and XSS via strict payload validation, parameterized ORM queries, and HTML escaping.
- **Secure File Uploads:** Robust multipart sanitization using `python-magic` for MIME-type validation, preventing malicious file executions.

---

## 🏗 Architecture & Tech Stack

|Component|Technology|
|--------|-----------|
|**Backend API**|Python, Flask, SQLAlchemy, Alembic (Migrations), JWT, APScheduler|
|**Frontend (Customer)**|React (Vite), Tailwind CSS, Context API|
|**Frontend (Admin)**|React (Vite), Tailwind CSS, Chart.js (Analytics)|
|**Database & Cache**|MySQL 8.0, Redis (Token blocklist & Rate limits)|
|**Infrastructure**|Docker, Docker Compose, Gunicorn|

---

## 🚀 Getting Started (Docker - Recommended)

The easiest way to run the entire stack (Backend, Frontend, MySQL, and Redis) is using Docker Compose.

1. Clone & Configure
```bash
git clone <your-repository-url>
cd skf

# Ensure your .env file is populated with production secrets
cp .env.example .env
```

2. Start the Stack
```bash
docker-compose up --build -d
```
* **Customer Storefront:** http://localhost:3000
* **Admin Dashboard:** http://localhost:3001
* **Backend API:** http://localhost:5000

---

## 👹 Local Development (Manual Setup)

If you prefer to run the services bare-metal for development:

1. Backend Setup
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Ensure a local Redis instance is running (required for rate limiting):
```bash
docker run --name my-redis -p 6379:6379 -d redis:alpine
```

Start the backend (this will default to a local SQLite database for development; for production, provide MYSQL_* environment variables or DATABASE_URL):
```bash
flask db upgrade
flask run
```

2. Frontend Setup
Run the customer storefront and admin dashboards in separate terminals:
```bash
cd frontend-admin && npm install && npm run dev
cd frontend-customer && npm install && npm run dev
```

---

## ⚹ Production Deployment Guidelines

When deploying to a production server, the application strictly enforces a fail-closed secure state.

### Required Environment Variables
If `FLASK_ENV=production` is set, the application **will refuse to start** unless all of the following are configured and reachable:
* `SECRET_KEY` & `JWT_SECRET_KEY`: Cryptographically secure random strings.
* `REDIS_URL`: Must be reachable for token blocklisting and rate limiting.
* `DATABASE_URL`: Must point to a highly available MySQL instance.
* `FRONTEND_URL`: Used for CORS and email callbacks (e.g. `https://store.example.com,https://admin.example.com`).

### Docker Compose Hardening
The provided `docker-compose.yml` is pre-tuned for production with:
* Resource constraints (`cpus`, `memory` limits) to prevent runaway processes.
* Docker `healthcheck` attributes for MySQL, Redis, and the Backend API to ensure safe startup ordering.
* Log rotation (10MB max, 3 files) via the `json-file` driver.
* Cross-process locking via `fcntl` ensuring APScheduler (daily reports, ticket cleanups) executes exactly once across Gunicorn workers.

---

## 🃱 Online Payments (Razorpay)

The backend ships a complete, self-hosting Razorpay integration. Credentials live in `StoreSetting` (Fernet-encrypted with `PAYMENT_ENCRYPTION_KEY`) and are managed from **Admin → Payment Gateway**.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/payments/razorpay/order` | JWT | Creates a Razorpay order, returns keys for `checkout.js` |
| `POST /api/payments/razorpay/verify` | JWT | Verifies HMAC signature, marks order `paid`. Idempotent. |
| `POST /api/payments/razorpay/webhook` | Signature | Server-to-server fallback. Marks orders paid even if the browser closes. |

Every payment event is written to the `payment_transactions` table for automated financial reconciliation.

---

## 🚕 Testing

The backend includes a comprehensive test suite covering authentication flows, RBAC authorization, business logic, rate limiting, and input sanitization (SQLi/XSS).

To run the test suite:
```bash
cd backend
REDIS_URL=memory:// python -m unittest discover tests/ -v
```
*(Note: `REDIS_URL=memory://` is used during testing to prevent polluting the production Redis cache).*