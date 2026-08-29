# Food Ordering Platform & POS

A comprehensive full-stack application providing a complete ecosystem for food service management. It includes a Customer Storefront (B2C/B2B), a Point of Sale (POS) system, a Kitchen Display System (KDS), and a full Admin Dashboard.

## 🚀 Key Features

*   **Customer Storefront:** Browse menus, dynamic product detail pages, shopping cart, guest checkout, wallet system, coupon catalog, and order tracking.
*   **Point of Sale (POS):** Fast order entry, POS lock screen, QR code generation, walk-in customer management, and receipt generation.
*   **Kitchen Display System (KDS):** Real-time order synchronization for the kitchen, status toggling, and ticket management.
*   **Admin & Management:** Granular audit logs, inventory management, role-based access control, bestseller tracking, and dynamic policy pages.
*   **Security (Zero Trust):** Robust zero-trust schemas, strict JWT token validation with Redis blocklisting, token versioning, and rate limiting.

## 🏗️ Architecture & Tech Stack

*   **Backend:** Python, Flask, SQLAlchemy (ORM), Flask-Migrate (Alembic), JWT Authentication, Redis, APScheduler (Background jobs)
*   **Customer Frontend:** React (Vite), Tailwind CSS
*   **Admin/POS Frontend:** React (Vite), Tailwind CSS

## 💻 Getting Started (Local Development)

### 1. Clone the repository
```bash
git clone <your-repository-url>
cd food
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
# Make sure to create a .env file for your database and secrets!
flask db upgrade
flask run
```

### 3. Frontend Setup (Admin & Customer)
Open a new terminal for the admin dashboard:
```bash
cd frontend-admin
npm install
npm run dev
```

Open another terminal for the customer storefront:
```bash
cd frontend-customer
npm install
npm run dev
```

## ⚙️ Deployment & Production Requirements

### Environment Variables (Backend)

*   `FLASK_ENV`: Set to `production` in live environments.
*   `SECRET_KEY`: **Required.** Used for session signing, QR code generation, etc.
*   `JWT_SECRET_KEY`: **Required.** Used for JWT signature.
*   `REDIS_URL`: **Required in production.** Used for JWT token blocklisting (e.g., `redis://localhost:6379/0`).
*   `ALLOW_SEED=1`: (Optional) Use only if you intentionally want demo seeds.
*   `DATABASE_URL`: (Optional) Full connection string. Defaults to SQLite if not provided (except in production).
*   **MySQL Variables (Alternative to `DATABASE_URL`)**:
    *   `MYSQL_HOST`: e.g., `localhost`
    *   `MYSQL_USER`: Database username
    *   `MYSQL_PASSWORD`: Database password
    *   `MYSQL_DB`: Database name
*   **Mail Variables**:
    *   `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `ADMIN_EMAIL`

### Redis Requirement

**Redis is strictly required in production (`FLASK_ENV=production`).** The application uses Redis for token revocation (blocklist) and rate-limiting. If `REDIS_URL` is missing or the Redis instance cannot be pinged on startup, the application will refuse to start.

To run Redis locally via Docker:
```bash
docker run --name my-redis -p 6379:6379 -d redis
```

## 🗄️ Database Migrations

The project uses `Flask-Migrate` (Alembic) to handle database schema changes.

When deploying a new version with schema changes, you can simply run:
```bash
flask db upgrade
```
*(Note: Manual `ALTER TABLE` commands are no longer needed as Alembic handles schema evolution automatically).*

## 🔐 Authentication & JWT Lifecycle

*   **Access Token**: Expires in 15 minutes.
*   **Refresh Token**: Expires in 7 days.
*   **Endpoints**:
    *   `POST /api/auth/login`: Returns `access_token` + `refresh_token`.
    *   `POST /api/auth/refresh`: Accepts `Authorization: Bearer <refresh_token>` and returns a new `access_token` and `refresh_token`.
    *   `POST /api/auth/logout`: Accepts `Authorization: Bearer <access_token>` and body `{"refresh_token": "<token>"}` to revoke tokens using the Redis blocklist.

## 💳 Online Payments (Razorpay)

The backend ships a complete, self-hosting Razorpay integration. Credentials live in
`StoreSetting` (Fernet-encrypted with `PAYMENT_ENCRYPTION_KEY`) and are managed from
**Admin → Payment Gateway**. A documented env-var fallback also exists:
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_MODE`, `RAZORPAY_ENABLED`.

### Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/payments/razorpay/order` | JWT | Creates a Razorpay order for a customer's pending order, stores `razorpay_order_id`, returns `{razorpay_order_id, amount, currency, key_id, mode}` for checkout.js |
| `POST /api/payments/razorpay/verify` | JWT | Verifies the checkout.js HMAC signature (`order_id\|payment_id`), marks the order `payment_status='paid'`, records an audit row. Idempotent |
| `POST /api/payments/razorpay/webhook` | X-Razorpay-Signature | Server-to-server events (`payment.captured`, `payment.failed`, `refund.processed`, `order.paid`). Marks orders paid even if the browser closes mid-payment |

### Customer flow

1. Customer places an order choosing **Pay Online** (or taps **Pay Now** on a pending order in *My Orders*).
2. Frontend calls `/payments/razorpay/order`, then opens the Razorpay checkout window.
3. On success the frontend posts the signature to `/payments/razorpay/verify`.
4. The webhook acts as a safety net — both paths are idempotent, so an order is never double-charged or double-marked.

Every payment event is written to the `payment_transactions` table (source: `checkout` or `webhook`,
including invalid-signature attempts) for reconciliation.

## 🛡️ Security & Privacy Notes

*   **Ticket Attachments**: Ticket attachment URLs are located under `/static/uploads/tickets/`. Currently, these URLs are unguessable due to timestamp prefixing.
*   **Token Caching**: For improved performance at scale, it is recommended to cache `user.token_version` in Redis using a short TTL and invalidate it upon password change.

## 🧪 Running Tests

To run the backend test suite, navigate to the `backend` directory and use pytest:
```bash
cd backend
REDIS_URL=memory:// python -m pytest tests/ -v --tb=short
```
