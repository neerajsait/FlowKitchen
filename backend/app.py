import os
import io
import json
import time
import base64
import hashlib
import hmac
import random
import logging
from datetime import datetime, timezone, timedelta
from functools import wraps
from decimal import Decimal
from sqlalchemy import select, func, update, or_
import sqlalchemy.exc
import redis
from sqlalchemy.orm import joinedload
from flask import Flask, request, jsonify, Request, send_from_directory, Response
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt, get_jwt_identity,
    create_refresh_token, set_access_cookies, unset_jwt_cookies
)
from redis_client import get_redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import qrcode
from flask_cors import CORS
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet, InvalidToken

from models import (
    db, User, Admin, Customer, Staff, OutletOwner, Outlet, MenuItem, OutletStock,
    Supplier, SupplierItem, StockAuditLog, ProductBatch,
    Order, OrderItem, Review, Coupon, StaffShift, Address, Favorite,
    KitchenStaff, KitchenProductionBatch, WalletTransaction, BroadcastMessage, Banner, StoreSetting, SupportTicket, StockRequest, MarketPurchase,
    AuditLog, MonthlyRevenueHistory, PaymentTransaction
)
import bleach
from audit_utils import log_audit, manual_log_audit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

bcrypt = Bcrypt()

jwt = JWTManager()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    import os
    from redis_client import get_redis
    jti = jwt_payload["jti"]
    token_version = jwt_payload.get("token_version", 0)
    user_id = jwt_payload.get("sub")
    
    redis_client = get_redis()
    if redis_client:
        try:
            token_in_redis = redis_client.get(f"revoked:{jti}")
            if token_in_redis is not None:
                return True
                
            redis_tv = redis_client.get(f"user_tv:{user_id}")
            if redis_tv is not None:
                if int(redis_tv) != token_version:
                    return True
                
                # Harden loader: even if user_tv matches, verify ban/active in DB using a lightweight query.
                # This ensures a stale Redis doesn't allow banned users to skip ban checks.
                try:
                    from models import User
                    flags = db.session.execute(db.select(User.is_banned, User.is_active, User.deleted_at).where(User.id == int(user_id))).first()
                    if flags:
                        is_banned, is_active, deleted_at = flags
                        if is_banned or deleted_at is not None or not is_active:
                            return True
                    else:
                        return True
                except sqlalchemy.exc.SQLAlchemyError as db_err:
                    import logging
                    logging.error(f"Lightweight DB check error: {db_err}")
                    return True

                return False
        except redis.RedisError as e:
            import logging
            logging.error(f"Redis error during blocklist check: {e}")
            if os.getenv("FLASK_ENV") == "production":
                return True
    elif os.getenv("FLASK_ENV") == "production":
        return True

    try:
        from models import User
        user = db.session.get(User, int(user_id)) if user_id else None
        if user:
            db_tv = getattr(user, 'token_version', 0)
            
            if redis_client:
                try:
                    redis_client.setex(f"user_tv:{user_id}", 2 * 86400, db_tv)
                except Exception:
                    pass

            if db_tv != token_version:
                return True
            if getattr(user, 'is_banned', False) or getattr(user, 'deleted_at', None) is not None:
                return True
            if not getattr(user, 'is_active', True):
                return True
        else:
            return True
    except sqlalchemy.exc.SQLAlchemyError as e:
        import logging
        logging.error(f"Error during blocklist db check: {e}")
        return True

    return False

mail = Mail()
redis_url = os.getenv("REDIS_URL")
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url or "memory://",
    storage_options={"protocol": 2} if redis_url and "redis" in redis_url else {}
)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
ALLOWED_MIMETYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf'}

# Minimal content signatures — fallback when libmagic is unavailable
# (e.g. Windows dev machines without the library).
_MAGIC_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
)

def _sniff_mime(header):
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return "image/webp"
    for sig, mime in _MAGIC_SIGNATURES:
        if header.startswith(sig):
            return mime
    return None

def allowed_file(file_obj):
    filename = getattr(file_obj, 'filename', '')
    if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
        return False
    
    try:
        header = file_obj.read(2048)
        file_obj.seek(0)
        try:
            import magic
            mime = magic.from_buffer(header, mime=True)
        except ImportError:
            # python-magic present but libmagic missing (typical bare Windows
            # dev box): fall back to lightweight signature sniffing.
            mime = _sniff_mime(header)
        return mime in ALLOWED_MIMETYPES
    except Exception as e:
        logger.error(f"Magic mime check failed: {e}")
        return False

# --- Ticket attachment hardening ------------------------------------------
TICKET_MAX_FILE_SIZE = 5 * 1024 * 1024       # 5 MB per file (mirrors MAX_CONTENT_LENGTH)
TICKET_USER_TOTAL_QUOTA = 20 * 1024 * 1024   # 20 MB lifetime attachment storage per user
_clamav_warned = False

def _clamav_scan(file_path):
    """Scan a saved file via clamd INSTREAM protocol.

    Returns:
        True  -> clean
        False -> malware detected / scan says infected
        None  -> no scanner configured (or dev-mode skip)

    Raises on connection errors when FLASK_ENV=production (fail closed).
    Configure with CLAMD_HOST (+CLAMD_TCP_PORT, default 3310) or a unix
    CLAMD_SOCKET path.
    """
    global _clamav_warned
    host = os.getenv("CLAMD_HOST")
    socket_path = os.getenv("CLAMD_SOCKET")
    is_production = os.getenv("FLASK_ENV") == "production"
    if not host and not socket_path:
        if not _clamav_warned:
            logger.warning(
                "No malware scanner configured (set CLAMD_HOST or "
                "CLAMD_SOCKET). Ticket attachments are NOT AV-scanned."
            )
            _clamav_warned = True
        return None
    try:
        import socket
        if socket_path:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(socket_path)
        else:
            sock = socket.create_connection((host, int(os.getenv("CLAMD_TCP_PORT", "3310"))), timeout=10)
        try:
            sock.sendall(b"zINSTREAM\0")
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
            sock.sendall((0).to_bytes(4, "big"))
            response = b""
            while True:
                part = sock.recv(4096)
                if not part:
                    break
                response += part
        finally:
            sock.close()
        decoded = response.decode("utf-8", errors="replace").strip("\0 \r\n")
        if decoded.endswith("OK"):
            return True
        logger.warning(f"ClamAV flagged uploaded file: {decoded}")
        return False
    except Exception as e:
        logger.error(f"ClamAV scan unavailable: {e}")
        if is_production:
            raise  # fail closed: never accept unscanned files in production
        return None

def _user_attachment_usage(user_id):
    """Total bytes currently stored on disk for this user's ticket attachments."""
    total = 0
    tickets = db.session.scalars(
        select(SupportTicket).where(SupportTicket.customer_id == user_id)
    ).all()
    for t in tickets:
        if t.attachment_filename:
            p = os.path.join(TICKETS_UPLOAD_FOLDER, t.attachment_filename)
            if os.path.exists(p):
                try:
                    total += os.path.getsize(p)
                except OSError:
                    pass
    return total

def _check_attachment_quota(user_id, incoming_size, replaced_filename=None):
    """Return an error response if this upload would exceed the user's quota."""
    usage = _user_attachment_usage(user_id)
    if replaced_filename:
        old = os.path.join(TICKETS_UPLOAD_FOLDER, replaced_filename)
        if os.path.exists(old):
            try:
                usage -= os.path.getsize(old)
            except OSError:
                pass
    if usage + incoming_size > TICKET_USER_TOTAL_QUOTA:
        return jsonify({
            "error": "Bad Request",
            "message": f"Attachment storage limit exceeded ({TICKET_USER_TOTAL_QUOTA // (1024*1024)} MB per user). Please delete old attachments first."
        }), 400
    return None

def _save_scanned_attachment(file_obj, customer_id, replaced_filename=None):
    """Validate size/quota, save, then AV-scan. On any failure the saved file
    is removed. Returns (unique_name, error_response, status_code) where
    error_response and status_code are None on success."""
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    if size <= 0:
        return None, jsonify({"error": "Bad Request", "message": "Empty attachment"}), 400
    if size > TICKET_MAX_FILE_SIZE:
        return None, jsonify({"error": "Bad Request", "message": "Attachment exceeds 5 MB limit"}), 400
    quota_err = _check_attachment_quota(customer_id, size, replaced_filename=replaced_filename)
    if quota_err:
        return None, quota_err[0], quota_err[1]

    filename = secure_filename(file_obj.filename)
    unique_name = f"{int(datetime.now().timestamp())}_{filename}"
    file_path = os.path.join(TICKETS_UPLOAD_FOLDER, unique_name)
    file_obj.save(file_path)

    try:
        clean = _clamav_scan(file_path)
    except Exception as e:
        try:
            os.remove(file_path)
        except OSError:
            pass
        logger.error(f"Attachment rejected - scanner unavailable: {e}")
        return None, jsonify({"error": "Service Unavailable", "message": "Malware scanner unavailable; upload rejected"}), 503
    if clean is False:
        try:
            os.remove(file_path)
        except OSError:
            pass
        return None, jsonify({"error": "Bad Request", "message": "Attachment failed malware scanning"}), 400
    return unique_name, None, None


# ============================================================
# PAYMENT GATEWAY (Razorpay) — DB-backed credential vault
# Credentials live in StoreSetting; secrets are Fernet-encrypted with a
# master key from PAYMENT_ENCRYPTION_KEY (never stored in the database).
# Resolution order when creating payments: DB first, env vars as fallback
# for first-time setups. A short TTL cache is cleared on every save.
# ============================================================
_razorpay_cache = {"creds": None, "loaded_at": 0.0}
_RAZORPAY_CACHE_TTL = 60  # seconds

def _fernet():
    master = os.getenv("PAYMENT_ENCRYPTION_KEY")
    if not master:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
    return Fernet(key)

def _encrypt_secret(plaintext):
    f = _fernet()
    if f is None:
        raise RuntimeError("PAYMENT_ENCRYPTION_KEY is not configured")
    return f.encrypt(plaintext.encode()).decode()

def _decrypt_secret(ciphertext):
    f = _fernet()
    if f is None:
        raise RuntimeError("PAYMENT_ENCRYPTION_KEY is not configured")
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise RuntimeError(
            "Stored Razorpay secret cannot be decrypted - PAYMENT_ENCRYPTION_KEY "
            "was likely rotated. Re-enter the secret in the Admin UI."
        )

def _setting_value(key, default=None):
    row = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == key)).first()
    return row.setting_value if row else default

def _set_setting(key, value):
    row = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == key)).first()
    if not row:
        db.session.add(StoreSetting(setting_key=key, setting_value=value))
    else:
        row.setting_value = value

def get_razorpay_credentials(force_refresh=False):
    """Resolve Razorpay config: encrypted DB values first, env-var fallback.
    Returns {key_id, key_secret, mode, enabled, webhook_secret, source} or None."""
    now = time.monotonic()
    if (not force_refresh and _razorpay_cache["creds"]
            and now - _razorpay_cache["loaded_at"] < _RAZORPAY_CACHE_TTL):
        return _razorpay_cache["creds"]

    creds = None
    key_id = _setting_value("razorpay_key_id")
    enc_secret = _setting_value("razorpay_key_secret")
    if key_id and enc_secret:
        secret = _decrypt_secret(enc_secret)
        creds = {
            "key_id": key_id,
            "key_secret": secret,
            "mode": _setting_value("razorpay_mode", "test") or "test",
            "enabled": (_setting_value("razorpay_enabled", "false") == "true"),
            "webhook_secret": None,
            "source": "database",
        }
        enc_wh = _setting_value("razorpay_webhook_secret")
        if enc_wh:
            creds["webhook_secret"] = _decrypt_secret(enc_wh)
    else:
        env_id = os.getenv("RAZORPAY_KEY_ID")
        env_secret = os.getenv("RAZORPAY_KEY_SECRET")
        if env_id and env_secret:
            creds = {
                "key_id": env_id,
                "key_secret": env_secret,
                "mode": os.getenv("RAZORPAY_MODE", "test"),
                "enabled": os.getenv("RAZORPAY_ENABLED", "true").lower() == "true",
                "webhook_secret": os.getenv("RAZORPAY_WEBHOOK_SECRET"),
                "source": "environment",
            }

    _razorpay_cache["creds"] = creds
    _razorpay_cache["loaded_at"] = time.monotonic()
    return creds

def clear_razorpay_cache():
    _razorpay_cache["creds"] = None
    _razorpay_cache["loaded_at"] = 0.0

def verify_razorpay_webhook_signature(payload_bytes, signature, webhook_secret):
    """Constant-time verification of Razorpay's X-Razorpay-Signature header."""
    expected = hmac.new(webhook_secret.encode(), payload_bytes or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


TICKETS_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'tickets')
os.makedirs(TICKETS_UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# HELPERS
# ============================================================

def get_loyalty_settings():
    from decimal import Decimal, InvalidOperation
    enabled = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == 'enable_loyalty_program')).first()
    if enabled and enabled.setting_value == 'false':
        return Decimal("0"), Decimal("0")

    earn_rate = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == 'loyalty_earn_rate')).first()
    redeem_rate = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == 'loyalty_redeem_rate')).first()

    def _safe_decimal(raw, fallback):
        try:
            val = Decimal(str(raw))
            return val if val >= 0 else fallback
        except (InvalidOperation, ValueError, TypeError):
            logger.warning(f"Invalid loyalty setting value {raw!r}; falling back to {fallback}")
            return fallback

    earn_val = _safe_decimal(earn_rate.setting_value if earn_rate else None, Decimal("0.1"))
    redeem_val = _safe_decimal(redeem_rate.setting_value if redeem_rate else None, Decimal("0.01"))
    return earn_val, redeem_val

# Loyalty settings keys editable through /api/admin/store-settings, with the
# validation bounds applied by that endpoint.
LOYALTY_SETTING_KEYS = {
    "loyalty_earn_rate":    (0, 10000),   # multiplier: points = amount * rate
    "loyalty_redeem_rate":  (0, 10000),   # rupees per point at redemption
    "loyalty_review_points": (0, 100),    # review bonus as % of item price
}

def role_required(*roles):
    """Decorator: JWT required + role check."""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") not in roles:
                return jsonify({"error": "Forbidden", "message": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def department_required(*departments):
    """Decorator: JWT required + admin role + department check."""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") != "admin":
                return jsonify({"error": "Forbidden", "message": "Admin access required"}), 403
            
            # Superadmin or unspecified department has full access
            if claims.get("is_superadmin"):
                return fn(*args, **kwargs)
                
            user_dept = claims.get("admin_department")
            if user_dept == "SuperAdmin":
                return fn(*args, **kwargs)
            if not user_dept:
                if departments:
                    return jsonify({"error": "Forbidden", "message": "No department assigned. Please contact SuperAdmin."}), 403
                return fn(*args, **kwargs)
                
            if departments and user_dept not in departments:
                return jsonify({"error": "Forbidden", "message": f"Access restricted to departments: {', '.join(departments)}"}), 403
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def validate_public_url(url: str | None) -> bool:
    if not url:
        return True
    u = url.strip().lower()
    if os.getenv("FLASK_ENV") == "production":
        return u.startswith("https://")
    return u.startswith("http://") or u.startswith("https://")

def sanitize_input(data, skip_keys=None):
    if skip_keys is None:
        skip_keys = ["password", "new_password", "old_password", "image_url", "target_url", "icon", "attachment"]
        
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in ["image_url", "target_url", "icon"] and isinstance(v, str) and v.strip():
                if not validate_public_url(v):
                    from werkzeug.exceptions import BadRequest
                    raise BadRequest("Invalid URL scheme")
            result[k] = v if k in skip_keys else sanitize_input(v, skip_keys)
        return result
    elif isinstance(data, list):
        return [sanitize_input(i, skip_keys) for i in data]
    elif isinstance(data, str):
        return bleach.clean(data)
    return data


def validate_phone(phone_str):
    """Strictly sanitize and validate Indian phone numbers."""
    if not phone_str:
        return True, None
        
    phone_str = str(phone_str).strip()
    if not phone_str:
        return True, None
        
    import re
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone_str)
    
    # Strip country code variants
    if cleaned.startswith('91') and len(cleaned) > 10:
        cleaned = cleaned[2:]
        # After stripping 91, it might still have a leading 0 (e.g., +91 09876543210)
        if cleaned.startswith('0') and len(cleaned) > 10:
            cleaned = cleaned[1:]
    elif cleaned.startswith('0') and len(cleaned) > 10:
        cleaned = cleaned[1:]
        
    # Indian mobile numbers must be exactly 10 digits and start with 6, 7, 8, or 9
    if len(cleaned) != 10 or cleaned[0] not in '6789':
        return False, None
        
    return True, cleaned


def log_stock_change(db_session, outlet_id, menu_item_id, change_qty, change_type,
                     stock_before=None, stock_after=None, reference_id=None,
                     performed_by=None, notes=None):
    """Helper to write a StockAuditLog entry."""
    entry = StockAuditLog(
        change_qty=change_qty,
        change_type=change_type,
        outlet_id=outlet_id,
        menu_item_id=menu_item_id,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_id=reference_id,
        performed_by=performed_by,
        notes=notes
    )
    db_session.add(entry)

def log_admin_action(db_session, admin_id, action, target_entity=None, target_id=None, details=None):
    """Helper to write an AuditLog entry for admins."""
    entry = AuditLog(
        actor_id=admin_id,
        actor_role='admin',
        action=action,
        resource_type=target_entity,
        resource_id=target_id,
        new_value=details
    )
    db_session.add(entry)


def _generate_unique_code(db_session):
    """Generate a unique 4-digit numeric product code."""
    for _ in range(1000):
        code = f"{random.randint(1000, 9999)}"
        existing = db_session.scalars(
            select(MenuItem).where(MenuItem.code == code, MenuItem.deleted_at.is_(None))
        ).first()
        if not existing:
            return code
    raise RuntimeError("Unable to generate a unique 4-digit product code after 1000 attempts")


def _generate_order_qr(app, order):
    """Generate a securely signed QR code for an order and save it as base64."""
    import hashlib, hmac
    try:
        qr_payload = {
            "action": "view_order",
            "order_id": order.id,
            "order_type": order.order_type
        }
        serialized = json.dumps(qr_payload, sort_keys=True)
        signature = hmac.new(app.config["SECRET_KEY"].encode(), serialized.encode(), hashlib.sha256).hexdigest()
        qr_payload["signature"] = signature
        
        payload_str = json.dumps(qr_payload)
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(payload_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        # pyrefly: ignore [unexpected-keyword]
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        order.qr_code_base64 = f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.error(f"QR generation failed for order {order.id}: {e}")


# ============================================================
# APP FACTORY
# ============================================================

class SanitizedRequest(Request):
    def get_json(self, *args, **kwargs):
        data = super().get_json(*args, **kwargs)
        if data:
            return sanitize_input(data)
        return data

def create_app(config_override=None):
    app = Flask(__name__)
    app.request_class = SanitizedRequest
    cors_origins = os.getenv("CORS_ORIGINS")
    if os.getenv("FLASK_ENV") == "production" and not cors_origins:
        raise RuntimeError("CORS_ORIGINS must be set in production")
    if cors_origins:
        origins = cors_origins.split(",")
    else:
        origins = os.getenv("FRONTEND_URL", "https://suggulaskitchen.local,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174").split(",")
    # supports_credentials=True is REQUIRED so the HttpOnly refresh-token
    # cookie flows between frontend and API during login/refresh/logout.
    CORS(app, resources={r"/api/*": {"origins": origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-CSRF-TOKEN"])

    # --- Config ---
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("werkzeug")
    
    @app.before_request
    def log_request_info():
        safe_url = request.url
        import re
        safe_url = re.sub(r'((?:token|password|pin|code)=)[^&]+', r'\1[REDACTED]', safe_url, flags=re.IGNORECASE)
        app.logger.info(f"Incoming Request: {request.method} {safe_url}")

    @app.after_request
    def log_response_info(response):
        safe_url = request.url
        import re
        safe_url = re.sub(r'((?:token|password|pin|code)=)[^&]+', r'\1[REDACTED]', safe_url, flags=re.IGNORECASE)
        app.logger.info(f"Outgoing Response: {response.status} for {request.method} {safe_url}")
        
        # Prevent caching for all API responses
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            
        # Security headers handled by add_security_headers
        return response
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        h = os.getenv("MYSQL_HOST")
        u = os.getenv("MYSQL_USER")
        p = os.getenv("MYSQL_PASSWORD")
        d = os.getenv("MYSQL_DB")
        db_url = f"mysql+pymysql://{u}:{p}@{h}/{d}" if all([h, u, p, d]) else None
        if not db_url:
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError("MySQL database credentials must be provided in production.")
            db_url = "sqlite:///food.db"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_recycle": 280, "pool_pre_ping": True}
    
    secret_key = os.getenv("SECRET_KEY")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    if os.getenv("FLASK_ENV") == "production":
        if not secret_key:
            raise RuntimeError("SECRET_KEY must be set in production")
        if not jwt_secret_key:
            raise RuntimeError("JWT_SECRET_KEY must be set in production")
        
        if not os.getenv("REDIS_URL"):
            raise RuntimeError("REDIS_URL must be set in production for JWT blocklist.")
            
        from redis_client import get_redis
        if not get_redis():
            import logging
            logging.error("Redis is unreachable. REDIS_URL is required in production.")
            raise RuntimeError("Redis is required in production for JWT blocklist.")
            
    app.config["SECRET_KEY"] = secret_key or os.urandom(24).hex()
    app.config["JWT_SECRET_KEY"] = jwt_secret_key or os.urandom(24).hex()
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

    # --- Access token as a short-lived HttpOnly cookie ---------------------
    # Tokens are accepted from BOTH the Authorization header (API clients,
    # frontend memory fast-path) and an HttpOnly cookie (browser sessions).
    # Cookie-sourced authentication on state-changing methods is protected by
    # double-submit CSRF (X-CSRF-TOKEN header echoing csrf_access_token).
    is_production = os.getenv("FLASK_ENV") == "production"
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token"
    app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
    app.config["JWT_COOKIE_SAMESITE"] = "Strict"
    app.config["JWT_COOKIE_SECURE"] = is_production
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]


    # Mail config
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USERNAME", "noreply@fooderp.local")
    app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL", "")

    if config_override:
        app.config.update(config_override)
        
    if app.config.get("TESTING") and os.getenv("FLASK_ENV") == "production":
        raise RuntimeError("FATAL: Cannot run with TESTING=True in production environment")

    db.init_app(app)

    # Enforce foreign keys on SQLite (OFF by default!). Without this, the
    # ON DELETE CASCADE / SET NULL actions defined in models.py are ignored
    # in development, which is why raw-SQL delete fallbacks used to be needed.
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        from sqlalchemy import event

        with app.app_context():
            @event.listens_for(db.engine, "connect")
            def _sqlite_fk_pragma_on_connect(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    # IMPORTANT: Real Alembic migration scripts must exist and be applied for:
    # - users.token_version
    # - support_tickets.attachment_filename
    # db.create_all() will NOT add these columns on existing databases.
    migrate = Migrate(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # --- DB Init + Seed ---
    with app.app_context():
        # NOTE: For existing MySQL databases, db.create_all() will NOT add token_version to the users table.
        # Production must run: ALTER TABLE users ADD COLUMN token_version INT NOT NULL DEFAULT 0;
        db.create_all()
        try:
            if os.getenv("FLASK_ENV") != "production" or os.getenv("ALLOW_SEED") == "1":
                _seed_admin(app)
            # Bootstrap: assign 4-digit codes to any existing MenuItems that lack one
            items_without_code = db.session.scalars(
                select(MenuItem).where(MenuItem.code.is_(None), MenuItem.deleted_at.is_(None))
            ).all()
            for item in items_without_code:
                item.code = _generate_unique_code(db.session)
            if items_without_code:
                db.session.commit()
                logger.info(f"Assigned product codes to {len(items_without_code)} existing menu items.")
        except Exception as e:
            logger.warning(f"Startup DB checks failed (expected during migrations): {e}")

    # --- Scheduler ---
    if not app.config.get("TESTING"):
        if os.getenv("RUN_SCHEDULER", "false").lower() == "true":
            _start_scheduler(app)
    # ============================================================
    # ROUTES
    # ============================================================

    # --- Global Error Handlers (always return JSON) ---
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return jsonify({"error": "Too Many Requests", "message": str(e.description)}), 429

    @app.errorhandler(429)
    def handle_429(e):
        return jsonify({"error": "Too Many Requests", "message": "Rate limit exceeded. Please slow down."}), 429

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not Found", "message": str(e)}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        import uuid
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"error": e.name, "message": e.description}), e.code
        error_id = uuid.uuid4().hex[:12]
        logger.exception(f"[{error_id}] Unhandled exception: {e}")

        response_data = {
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred.",
            "error_id": error_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if os.getenv("FLASK_ENV") != "production":
            # Development only - structured debug payload. Production NEVER
            # receives stack traces; correlate via error_id in server logs.
            response_data["debug"] = {
                "exception": repr(e),
                "traceback": traceback.format_exc().splitlines(),
            }
        return jsonify(response_data), 500

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Hardened CSP - no 'unsafe-inline' / 'unsafe-eval'.
        # React SPAs built with Vite use external scripts and CSSOM style
        # injection, so neither directive is required.
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data: blob: https:; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self' https: wss:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        if os.getenv("FLASK_ENV") == "production":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # ---------- Health ----------
    # NOTE: The former /api/public/proxy-image endpoint was REMOVED for security.
    # It allowed SSRF attacks (internal network scanning, cloud metadata access)
    # by fetching arbitrary user-supplied URLs server-side.

    @app.route("/api/health")
    @limiter.limit("120 per minute")
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

    # ============================================================
    # 1. AUTH ROUTES
    # ============================================================

    def auth_rate_limit_key():
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                email = data.get("email")
                if email:
                    val = email.strip().lower()
                    print(f"RATE LIMIT KEY (EMAIL): {val}")
                    return val
        except Exception as e:
            pass
        from flask_limiter.util import get_remote_address
        res = get_remote_address()
        print(f"RATE LIMIT KEY (IP): {res}")
        return res

    # --- Refresh-token cookie helpers -------------------------------------
    # The refresh token lives in an HttpOnly cookie scoped to /api/auth so
    # client-side scripts (XSS) can never read it. Cookies are only sent to
    # auth endpoints, minimising exposure. SameSite=Strict assumes frontend
    # and API are served from the same site (true for this deployment).
    REFRESH_COOKIE = "refresh_token"

    def _set_refresh_cookie(resp, token):
        resp.set_cookie(
            REFRESH_COOKIE,
            token,
            httponly=True,
            secure=(os.getenv("FLASK_ENV") == "production"),
            samesite="Strict",
            path="/api/auth",
            max_age=int(timedelta(days=7).total_seconds()),
        )
        return resp

    def _clear_refresh_cookie(resp):
        resp.set_cookie(
            REFRESH_COOKIE,
            "",
            httponly=True,
            secure=(os.getenv("FLASK_ENV") == "production"),
            samesite="Strict",
            path="/api/auth",
            max_age=0,
        )
        return resp

    @app.route("/api/auth/register", methods=["POST"])
    @limiter.limit("10 per minute", key_func=auth_rate_limit_key)
    def register():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")
        role = data.get("role", "customer")
        
        TEMP_DOMAINS = ["temp-mail.org", "10minutemail.com", "guerrillamail.com", "mailinator.com"]
        domain = email.split("@")[-1] if "@" in email else ""
        if domain in TEMP_DOMAINS:
            return jsonify({"error": "Bad Request", "message": "This was caused due to temp mail use personal mail"}), 400
            
        # Self-registration strictly yields customer accounts
        role = "customer"
            
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        phone_raw = data.get("phone")
        if not phone_raw:
            return jsonify({"error": "Bad Request", "message": "Phone number is required"}), 400
        valid_phone, phone = validate_phone(phone_raw)
        if not valid_phone:
            return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
            
        address_raw = (data.get("address") or "").strip()
        if not address_raw:
            return jsonify({"error": "Bad Request", "message": "Delivery address is required"}), 400
        
        import re
        if first_name and not re.match(r"^[a-zA-Z\s\-']+$", first_name):
            return jsonify({"error": "Bad Request", "message": "First name contains invalid characters"}), 400
        if last_name and not re.match(r"^[a-zA-Z\s\-']+$", last_name):
            return jsonify({"error": "Bad Request", "message": "Last name contains invalid characters"}), 400

        if not email or not password:
            return jsonify({"error": "Bad Request", "message": "Email and password are required"}), 400
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"error": "Bad Request", "message": "Invalid email format"}), 400
        if len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain a mix of letters and numbers"}), 400
        if db.session.scalars(select(User).where(User.email == email)).first():
            # Generic response to prevent email enumeration
            return jsonify({"message": "If the email is valid, a registration confirmation will be sent."}), 201
        if role == "customer":
            user = Customer(email=email, first_name=first_name or None, last_name=last_name or None, phone=phone or None)
        elif role == "outlet_owner":
            user = OutletOwner(email=email, first_name=first_name or None, last_name=last_name or None, phone=phone or None)
        else:
            user = Customer(email=email, first_name=first_name or None, last_name=last_name or None, phone=phone or None)
            
        user.set_password(password, bcrypt)
        
        db.session.add(user)
        db.session.flush()

        if role == "customer" and data.get("address"):
            addr = Address(user_id=user.id, title="Home", address_line=data.get("address").strip(), is_default=True)
            db.session.add(addr)

        db.session.commit()

        # Send verification email if customer role
        if getattr(user, 'role', '') == "customer":
            _send_verification_email(app, user)

        return jsonify({"message": "If the email is valid, a registration confirmation will be sent."}), 201

    @app.route("/api/auth/login", methods=["POST"])
    @limiter.limit("5 per minute", key_func=auth_rate_limit_key)
    def login():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        # Check if this is a staff login via staff_code
        staff_code = (data.get("staff_code") or "").strip()
        pin = data.get("pin", "")
        
        if staff_code and pin:
            try:
                rc = get_redis()
            except Exception:
                rc = None
            
            if not rc and os.getenv("FLASK_ENV") == "production":
                return jsonify({"error": "Service Unavailable", "message": "Login temporarily unavailable"}), 503

            ip_address = request.remote_addr
            ip_lockout_key = f"staff_login_ip:{ip_address}"
            lockout_key = f"staff_login_attempts:{staff_code}"
            
            attempts = 0
            ip_attempts = 0
            if rc:
                attempts = int(rc.get(lockout_key) or 0)
                ip_attempts = int(rc.get(ip_lockout_key) or 0)
                if attempts >= 5 or ip_attempts >= 10:
                    return jsonify({"error": "Too Many Requests", "message": "Account or IP temporarily locked due to excessive failed attempts"}), 429

            user = db.session.scalars(select(User).where(User.staff_code == staff_code)).first()
            if not user or getattr(user, 'pin_hash', None) is None or not user.check_pin(pin, bcrypt):
                logger.warning(f"Failed staff login attempt for staff_code: {staff_code} from IP {ip_address}")
                if rc:
                    attempts += 1
                    ip_attempts += 1
                    rc.setex(lockout_key, 300, attempts)
                    rc.setex(ip_lockout_key, 300, ip_attempts)
                
                import time
                time.sleep(min(attempts, 4))
                return jsonify({"error": "Unauthorized", "message": "Invalid staff code or PIN"}), 401
            
            if rc:
                rc.setex(lockout_key, 1, 0) # reset lockout
                rc.setex(ip_lockout_key, 1, 0)
        else:
            email = (data.get("email") or "").strip().lower()
            password = data.get("password", "")

            if not email or not password:
                return jsonify({"error": "Bad Request", "message": "Email and password are required"}), 400

            user = db.session.scalars(select(User).where(User.email == email)).first()
            if not user or not user.check_password(password, bcrypt):
                logger.warning(f"Failed login attempt for email: {email}")
                from redis_client import get_redis
                try:
                    rc = get_redis()
                except Exception:
                    rc = None
                failed_count = 1
                if rc:
                    lock_key = f"login_attempts:{email}"
                    failed_count = int(rc.get(lock_key) or 0) + 1
                    rc.setex(lock_key, 300, failed_count)
                import time
                # Note: progressive delay + Redis lockout is used instead of CAPTCHA for now
                time.sleep(min(failed_count, 3))
                return jsonify({"error": "Unauthorized", "message": "Invalid email or password"}), 401
            
            from redis_client import get_redis
            try:
                rc = get_redis()
            except Exception:
                rc = None
            if rc:
                rc.delete(f"login_attempts:{email}")
            
            if not user.is_active:
                logger.warning(f"Login attempt on inactive account: {email}")
                return jsonify({"error": "Forbidden", "message": "Account is disabled. Please contact support."}), 403

        if getattr(user, 'deleted_at', None) is not None:
            return jsonify({"error": "Unauthorized", "message": "Account has been deleted"}), 401
        if getattr(user, 'is_banned', False):
            reason = getattr(user, 'ban_reason', 'No reason provided')
            return jsonify({"error": "Forbidden", "message": f"Account is banned: {reason}"}), 403
        if not user.is_active:
            return jsonify({"error": "Forbidden", "message": "Account is deactivated"}), 403

        additional_claims = {
            "role": user.role,
            "outlet_id": user.outlet_id,
            "user_id": user.id,
            "admin_department": getattr(user, 'admin_department', None),
            "is_superadmin": getattr(user, 'is_superadmin', False),
            "token_version": getattr(user, 'token_version', 0)
        }
        
        try:
            from redis_client import get_redis
            rc = get_redis()
            if rc:
                rc.setex(f"user_tv:{user.id}", 2 * 86400, getattr(user, 'token_version', 0))
        except Exception:
            pass
            
        # Session Timeouts: Admin 30m, Cashier/Staff 10m
        expires_delta = timedelta(minutes=30) if user.role == 'admin' else timedelta(minutes=10)
        token = create_access_token(identity=str(user.id), additional_claims=additional_claims, expires_delta=expires_delta)
        refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)

        manual_log_audit("login", "User", user.id)

        # Both tokens are delivered as short-lived HttpOnly cookies:
        #  - access_token (+ csrf_access_token) via flask-jwt-extended,
        #    scoped to the browser session and matching the token lifetime.
        #  - refresh_token manually, path-scoped to /api/auth.
        # The body still carries access_token for non-browser API clients;
        # browser frontends rely on the cookies + memory fast-path only.
        resp = jsonify({"access_token": token, "refresh_token": refresh_token, "user": user.to_dict()})
        set_access_cookies(resp, token, max_age=int(expires_delta.total_seconds()))
        _set_refresh_cookie(resp, refresh_token)
        return resp, 200

    
    @app.route("/api/auth/refresh", methods=["POST"])
    @limiter.limit("30 per minute")
    def refresh():
        # Read the refresh token from the HttpOnly cookie first; fall back to
        # a JSON body token for backward compatibility during migration.
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        if not refresh_token:
            data = sanitize_input(request.get_json(silent=True)) or {}
            refresh_token = data.get("refresh_token")
        if not refresh_token:
            return jsonify({"error": "Unauthorized", "message": "Missing refresh token"}), 401

        try:
            from flask_jwt_extended import decode_token
            claims = decode_token(refresh_token)
        except Exception:
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired refresh token"}), 401
        if claims.get("type") != "refresh":
            return jsonify({"error": "Unauthorized", "message": "Invalid token type"}), 401

        identity = claims["sub"]
        jti = claims["jti"]

        # Manual blocklist + token-version checks (bypasses jwt_required loaders).
        from redis_client import get_redis
        try:
            redis_client = get_redis()
        except Exception:
            redis_client = None
        now = int(datetime.now(timezone.utc).timestamp())
        if redis_client:
            if redis_client.get(f"revoked:{jti}") is not None:
                return jsonify({"error": "Unauthorized", "message": "Token has been revoked"}), 401
        elif os.getenv("FLASK_ENV") == "production":
            return jsonify({"error": "Service Unavailable", "message": "Redis required for secure refresh"}), 503

        user = db.session.get(User, int(identity))
        if not user or getattr(user, 'is_banned', False) or getattr(user, 'deleted_at', None) is not None:
            return jsonify({"error": "Unauthorized", "message": "User not found or banned"}), 401

        current_tv = getattr(user, "token_version", 0) or 0
        if int(claims.get("token_version", 0)) != current_tv:
            return jsonify({"error": "Unauthorized", "message": "Token has been revoked"}), 401

        additional_claims = {
            "role": user.role,
            "outlet_id": user.outlet_id,
            "user_id": user.id,
            "admin_department": getattr(user, 'admin_department', None),
            "is_superadmin": getattr(user, 'is_superadmin', False),
            "token_version": current_tv
        }

        # Rotation: revoke the presented refresh token before issuing a new one.
        if redis_client:
            rt_ttl = max(1, int(claims.get("exp", now)) - now)
            redis_client.setex(f"revoked:{jti}", rt_ttl, "revoked")

        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        new_refresh_token = create_refresh_token(identity=identity, additional_claims=additional_claims)

        # Rotate BOTH cookies: new short-lived access cookie + new refresh cookie.
        resp = jsonify({"access_token": access_token})
        set_access_cookies(resp, access_token,
                           max_age=int(app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()))
        _set_refresh_cookie(resp, new_refresh_token)
        return resp, 200


    @app.route("/api/auth/logout", methods=["POST"])
    @jwt_required()
    def logout():
        jti = get_jwt()["jti"]
        from datetime import datetime, timezone
        from redis_client import get_redis
        
        try:
            redis_client = get_redis()
        except Exception:
            redis_client = None
        if not redis_client:
            return jsonify({"error": "Service Unavailable", "message": "Logout temporarily unavailable"}), 503
            
        try:
            exp = get_jwt().get("exp")
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = max(1, exp - now) if exp else 3600
            redis_client.setex(f"revoked:{jti}", ttl, "1")
            
            # Revoke the refresh token from the HttpOnly cookie (or legacy body).
            data = sanitize_input(request.get_json(silent=True)) or {}
            refresh_token = request.cookies.get(REFRESH_COOKIE) or data.get("refresh_token")
            if refresh_token:
                from flask_jwt_extended import decode_token
                try:
                    rt_claims = decode_token(refresh_token)
                    rt_jti = rt_claims["jti"]
                    rt_exp = rt_claims["exp"]
                    rt_ttl = max(1, rt_exp - now)
                    redis_client.setex(f"revoked:{rt_jti}", rt_ttl, "1")
                except Exception:
                    pass
        except Exception:
            return jsonify({"error": "Service Unavailable", "message": "Logout temporarily unavailable"}), 503

        try:
            uid = int(get_jwt_identity())
        except (TypeError, ValueError):
            uid = None
        manual_log_audit("logout", "User", uid)

        resp = jsonify({"message": "Logged out"})
        # Clear the access + csrf cookies AND the refresh cookie.
        unset_jwt_cookies(resp)
        _clear_refresh_cookie(resp)
        return resp, 200


    @app.route("/api/auth/me", methods=["GET"])
    @jwt_required()
    def get_me():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found"}), 404
        return jsonify(user.to_dict()), 200

    @app.route("/api/auth/forgot-password", methods=["POST"])
    @limiter.limit("3 per minute", key_func=auth_rate_limit_key)
    def forgot_password():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "Bad Request", "message": "Email is required"}), 400

        user = db.session.scalars(select(User).where(User.email == email)).first()
        if user:
            import secrets
            if app.config.get("TESTING"):
                token = '123456'
            else:
                token = f"{secrets.randbelow(1000000):06d}"
            user.password_reset_token = bcrypt.generate_password_hash(token).decode('utf-8')
            user.password_reset_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            db.session.commit()

            sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
            msg = Message(
                subject="Suggula\'s Kitchen Password Reset Token",
                sender=sender,
                recipients=[email]
            )
            msg.body = f"""Hi {user.first_name or 'User'},

You have requested to reset your password for your Suggula\'s Kitchen account.
Please use the following 6-digit code in the password reset form:

Reset Code: {token}

This code is valid for 1 hour. If you did not request this, please ignore this email.

Best regards,
Suggula\'s Kitchen Team
"""
            try:
                mail.send(msg)
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send email: {e}")

        return jsonify({"message": "If the email is registered, you will receive a reset token shortly."}), 200

    @app.route("/api/auth/reset-password", methods=["POST"])
    @limiter.limit("5 per minute", key_func=auth_rate_limit_key)
    def reset_password():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        email = (data.get("email") or "").strip().lower()
        token = (data.get("token") or "").strip()
        new_password = data.get("new_password", "")

        if not email or not token or not new_password:
            return jsonify({"error": "Bad Request", "message": "Email, token, and new password are required"}), 400
        import re
        if len(new_password) < 8 or not re.search(r'[A-Za-z]', new_password) or not re.search(r'[0-9]', new_password):
            return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain a mix of letters and numbers"}), 400

        user = db.session.scalars(select(User).where(User.email == email)).first()
        if not user or not user.password_reset_token or not bcrypt.check_password_hash(user.password_reset_token, token):
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired token"}), 401

        if not user.password_reset_expiry:
            return jsonify({"error": "Unauthorized", "message": "Invalid token state"}), 401

        expiry = user.password_reset_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        
        if datetime.now(timezone.utc) > expiry:
            return jsonify({"error": "Unauthorized", "message": "Token has expired"}), 401

        user.set_password(new_password, bcrypt)
        user.password_reset_token = None
        user.password_reset_expiry = None
        user.is_first_login = False
        user.bump_token_version()
        db.session.commit()

        return jsonify({"message": "Password has been reset successfully"}), 200

    @app.route("/api/auth/request-password-change-otp", methods=["POST"])
    @jwt_required()
    @limiter.limit("3 per minute")
    def request_password_change_otp():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404

        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        if not user.is_first_login:
            old_password = data.get("old_password", "")
            if not old_password or not user.check_password(old_password, bcrypt):
                return jsonify({"error": "Unauthorized", "message": "Incorrect old password"}), 401
                
        import secrets
        if app.config.get("TESTING"):
            token = '123456'
        else:
            token = f"{secrets.randbelow(1000000):06d}"
        user.password_reset_token = bcrypt.generate_password_hash(token).decode('utf-8')
        user.password_reset_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()

        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(
            subject="Suggula\'s Kitchen Password Change Code",
            sender=sender,
            recipients=[user.email]
        )
        msg.body = f"""Hi {user.first_name or 'User'},

You have requested to change your password for your Suggula\'s Kitchen account.
Please use the following 6-digit code in the password change form:

Change Code: {token}

This code is valid for 1 hour. If you did not request this, please ignore this email.

Best regards,
The Suggula\'s Kitchen Team"""
        try:
            mail.send(msg)
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            
        return jsonify({"message": "OTP sent to your email"}), 200

    @app.route("/api/auth/change-password", methods=["POST"])
    @jwt_required()
    def change_password():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404

        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        # Check old password if not first login
        if not user.is_first_login:
            old_password = data.get("old_password", "")
            if not old_password or not user.check_password(old_password, bcrypt):
                return jsonify({"error": "Unauthorized", "message": "Incorrect old password"}), 401


        new_password = data.get("new_password", "")
        import re
        if not new_password or len(new_password) < 8 or not re.search(r'[A-Za-z]', new_password) or not re.search(r'[0-9]', new_password):
            return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain a mix of letters and numbers"}), 400

        user.set_password(new_password, bcrypt)
        user.is_first_login = False
        user.password_reset_token = None
        user.password_reset_expiry = None
        user.bump_token_version()
        db.session.commit()

        return jsonify({"message": "Password changed successfully"}), 200

    @app.route("/api/auth/profile", methods=["PUT"])
    @jwt_required()
    def update_profile():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404
            
        data = (sanitize_input(request.get_json(silent=True)) or {})
        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        if "phone" in data:
            valid_phone, phone_clean = validate_phone(data["phone"])
            if not valid_phone:
                return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
            user.phone = phone_clean
        
        if "address" in data:
            user.address = data["address"]
            
        # Handle password change
        new_password = data.get("password")
        if new_password:
            old_password = data.get("old_password", "")
            if not old_password or not user.check_password(old_password, bcrypt):
                return jsonify({"error": "Unauthorized", "message": "Incorrect old password"}), 401
                
            import re
            if len(new_password) < 8 or not re.search(r'[A-Za-z]', new_password) or not re.search(r'[0-9]', new_password):
                return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain both letters and numbers."}), 400
            
            user.set_password(new_password, bcrypt)
            user.bump_token_version()

        # Handle PIN change (for staff/kitchen)
        new_pin = data.get("pin")
        if new_pin is not None:
            new_pin = str(new_pin).strip()
            if new_pin:
                if not new_pin.isdigit() or len(new_pin) != 4:
                    return jsonify({"error": "Bad Request", "message": "PIN must be exactly 4 digits"}), 400
                user.set_pin(new_pin, bcrypt)
                user.bump_token_version()
            else:
                user.pin_hash = None
                user.bump_token_version()
        db.session.commit()
        return jsonify({"message": "Profile updated successfully", "user": user.to_dict()}), 200

    @app.route("/api/auth/profile", methods=["DELETE"])
    @jwt_required()
    def delete_profile():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404
        
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        user.bump_token_version()
        db.session.commit()
        return jsonify({"message": "Account deleted successfully"}), 200

    @app.route("/api/admin/profile", methods=["PATCH"])
    @jwt_required()
    @role_required("admin")
    def patch_admin_profile():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404

        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        email = data.get("email")
        if email:
            email = email.strip().lower()
            if email != user.email:
                existing = db.session.scalars(select(User).where(User.email == email)).first()
                if existing:
                    return jsonify({"error": "Conflict", "message": "Email already in use"}), 409
                user.email = email
                
        if "phone" in data:
            if data["phone"]:
                valid_phone, phone_clean = validate_phone(data["phone"])
                if not valid_phone:
                    return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
                user.phone = phone_clean
            else:
                user.phone = None
                
        db.session.commit()
        return jsonify({"message": "Admin profile updated successfully", "user": user.to_dict()}), 200

    @app.route("/api/auth/verify-email", methods=["POST"])
    @limiter.limit("5 per minute")
    def verify_email():
        data = sanitize_input(request.get_json(silent=True)) or {}
        token = data.get("token")
        if not token:
            return jsonify({"error": "Bad Request", "message": "Token is missing"}), 400
            
        serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        try:
            # Token expires in 24 hours (86400 seconds)
            email = serializer.loads(token, salt="email-verify-salt", max_age=86400)
        except SignatureExpired:
            return jsonify({"error": "Unauthorized", "message": "Verification token has expired"}), 401
        except BadSignature:
            return jsonify({"error": "Unauthorized", "message": "Invalid verification token"}), 401
            
        user = db.session.scalars(select(User).where(User.email == email)).first()
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404
            
        if user.is_email_verified:
            return jsonify({"message": "Email is already verified", "already_verified": True}), 200
            
        user.is_email_verified = True
        db.session.commit()
        return jsonify({"message": "Email verified successfully"}), 200

    # --- Address Book ---
    @app.route("/api/auth/addresses", methods=["GET"])
    @jwt_required()
    def get_addresses():
        uid = int(get_jwt_identity())
        addresses = db.session.scalars(select(Address).where(Address.user_id == uid)).all()
        return jsonify([addr.to_dict() for addr in addresses]), 200

    @app.route("/api/auth/addresses", methods=["POST"])
    @jwt_required()
    def add_address():
        uid = int(get_jwt_identity())
        data = sanitize_input(request.get_json(silent=True)) or {}
        
        title = data.get("title", "").strip()
        address_line = data.get("address_line", "").strip()
        is_default = data.get("is_default", False)
        
        if not title or not address_line:
            return jsonify({"error": "Bad Request", "message": "Title and address line are required"}), 400
            
        if is_default:
            # Remove default from old addresses
            db.session.execute(
                db.update(Address).where(Address.user_id == uid).values(is_default=False)
            )
            
        new_addr = Address(user_id=uid, title=title, address_line=address_line, is_default=is_default)
        db.session.add(new_addr)
        db.session.commit()
        return jsonify({"message": "Address added", "address": new_addr.to_dict()}), 201

    @app.route("/api/auth/addresses/<int:address_id>", methods=["DELETE"])
    @jwt_required()
    def delete_address(address_id):
        uid = int(get_jwt_identity())
        addr = db.session.get(Address, address_id)
        if not addr or addr.user_id != uid:
            return jsonify({"error": "Not Found"}), 404
            
        db.session.delete(addr)
        db.session.commit()
        return jsonify({"message": "Address deleted"}), 200

    @app.route("/api/customer/account", methods=["DELETE"])
    @role_required("customer")
    def delete_customer_account():
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404
        
        try:
            # Deterministic, portable cleanup performed in ONE transaction.
            # Child rows are deleted explicitly (order-independent of whether
            # the underlying schema already has ON DELETE CASCADE applied via
            # Alembic). No raw-SQL fallback anymore.
            from sqlalchemy import delete as sa_delete, update as sa_update

            # Break self-referential referral links (FK has no ondelete action).
            db.session.execute(
                sa_update(User).where(User.referred_by_id == user_id).values(referred_by_id=None)
            )

            db.session.execute(sa_delete(Review).where(Review.customer_id == user_id))
            db.session.execute(sa_delete(Address).where(Address.user_id == user_id))
            db.session.execute(sa_delete(SupportTicket).where(SupportTicket.customer_id == user_id))
            db.session.execute(sa_delete(WalletTransaction).where(WalletTransaction.user_id == user_id))
            db.session.execute(sa_delete(Favorite).where(Favorite.customer_id == user_id))

            # Delete order items before their parent orders (ORM cascade on
            # Order.items also covers this when rows are loaded).
            order_ids = db.session.scalars(
                select(Order.id).where(Order.customer_id == user_id)
            ).all()
            if order_ids:
                db.session.execute(sa_delete(OrderItem).where(OrderItem.order_id.in_(order_ids)))
                db.session.execute(sa_delete(Order).where(Order.id.in_(order_ids)))

            # Nullable audit/tracking FKs are ON DELETE SET NULL in the schema
            # (stock_audit_logs.performed_by, product_batches.received_by,
            # kitchen_production_batches.produced_by, outlets.owner_id) and are handled
            # by the database itself.

            db.session.delete(user)
            db.session.commit()
            return jsonify({"message": "Account deleted successfully"}), 200
        except sqlalchemy.exc.SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error deleting account {user_id}: {str(e)}")
            return jsonify({"error": "Delete Failed", "message": "Could not delete account"}), 500



    # ============================================================
    # 2. CUSTOMER ROUTES (role: customer)
    # ============================================================
    
    # --- Favorites ---
    @app.route("/api/foods/favorites", methods=["GET"])
    @jwt_required()
    def get_favorites():
        uid = int(get_jwt_identity())
        favs = db.session.scalars(select(Favorite).where(Favorite.customer_id == uid)).all()
        return jsonify([f.to_dict() for f in favs]), 200

    @app.route("/api/foods/favorites", methods=["POST"])
    @jwt_required()
    def add_favorite():
        uid = int(get_jwt_identity())
        data = sanitize_input(request.get_json(silent=True)) or {}
        menu_item_id = data.get("menu_item_id")
        
        if not menu_item_id:
            return jsonify({"error": "Bad Request", "message": "menu_item_id is required"}), 400
            
        existing = db.session.scalar(
            select(Favorite).where(Favorite.customer_id == uid, Favorite.menu_item_id == menu_item_id)
        )
        if existing:
            return jsonify({"message": "Already in favorites", "favorite": existing.to_dict()}), 200
            
        fav = Favorite(customer_id=uid, menu_item_id=menu_item_id)
        db.session.add(fav)
        db.session.commit()
        return jsonify({"message": "Added to favorites", "favorite": fav.to_dict()}), 201

    @app.route("/api/foods/favorites/<int:menu_item_id>", methods=["DELETE"])
    @jwt_required()
    def remove_favorite(menu_item_id):
        uid = int(get_jwt_identity())
        fav = db.session.scalar(
            select(Favorite).where(Favorite.customer_id == uid, Favorite.menu_item_id == menu_item_id)
        )
        if not fav:
            return jsonify({"error": "Not Found", "message": "Not in favorites"}), 404
            
        db.session.delete(fav)
        db.session.commit()
        return jsonify({"message": "Removed from favorites"}), 200


    @app.route("/api/foods/menu", methods=["GET"])
    @limiter.limit("60 per minute")
    def get_foods_menu():
        """Public: home foods menu."""
        from sqlalchemy.orm import selectinload
        items = db.session.scalars(
            select(MenuItem).where(
                MenuItem.is_active == True,
                MenuItem.business_type.in_(["home_foods", "both"])
            ).options(selectinload(MenuItem.reviews)).order_by(MenuItem.category, MenuItem.name)
        ).all()
        return jsonify([i.to_dict() for i in items]), 200

    @app.route("/api/foods/menu/code/<code>", methods=["GET"])
    @limiter.limit("60 per minute")
    def get_food_by_code(code):
        """Public: get a menu item by its code"""
        item = db.session.scalars(
            select(MenuItem).where(MenuItem.code == code, MenuItem.deleted_at.is_(None))
        ).first()
        if not item:
            return jsonify({"error": "Not Found", "message": "Item not found with this code"}), 404
        return jsonify(item.to_dict()), 200

    @app.route("/api/foods/order", methods=["POST"])
    @limiter.limit("5 per minute")
    @jwt_required(optional=True)
    def place_order():
        # TRANSACTION BOUNDARY: everything below runs in ONE transaction that
        # commits only at the end (see db.session.commit() near the return).
        # Concurrency controls:
        #   - Customer row locked with SELECT ... FOR UPDATE up front.
        #   - Stock decrements use guarded atomic UPDATE ... WHERE stock >= qty
        #     (409 on rowcount != 1) — no oversell possible.
        #   - Coupon row locked FOR UPDATE; usage increment is guarded by
        #     usage_count < usage_limit (400 on rowcount != 1).
        #   - Loyalty redemption is a guarded atomic decrement (409 on race).
        # Any failure path rolls back, so no partial order state can persist.
        customer_id = get_jwt_identity()
        customer = None
        if customer_id is not None:
            customer_id = int(customer_id)
            claims = get_jwt()
            if claims.get("role") not in ["customer", "outlet_owner"]:
                return jsonify({"error": "Forbidden", "message": "Insufficient permissions"}), 403
            
            customer = db.session.scalars(
                select(User).where(User.id == customer_id).with_for_update()
            ).first()
            if customer and not getattr(customer, 'is_email_verified', False):
                return jsonify({"error": "Forbidden", "message": "Please verify your email before placing an order."}), 403

        data = (sanitize_input(request.get_json(silent=True)) or {})
        items_data = data.get("items", [])
        delivery_address = data.get("delivery_address")
        payment_method = data.get("payment_method", "COD")
        coupon_code = data.get("coupon_code")
        delivery_charge = Decimal(str(data.get("delivery_charge") or 0.00))
        
        guest_name = data.get("guest_name")
        guest_email = data.get("guest_email")
        guest_phone = data.get("guest_phone")

        if not customer_id and not (guest_name and guest_email and guest_phone):
            return jsonify({"error": "Bad Request", "message": "Guest details (name, email, phone) are required for guest checkout."}), 400

        if not items_data:
            return jsonify({"error": "Bad Request", "message": "No items in order"}), 400

        total = Decimal("0.00")
        order_items = []
        for it in items_data:
            mid = it.get("menu_item_id")
            qty = int(it.get("quantity", 1))
            if qty < 1:
                continue
            menu_item = db.session.get(MenuItem, mid)
            if not menu_item or not menu_item.is_active:
                return jsonify({"error": "Bad Request", "message": f"Item ID {mid} not found"}), 404
            if menu_item.business_type not in ("home_foods", "both"):
                return jsonify({"error": "Bad Request", "message": f"Item '{menu_item.name}' is not available for B2C order"}), 400
            
            if menu_item.global_stock is not None:
                result = db.session.execute(
                    update(MenuItem).where(MenuItem.id == mid, MenuItem.global_stock >= qty)
                    .values(global_stock=MenuItem.global_stock - qty)
                )
                if result.rowcount != 1:
                    db.session.rollback()
                    return jsonify({"error": "Conflict", "message": f"Item '{menu_item.name}' is out of stock"}), 409
                db.session.refresh(menu_item)
                
                if menu_item.global_stock == 0:
                    logger.info(f"[NOTIFICATION] KITCHEN/ADMIN: Item '{menu_item.name}' is now SOLD OUT!")

            price = menu_item.price
            total += price * qty
            order_items.append(OrderItem(menu_item_id=mid, price=price, quantity=qty))
        
        total += delivery_charge

        discount_pct = 0
        coupon = None
        if coupon_code:
            coupon = db.session.scalars(
                select(Coupon).where(Coupon.code == coupon_code.upper().strip(), Coupon.is_active == True).with_for_update()
            ).first()
            if coupon:
                if coupon.expiry_date and coupon.expiry_date < datetime.now(timezone.utc).date():
                    return jsonify({"error": "Bad Request", "message": "Coupon has expired"}), 400
                if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
                    return jsonify({"error": "Bad Request", "message": "Coupon usage limit reached"}), 400

                # Check scope
                if coupon.scope == 'outlet':
                    return jsonify({"error": "Bad Request", "message": "This coupon is only valid for in-store purchases"}), 400

                # Check min order value
                if coupon.min_order_value and total < Decimal(str(coupon.min_order_value)):
                    return jsonify({"error": "Bad Request", "message": f"Minimum order value of ₹{coupon.min_order_value} required"}), 400

                # Check if first order only
                if coupon.is_first_order_only:
                    has_orders = db.session.scalars(select(Order).where(Order.customer_id == customer_id)).first()
                    if has_orders:
                        return jsonify({"error": "Bad Request", "message": "This coupon is only valid for your first order"}), 400

                # Check if this user already used this coupon
                used = db.session.scalars(select(Order).where(Order.customer_id == customer_id, Order.applied_coupon_code == coupon.code)).first()
                if used:
                    return jsonify({"error": "Bad Request", "message": "You have already used this coupon. Sorry, try other options."}), 400

                stmt = update(Coupon).where(
                    Coupon.id == coupon.id,
                    or_(Coupon.usage_limit == None, Coupon.usage_count < Coupon.usage_limit)
                ).values(usage_count=Coupon.usage_count + 1)
                res = db.session.execute(stmt)
                if res.rowcount == 0:
                    return jsonify({"error": "Bad Request", "message": "Coupon usage limit reached during checkout"}), 400
                
                # Apply discount
                if coupon.discount_amount and coupon.discount_amount > 0:
                    total = max(Decimal("0.00"), total - Decimal(str(coupon.discount_amount)))
                elif coupon.discount_pct and coupon.discount_pct > 0:
                    discount_pct = min(100, coupon.discount_pct)
                    discount_value = total * (Decimal(str(discount_pct)) / Decimal("100"))
                    if coupon.max_discount_amount and discount_value > Decimal(str(coupon.max_discount_amount)):
                        discount_value = Decimal(str(coupon.max_discount_amount))
                    total = max(Decimal("0.00"), total - discount_value)

        earn_rate, redeem_rate = get_loyalty_settings()
        
        redeem_points = int(data.get("redeem_loyalty_points") or 0)
        points_redeemed = 0
        if redeem_points > 0:
            if not customer:
                return jsonify({"error": "Bad Request", "message": "Loyalty points can only be used by registered customers"}), 400
            
            # calculate max redeemable points so it doesn't exceed total cost
            max_redeem_allowed = int(total / Decimal(str(redeem_rate))) if redeem_rate > 0 else 0
            actual_redeem = min(redeem_points, customer.loyalty_points, max_redeem_allowed)

            if actual_redeem > 0:
                points_discount = Decimal(str(actual_redeem * redeem_rate))
                # Atomic, guarded decrement: fails if a concurrent checkout
                # already drained the balance below actual_redeem.
                from sqlalchemy import update as _sa_update
                redeem_res = db.session.execute(
                    _sa_update(Customer).where(Customer.id == customer.id, Customer.loyalty_points >= actual_redeem)
                    .values(loyalty_points=Customer.loyalty_points - actual_redeem)
                )
                if redeem_res.rowcount != 1:
                    db.session.rollback()
                    return jsonify({"error": "Conflict", "message": "Loyalty points changed during checkout. Please retry."}), 409
                db.session.refresh(customer)
                points_redeemed = actual_redeem
                total = max(Decimal("0.00"), total - points_discount)
        
        points_earned = 0
        if customer:
            points_earned = int(total * Decimal(str(earn_rate)))
            # Note: We NO LONGER instantly credit loyalty points on checkout. 
            # They will be credited when status becomes 'delivered' or 'completed'

        order = Order(
            customer_id=customer_id, 
            total_price=total, 
            items=order_items, 
            delivery_address=delivery_address, 
            payment_method=payment_method,
            applied_coupon_code=coupon.code if coupon else None,
            loyalty_points_earned=points_earned,
            loyalty_points_redeemed=points_redeemed,
            delivery_charge=delivery_charge,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone
        )
        db.session.add(order)
        db.session.flush() # ensure we have order.id
        
        _generate_order_qr(app, order)
        db.session.commit()

        # Send order confirmation email to customer
        if customer_id is not None:
            customer = db.session.get(User, customer_id)
            if customer and customer.email:
                _send_order_placed_email(app, order, customer)
        elif guest_email:
            class MockCustomer:
                def __init__(self, name, email):
                    self.name = name
                    self.first_name = name.split()[0] if name else ""
                    self.email = email
            _send_order_placed_email(app, order, MockCustomer(guest_name, guest_email))

        return jsonify({"message": "Order placed", "order": order.to_dict()}), 201

    @app.route("/api/foods/orders", methods=["GET"])
    @role_required("customer", "outlet_owner")
    def get_order_history():
        customer_id = int(get_jwt_identity())
        orders = db.session.scalars(
            select(Order).where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
        ).unique().all()
        return jsonify([o.to_dict() for o in orders]), 200

    @app.route("/api/foods/orders/<int:order_id>/cancel", methods=["POST"])
    @role_required("customer", "outlet_owner")
    def cancel_order(order_id):
        customer_id = int(get_jwt_identity())
        data = (sanitize_input(request.get_json(silent=True)) or {})
        reason = data.get("reason", "Cancelled by customer")

        order = db.session.get(Order, order_id)
        if not order:
            return jsonify({"error": "Not Found", "message": "Order not found"}), 404
        if order.customer_id != customer_id:
            return jsonify({"error": "Forbidden"}), 403
        if order.status not in ("pending", "processing"):
            return jsonify({"error": "Bad Request", "message": f"Cannot cancel order with status '{order.status}'"}), 400

        order.status = "cancelled"
        order.cancel_reason = reason
        
        # Restore stock and coupon
        for item in order.items:
            menu_item = db.session.scalars(select(MenuItem).where(MenuItem.id == item.menu_item_id).with_for_update()).first()
            if menu_item and menu_item.global_stock is not None:
                menu_item.global_stock += item.quantity
        
        if order.applied_coupon_code:
            coupon = db.session.scalars(select(Coupon).where(Coupon.code == order.applied_coupon_code).with_for_update()).first()
            if coupon and coupon.usage_count > 0:
                coupon.usage_count -= 1

        if order.customer_id:
            customer = db.session.scalars(select(User).where(User.id == order.customer_id).with_for_update()).first()
            if customer:
                # Note: We DO NOT deduct loyalty_points_earned here because pending/processing orders 
                # have not yet credited those points to the customer. We ONLY refund the redeemed points.
                if order.loyalty_points_redeemed and order.loyalty_points_redeemed > 0:
                    customer.loyalty_points = (customer.loyalty_points or 0) + order.loyalty_points_redeemed
                    db.session.add(WalletTransaction(
                        user_id=customer.id, amount=order.loyalty_points_redeemed, transaction_type="credit",
                        description=f"Points refunded due to cancellation of Order #{order.id}"
                    ))

        db.session.commit()
        return jsonify({"message": "Order cancelled", "order": order.to_dict()}), 200

    @app.route("/api/foods/orders/<int:order_id>/confirm", methods=["POST"])
    @role_required("customer", "outlet_owner")
    def confirm_receipt(order_id):
        customer_id = int(get_jwt_identity())
        data = (sanitize_input(request.get_json(silent=True)) or {})
        code = (data.get("delivery_confirmation_code") or data.get("tracking_code") or "").strip()

        order = db.session.get(Order, order_id)
        if not order or order.customer_id != customer_id:
            return jsonify({"error": "Not Found"}), 404
        if order.status != "shipped":
            return jsonify({"error": "Bad Request", "message": "Order is not in shipped status"}), 400
        
        if order.delivery_confirmation_code and order.delivery_confirmation_code != code:
            return jsonify({"error": "Unauthorized", "message": "Incorrect Delivery PIN. Please check your email and try again."}), 401
        elif not order.delivery_confirmation_code and order.tracking_id != code:
            return jsonify({"error": "Unauthorized", "message": "Tracking code does not match"}), 401
        
        if order.status != "delivered":
            order.status = "delivered"
            order.is_received = True
            
            # Award points upon delivery
            if order.customer_id and order.loyalty_points_earned > 0:
                customer = db.session.scalars(select(User).where(User.id == order.customer_id).with_for_update()).first()
                if customer:
                    customer.loyalty_points = (customer.loyalty_points or 0) + order.loyalty_points_earned
                    db.session.add(WalletTransaction(
                        user_id=customer.id, amount=order.loyalty_points_earned, transaction_type="credit",
                        description=f"Points awarded for completion of Order #{order.id}"
                    ))

        db.session.commit()
        return jsonify({"message": "Order confirmed as delivered", "order": order.to_dict()}), 200

    @app.route("/api/foods/orders/<int:order_id>/feedback", methods=["POST"])
    @role_required("customer", "outlet_owner")
    def submit_feedback(order_id):
        customer_id = int(get_jwt_identity())
        data = (sanitize_input(request.get_json(silent=True)) or {})

        order = db.session.get(Order, order_id)
        if not order or order.customer_id != customer_id:
            return jsonify({"error": "Not Found"}), 404
        if not order.is_received:
            return jsonify({"error": "Forbidden", "message": "Feedback form is locked until receipt confirmation"}), 403
        if order.review:
            return jsonify({"error": "Conflict", "message": "Feedback already submitted"}), 409

        rating = int(data.get("rating", 5))
        if not 1 <= rating <= 5:
            return jsonify({"error": "Bad Request", "message": "Rating must be 1–5"}), 400

        fb = Review(order_id=order_id, customer_id=customer_id,
                      menu_item_id=data.get("menu_item_id"),
                      rating=rating, comment=data.get("comment"))
        db.session.add(fb)
        db.session.commit()
        return jsonify({"message": "Feedback submitted", "feedback": fb.to_dict()}), 201

    @app.route("/api/customer/tickets", methods=["GET"])
    @role_required("customer", "outlet_owner")
    def get_my_tickets():
        customer_id = int(get_jwt_identity())
        tickets = db.session.scalars(select(SupportTicket).where(SupportTicket.customer_id == customer_id).order_by(SupportTicket.created_at.desc())).all()
        return jsonify([t.to_dict() for t in tickets]), 200

    @app.route("/api/customer/tickets", methods=["POST"])
    @limiter.limit("5 per minute")
    @role_required("customer", "outlet_owner")
    def create_ticket():
        customer_id = int(get_jwt_identity())
        
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            data = sanitize_input(dict(request.form))
        else:
            data = sanitize_input(request.get_json(silent=True)) or {}

        issue_type = data.get("issue_type")
        description = data.get("description")
        order_id = data.get("order_id")
        if order_id and order_id != "null":
            try:
                order_id = int(order_id)
            except ValueError:
                order_id = None
        else:
            order_id = None

        if not issue_type or not description:
            return jsonify({"error": "Bad Request", "message": "Issue type and description are required"}), 400

        unique_name = None
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename:
                if not allowed_file(file):
                    return jsonify({"error": "Bad Request", "message": "Invalid or disallowed file type"}), 400
                unique_name, err_resp, err_code = _save_scanned_attachment(file, customer_id)
                if err_resp is not None:
                    return err_resp, err_code

        ticket = SupportTicket(customer_id=customer_id, issue_type=issue_type, description=description, order_id=order_id, attachment_filename=unique_name)
        db.session.add(ticket)
        db.session.flush()
        if unique_name:
            ticket.attachment_url = f"/api/tickets/{ticket.id}/attachment"
        db.session.commit()
        
        return jsonify({"message": "Support ticket created successfully", "ticket": ticket.to_dict()}), 201

    @app.route("/api/customer/tickets/<int:ticket_id>", methods=["PUT"])
    @limiter.limit("10 per hour")
    @role_required("customer", "outlet_owner")
    def update_ticket(ticket_id):
        customer_id = int(get_jwt_identity())
        ticket = db.session.get(SupportTicket, ticket_id)
        if not ticket or ticket.customer_id != customer_id:
            return jsonify({"error": "Not Found"}), 404
            
        status_val = ticket.status.value if hasattr(ticket.status, "value") else ticket.status
        if str(status_val).lower() != "open":
            return jsonify({"error": "Bad Request", "message": "Only open tickets can be edited"}), 400

        if request.content_type and request.content_type.startswith("multipart/form-data"):
            data = sanitize_input(dict(request.form))
        else:
            data = sanitize_input(request.get_json(silent=True)) or {}

        if "issue_type" in data:
            ticket.issue_type = data["issue_type"]
        if "description" in data:
            ticket.description = data["description"]

        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename:
                if not allowed_file(file):
                    return jsonify({"error": "Bad Request", "message": "Invalid or disallowed file type"}), 400
                unique_name, err_resp, err_code = _save_scanned_attachment(
                    file, customer_id, replaced_filename=ticket.attachment_filename
                )
                if err_resp is not None:
                    return err_resp, err_code
                # New file saved & scanned - remove the replaced one.
                if ticket.attachment_filename:
                    old_path = os.path.join(TICKETS_UPLOAD_FOLDER, ticket.attachment_filename)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            logger.error(f"Failed to remove replaced attachment {old_path}: {e}")
                ticket.attachment_filename = unique_name
                ticket.attachment_url = f"/api/tickets/{ticket.id}/attachment"

        db.session.commit()
        return jsonify({"message": "Support ticket updated successfully", "ticket": ticket.to_dict()}), 200

    @app.route("/api/customer/tickets/<int:ticket_id>", methods=["DELETE"])
    @role_required("customer", "outlet_owner")
    def delete_ticket(ticket_id):
        customer_id = int(get_jwt_identity())
        ticket = db.session.get(SupportTicket, ticket_id)
        if not ticket or ticket.customer_id != customer_id:
            return jsonify({"error": "Not Found"}), 404
            
        if ticket.status != "Open":
            return jsonify({"error": "Bad Request", "message": "Only open tickets can be deleted"}), 400

        if ticket.attachment_filename:
            filepath = os.path.join(TICKETS_UPLOAD_FOLDER, ticket.attachment_filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.error(f"Failed to delete ticket attachment {filepath}: {e}")

        db.session.delete(ticket)
        db.session.commit()
        return jsonify({"message": "Support ticket deleted successfully"}), 200

    @app.route("/api/tickets/<int:ticket_id>/attachment", methods=["GET"])
    @jwt_required()
    def get_ticket_attachment(ticket_id):
        ticket = db.session.get(SupportTicket, ticket_id)
        if not ticket or not ticket.attachment_filename:
            return jsonify({"error": "Not Found", "message": "Attachment not found"}), 404
            
        claims = get_jwt()
        user_id = int(get_jwt_identity())
        
        # Must be owner or staff/admin
        if ticket.customer_id != user_id and claims.get("role") not in ["admin", "staff"]:
            return jsonify({"error": "Forbidden", "message": "You do not have access to this attachment"}), 403
            
        return send_from_directory(TICKETS_UPLOAD_FOLDER, ticket.attachment_filename, as_attachment=True)

    @app.route("/api/customer/loyalty", methods=["GET"])
    @role_required("customer", "outlet_owner")
    def get_loyalty_history():
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "Not Found"}), 404
            
        # Get wallet transactions
        txs = db.session.scalars(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.created_at.desc())
        ).all()
        
        # Get order points earned/redeemed
        orders = db.session.scalars(
            select(Order)
            .where(Order.customer_id == user_id)
            .where((Order.loyalty_points_earned > 0) | (Order.loyalty_points_redeemed > 0))
            .order_by(Order.created_at.desc())
        ).all()
        
        history = []
        for tx in txs:
            history.append({
                "id": f"tx_{tx.id}",
                "date": tx.created_at.isoformat(),
                "desc": tx.description,
                "amount": tx.amount if tx.transaction_type == 'credit' else -tx.amount,
                "type": tx.transaction_type
            })
            
        for o in orders:
            # Earned points are only credited if the order was actually delivered or completed
            if o.loyalty_points_earned and o.loyalty_points_earned > 0 and o.status in ["delivered", "completed"]:
                history.append({
                    "id": f"oe_{o.id}",
                    "date": o.created_at.isoformat(),
                    "type": "credit",
                    "amount": o.loyalty_points_earned,
                    "desc": f"Order #{o.id} reward"
                })
            if o.loyalty_points_redeemed and o.loyalty_points_redeemed > 0:
                history.append({
                    "id": f"or_{o.id}",
                    "date": o.created_at.isoformat(),
                    "desc": f"Redeemed points on order #{o.id}",
                    "amount": -o.loyalty_points_redeemed,
                    "type": "debit"
                })
                
        # Sort combined history
        history.sort(key=lambda x: x["date"], reverse=True)

        return jsonify({
            "loyalty_points": user.loyalty_points or 0,
            "history": history
        }), 200

    # ============================================================
    # 3. ADMIN ROUTES
    # ============================================================

    @app.route("/api/admin/tickets", methods=["GET"])
    @role_required("admin", "superadmin")
    def admin_get_tickets():
        tickets = db.session.scalars(select(SupportTicket).order_by(SupportTicket.status.asc(), SupportTicket.created_at.desc())).all()
        return jsonify([t.to_dict() for t in tickets]), 200

    @app.route("/api/admin/tickets/<int:ticket_id>", methods=["PUT"])
    @role_required("admin", "superadmin")
    def admin_reply_ticket(ticket_id):
        ticket = db.session.get(SupportTicket, ticket_id)
        if not ticket:
            return jsonify({"error": "Not Found"}), 404
        
        data = (sanitize_input(request.get_json(silent=True)) or {})
        if "status" in data:
            ticket.status = data["status"]
        if "admin_reply" in data:
            ticket.admin_reply = data["admin_reply"]
            
        db.session.commit()
        admin_id = int(get_jwt_identity())
        log_admin_action(db.session, admin_id, "Reply Ticket", "SupportTicket", ticket.id, f"Replied to ticket {ticket.id}")
        db.session.commit()
        
        return jsonify({"message": "Ticket updated", "ticket": ticket.to_dict()}), 200

    # --- Menu Items ---
    @app.route("/api/admin/menu", methods=["GET"])
    @department_required("Operations")
    def admin_get_menu():
        items = db.session.scalars(select(MenuItem).where(MenuItem.is_active == True, MenuItem.deleted_at.is_(None)).order_by(MenuItem.business_type, MenuItem.name)).all()
        return jsonify([i.to_dict() for i in items]), 200

    @app.route("/api/admin/menu", methods=["POST"])
    @department_required("Operations")
    def admin_add_menu():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        name = (data.get("name") or "").strip()
        price = data.get("price")
        btype = data.get("business_type", "home_foods")

        if not name or price is None:
            return jsonify({"error": "Bad Request", "message": "name and price are required"}), 400
        if btype not in ("home_foods", "snack_supply", "both"):
            return jsonify({"error": "Bad Request", "message": "Invalid business_type"}), 400

        # Check if an item with the same name already exists (case-insensitive)
        existing = db.session.scalars(
            select(MenuItem).where(func.lower(MenuItem.name) == name.lower())
        ).first()
        if existing:
            # Reuse existing item — reactivate and update fields
            existing.price = Decimal(str(price))
            existing.business_type = btype
            existing.description = data.get("description") or existing.description
            existing.category = data.get("category") or existing.category
            existing.image_url = data.get("image_url") or existing.image_url
            if "global_stock" in data:
                existing.global_stock = data.get("global_stock")
            existing.is_active = True
            if "code" in data and data["code"]:
                existing.code = data["code"].strip()
            elif not existing.code:
                existing.code = _generate_unique_code(db.session)
            if "is_best_seller" in data:
                if data["is_best_seller"]:
                    db.session.execute(update(MenuItem).values(is_best_seller=False))
                existing.is_best_seller = bool(data["is_best_seller"])
            if "is_popular" in data:
                existing.is_popular = bool(data["is_popular"])
            db.session.commit()
            return jsonify({"message": "Existing item reactivated", "item": existing.to_dict()}), 200

        code = (data.get("code") or "").strip()
        item = MenuItem(
            name=name, price=Decimal(str(price)), business_type=btype, code=code if code else _generate_unique_code(db.session),
            description=data.get("description"), category=data.get("category"),
            image_url=data.get("image_url"), global_stock=data.get("global_stock")
        )
        if not item.code:
            item.code = _generate_unique_code(db.session)
        if "is_best_seller" in data and data["is_best_seller"]:
            db.session.execute(update(MenuItem).values(is_best_seller=False))
            item.is_best_seller = True
        elif "is_best_seller" in data:
            item.is_best_seller = False
            
        if "is_popular" in data:
            item.is_popular = bool(data["is_popular"])
        
        db.session.add(item)
        db.session.commit()
        admin_id = int(get_jwt_identity())
        log_admin_action(db.session, admin_id, "Create Menu Item", "MenuItem", item.id, f"Created {item.name}")
        db.session.commit()
        return jsonify({"message": "Item created", "item": item.to_dict()}), 201

    @app.route("/api/admin/menu/<int:item_id>", methods=["PUT"])
    @department_required("Operations")
    def admin_edit_menu(item_id):
        item = db.session.get(MenuItem, item_id)
        if not item:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("name", "code", "description", "category", "image_url", "global_stock", "is_veg", "is_gluten_free", "spice_level", "tag", "is_popular", "ingredients", "nutritional_info", "dietary_guidelines"):
            if field in data:
                setattr(item, field, data[field])
        if "admin_rating" in data:
            val = data["admin_rating"]
            item.admin_rating = float(val) if val else None
        if "price" in data and data["price"] is not None:
            item.price = Decimal(str(data["price"]))
        if "business_type" in data and data["business_type"] in ("home_foods", "snack_supply", "both"):
            item.business_type = data["business_type"]
        if "is_active" in data:
            item.is_active = bool(data["is_active"])
        if "is_best_seller" in data:
            if data["is_best_seller"]:
                db.session.execute(update(MenuItem).values(is_best_seller=False))
            item.is_best_seller = bool(data["is_best_seller"])
            
        db.session.commit()
        return jsonify({"message": "Updated", "item": item.to_dict()}), 200

    @app.route("/api/admin/menu/<int:item_id>", methods=["DELETE", "POST"])
    @department_required("Operations")
    def admin_delete_menu(item_id):
        item = db.session.get(MenuItem, item_id)
        if not item:
            return jsonify({"error": "Not Found"}), 404
        item.is_active = False
        db.session.commit()
        admin_id = int(get_jwt_identity())
        log_admin_action(db.session, admin_id, "Deactivate Menu Item", "MenuItem", item.id, f"Deactivated {item.name}")
        db.session.commit()
        return jsonify({"message": "Item deactivated"}), 200

    # --- Outlets ---
    @app.route("/api/admin/outlets", methods=["GET"])
    @department_required("Operations")
    def admin_get_outlets():
        outlets = db.session.scalars(select(Outlet).order_by(Outlet.name)).all()
        return jsonify([o.to_dict() for o in outlets]), 200

    @app.route("/api/admin/outlets", methods=["POST"])
    @department_required("Operations")
    def admin_add_outlet():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        name = (data.get("name") or "").strip()
        address = (data.get("address") or "").strip()
        if not name or not address:
            return jsonify({"error": "Bad Request", "message": "name and address required"}), 400
        outlet = Outlet(name=name, address=address,
                        latitude=data.get("latitude"), longitude=data.get("longitude"),
                        owner_id=data.get("owner_id"))
        outlet.revenue_share_percentage = data.get("revenue_share_percentage", 0.00)
        db.session.add(outlet)
        db.session.flush()

        items_data = data.get("items", [])
        for it in items_data:
            mid = it.get("menu_item_id")
            if not mid:
                continue
            exists = db.session.scalars(
                select(OutletStock).filter_by(outlet_id=outlet.id, menu_item_id=mid)
            ).first()
            if not exists:
                stock = OutletStock(outlet_id=outlet.id, menu_item_id=mid,
                                    current_stock=int(it.get("initial_stock", 0)),
                                    restock_limit=int(it.get("threshold", 10)))
                db.session.add(stock)
        db.session.commit()
        return jsonify({"message": "Outlet created", "outlet": outlet.to_dict()}), 201

    @app.route("/api/admin/outlets/<int:outlet_id>", methods=["PUT"])
    @department_required("Operations")
    def admin_edit_outlet(outlet_id):
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("name", "address", "latitude", "longitude", "owner_id", "revenue_share_percentage"):
            if field in data:
                setattr(outlet, field, data[field])
        db.session.commit()
        return jsonify({"message": "Updated", "outlet": outlet.to_dict()}), 200

    @app.route("/api/admin/outlets/<int:outlet_id>", methods=["DELETE", "POST"])
    @department_required("Operations")
    def admin_delete_outlet(outlet_id):
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        # Bypass ORM to allow DB-level ON DELETE CASCADE to handle related non-nullable rows
        db.session.execute(db.delete(Outlet).where(Outlet.id == outlet_id))
        db.session.commit()
        return jsonify({"message": "Outlet deleted"}), 200

    # --- Outlet Stock Management ---
    @app.route("/api/admin/outlets/<int:outlet_id>/stock", methods=["POST"])
    @department_required("Operations")
    def admin_add_outlet_stock(outlet_id):
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400
        exists = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)
        ).first()
        if exists:
            return jsonify({"error": "Conflict", "message": "Item already assigned"}), 409
        stock = OutletStock(outlet_id=outlet_id, menu_item_id=mid,
                            current_stock=int(data.get("initial_stock", 0)),
                            restock_limit=int(data.get("threshold", 10)))
        db.session.add(stock)
        db.session.commit()
        log_stock_change(db.session, outlet_id=outlet_id, menu_item_id=mid,
                         change_qty=stock.current_stock, change_type="assign",
                         stock_before=0, stock_after=stock.current_stock,
                         notes="Admin assigned item to outlet")
        db.session.commit()
        return jsonify({"message": "Stock item added", "stock": stock.to_dict()}), 201

    # FIX: Added /items alias route to match frontend call
    @app.route("/api/admin/outlets/<int:outlet_id>/items", methods=["POST"])
    @department_required("Operations")
    def admin_add_outlet_item(outlet_id):
        """Alias for /stock endpoint — used by the frontend assign-item-to-outlet flow."""
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400

        exists = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)
        ).first()
        if exists:
            # Update existing stock if already assigned
            before = exists.current_stock
            if "current_stock" in data:
                exists.current_stock = int(data["current_stock"])
            if "restock_limit" in data:
                exists.restock_limit = int(data["restock_limit"])
            db.session.commit()
            log_stock_change(db.session, outlet_id=outlet_id, menu_item_id=mid,
                             change_qty=exists.current_stock - before, change_type="edit",
                             stock_before=before, stock_after=exists.current_stock,
                             notes="Admin edited stock via UI")
            return jsonify({"message": "Stock updated", "stock": exists.to_dict()}), 200

        stock = OutletStock(outlet_id=outlet_id, menu_item_id=mid,
                            current_stock=int(data.get("current_stock", 0)),
                            restock_limit=int(data.get("restock_limit", 10)))
        db.session.add(stock)
        db.session.commit()
        log_stock_change(db.session, outlet_id=outlet_id, menu_item_id=mid,
                         change_qty=stock.current_stock, change_type="assign",
                         stock_before=0, stock_after=stock.current_stock,
                         notes="Admin assigned item to outlet via UI")
        db.session.commit()
        return jsonify({"message": "Stock item added", "stock": stock.to_dict()}), 201

    # FIX: Added DELETE /items/<menu_item_id> route for frontend remove functionality
    @app.route("/api/admin/outlets/<int:outlet_id>/items/<int:menu_item_id>", methods=["DELETE"])
    @department_required("Operations")
    def admin_remove_outlet_item(outlet_id, menu_item_id):
        """Remove a specific item from an outlet's stock."""
        stock = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=menu_item_id)
        ).first()
        if not stock:
            return jsonify({"error": "Not Found", "message": "Item not assigned to this outlet"}), 404
        db.session.delete(stock)
        db.session.commit()
        return jsonify({"message": "Item removed from outlet"}), 200

    @app.route("/api/admin/outlets/<int:outlet_id>/restock", methods=["POST"])
    @department_required("Operations")
    def admin_restock_outlet(outlet_id):
        claims = get_jwt()
        admin_id = claims.get("user_id")
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        qty = int(data.get("qty", 0))
        if qty <= 0:
            return jsonify({"error": "Bad Request", "message": "qty must be > 0"}), 400
        stock = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)
        ).first()
        if not stock:
            return jsonify({"error": "Not Found"}), 404
        before = stock.current_stock
        stock.current_stock += qty
        log_stock_change(db.session, outlet_id=outlet_id, menu_item_id=mid,
                         change_qty=qty, change_type="manual",
                         stock_before=before, stock_after=stock.current_stock,
                         performed_by=admin_id, notes="Admin manual restock")
        db.session.commit()
        return jsonify({"message": f"+{qty} stocked", "new_stock": stock.current_stock}), 200

    @app.route("/api/admin/revenue-share", methods=["GET"])
    @department_required("Finance")
    def admin_revenue_share():
        outlets = db.session.scalars(select(Outlet)).all()
        results = []
        for o in outlets:
            total_sales = db.session.scalar(
                select(func.sum(Order.total_price))
                .where(Order.outlet_id == o.id)
                .where(Order.status == 'delivered')
            ) or Decimal('0.00')
            share_pct = o.revenue_share_percentage or Decimal('0.00')
            brand_cut = Decimal(total_sales) * (Decimal(share_pct) / Decimal('100.0'))
            results.append({
                "outlet_id": o.id,
                "outlet_name": o.name,
                "total_sales": float(total_sales),
                "revenue_share_percentage": float(share_pct),
                "brand_cut": round(float(brand_cut), 2)
            })
        return jsonify(results), 200

    # --- Admin Resets ---
    @app.route("/api/admin/reset/orders", methods=["POST"])
    @department_required("IT", "Operations", "Owner")
    def admin_reset_orders():
        try:
            db.session.query(OrderItem).delete()
            db.session.query(Order).delete()
            db.session.commit()
            return jsonify({"message": "All orders and order items have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    @app.route("/api/admin/reset/reviews", methods=["POST"])
    @department_required("IT", "Owner")
    def admin_reset_reviews():
        try:
            db.session.query(Review).delete()
            db.session.commit()
            return jsonify({"message": "All reviews have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    @app.route("/api/admin/reset/stock", methods=["POST"])
    @department_required("IT", "Operations", "Owner")
    def admin_reset_stock():
        try:
            db.session.execute(update(MenuItem).values(global_stock=0))
            db.session.commit()
            return jsonify({"message": "All product global stock levels have been set to 0."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    @app.route("/api/admin/reset/analytics", methods=["POST"])
    @department_required("IT", "Owner")
    def admin_reset_analytics():
        try:
            db.session.query(OrderItem).delete()
            db.session.query(Order).delete()
            db.session.query(WalletTransaction).delete()
            db.session.query(User).update({Customer.loyalty_points: 0})
            db.session.commit()
            return jsonify({"message": "Sales, Analytics and Wallets have been reset to zero."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    @app.route("/api/admin/reset/menu", methods=["POST"])
    @department_required("IT", "Owner")
    def admin_reset_menu():
        try:
            db.session.query(Review).delete()
            db.session.query(MenuItem).delete()
            db.session.commit()
            return jsonify({"message": "Factory Reset successful: All Menu items and categories have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    @app.route("/api/admin/reset/customers", methods=["POST"])
    @department_required("IT", "Owner")
    def admin_reset_customers():
        try:
            db.session.query(User).filter(User.role == 'customer').delete(synchronize_session=False)
            db.session.commit()
            return jsonify({"message": "All customer accounts have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    # --- Orders (admin) ---
    @app.route("/api/admin/orders", methods=["GET"])
    @department_required("Finance", "Operations")
    def admin_get_orders():
        orders = db.session.scalars(
            select(Order).order_by(Order.created_at.desc()).limit(200)
        ).unique().all()
        return jsonify([o.to_dict() for o in orders]), 200

    @app.route("/api/admin/orders/<int:order_id>", methods=["PUT"])
    @department_required("Finance", "Operations")
    def admin_update_order(order_id):
        order = db.session.get(Order, order_id)
        if not order:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        valid = ("pending", "processing", "shipped", "delivered", "completed", "cancelled", "refunded", "payment_failed")
        if "status" in data and data["status"] in valid:
            old_status = order.status
            order.status = data["status"]
            
            award_statuses = ["delivered", "completed"]
            reverse_statuses = ["cancelled", "refunded", "payment_failed"]
            
            # If changing TO an awarding status from a non-awarding status
            if order.status in award_statuses and old_status not in award_statuses:
                if order.customer_id and order.loyalty_points_earned > 0:
                    customer = db.session.scalars(select(User).where(User.id == order.customer_id).with_for_update()).first()
                    if customer:
                        customer.loyalty_points = (customer.loyalty_points or 0) + order.loyalty_points_earned
                        db.session.add(WalletTransaction(
                            user_id=customer.id, amount=order.loyalty_points_earned, transaction_type="credit",
                            description=f"Points awarded for completion of Order #{order.id}"
                        ))
            
            # If changing TO a reverse status from a non-reverse status
            if order.status in reverse_statuses and old_status not in reverse_statuses:
                for item in order.items:
                    menu_item = db.session.scalars(select(MenuItem).where(MenuItem.id == item.menu_item_id).with_for_update()).first()
                    if menu_item and menu_item.global_stock is not None:
                        menu_item.global_stock += item.quantity
                if order.applied_coupon_code:
                    coupon = db.session.scalars(select(Coupon).where(Coupon.code == order.applied_coupon_code).with_for_update()).first()
                    if coupon and coupon.usage_count > 0:
                        coupon.usage_count -= 1

                if order.customer_id:
                    customer = db.session.scalars(select(User).where(User.id == order.customer_id).with_for_update()).first()
                    if customer:
                        # Reverse awarded points ONLY IF they were previously awarded
                        if old_status in award_statuses and order.loyalty_points_earned and order.loyalty_points_earned > 0:
                            customer.loyalty_points = max(0, (customer.loyalty_points or 0) - order.loyalty_points_earned)
                            db.session.add(WalletTransaction(
                                user_id=customer.id, amount=-order.loyalty_points_earned, transaction_type="debit",
                                description=f"Points deducted due to {order.status} of Order #{order.id}"
                            ))
                        
                        # ALWAYS refund redeemed points on cancel/refund/fail (since they were deducted at checkout)
                        if order.loyalty_points_redeemed and order.loyalty_points_redeemed > 0:
                            customer.loyalty_points = (customer.loyalty_points or 0) + order.loyalty_points_redeemed
                            db.session.add(WalletTransaction(
                                user_id=customer.id, amount=order.loyalty_points_redeemed, transaction_type="credit",
                                description=f"Points refunded due to {order.status} of Order #{order.id}"
                            ))
        if "tracking_code" in data:
            order.tracking_code = data["tracking_code"]
        db.session.commit()
        return jsonify({"message": "Updated", "order": order.to_dict()}), 200

    @app.route("/api/admin/orders/<int:order_id>/ship", methods=["PUT"])
    @department_required("Finance", "Operations")
    def admin_ship_order(order_id):
        """Mark order as shipped with a tracking code and optional label upload."""
        order = db.session.get(Order, order_id)
        if not order:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        tracking_code = (data.get("tracking_code") or "").strip()
        tracking_label = data.get("tracking_label")
        order.status = "shipped"
        order.tracking_code = tracking_code if tracking_code else None
        order.delivery_confirmation_code = str(random.randint(100000, 999999))
        if tracking_label:
            order.tracking_label = tracking_label
        tracking_link = (data.get("tracking_link") or "").strip()
        if tracking_link:
            order.tracking_link = tracking_link
        db.session.commit()

        # Send order shipped email to customer
        customer = db.session.get(User, order.customer_id)
        if customer and customer.email:
            _send_order_shipped_email(app, order, customer, tracking_code)

        return jsonify({"message": "Order marked as shipped", "order": order.to_dict()}), 200

    # --- Refunds ---
    @app.route("/api/admin/orders/<int:order_id>/refund", methods=["POST"])
    @department_required("Finance", "Operations")
    def admin_refund_order(order_id):
        order = db.session.get(Order, order_id)
        if not order:
            return jsonify({"error": "Not Found"}), 404
        if order.status in ("refunded", "cancelled"):
            return jsonify({"error": "Bad Request", "message": "Order already refunded or cancelled"}), 400
        data = sanitize_input(request.get_json(silent=True)) or {}
        reason = (data.get("reason") or "").strip()
        amount = data.get("amount")
        if not reason:
            return jsonify({"error": "Bad Request", "message": "Refund reason is required"}), 400
        refund_amount = Decimal(str(amount)) if amount else order.total_price
        order.refund_status = "refunded"
        order.refund_amount = refund_amount
        order.refund_reason = reason
        order.status = "refunded"
        db.session.commit()
        manual_log_audit("refund_order", "Order", order_id,
                         old_value=f"status={order.status},amount={order.total_price}",
                         new_value=f"refund_amount={refund_amount},reason={reason}")
        return jsonify({"message": "Refund processed", "order": order.to_dict()}), 200

    

    # --- POS Fast-Switch PIN/RFID Unlock ---
    @app.route("/api/auth/pos/unlock", methods=["POST"])
    @limiter.limit("10 per minute")
    def pos_unlock():
        """
        Accepts staff_code + pin (or rfid_tag). Validates and issues a short-lived 10-min JWT.
        Does NOT require an existing auth token — used by shared POS kiosk lock screens.
        """
        data = sanitize_input(request.get_json(silent=True)) or {}
        pin = data.get("pin")
        rfid = data.get("rfid_tag")
        staff_code = (data.get("staff_code") or "").strip()

        user = None
        if rfid:
            user = db.session.scalars(select(User).where(User.rfid_tag == rfid)).first()
        elif staff_code and pin:
            user = db.session.scalars(select(User).where(User.staff_code == staff_code)).first()
            if user and not user.check_pin(str(pin), bcrypt):
                user = None

        if not user or not user.is_active:
            import time; time.sleep(1)
            return jsonify({"error": "Unauthorized", "message": "Invalid credentials"}), 401

        additional_claims = {
            "role": user.role,
            "outlet_id": user.outlet_id,
            "user_id": user.id,
            "token_version": getattr(user, "token_version", 0)
        }
        token = create_access_token(
            identity=str(user.id),
            additional_claims=additional_claims,
            expires_delta=timedelta(minutes=10)
        )
        manual_log_audit("pos_unlock", "User", user.id)
        return jsonify({"access_token": token, "user": user.to_dict()}), 200

    # --- Kitchen Active Orders (Zero PII) ---
    @app.route("/api/kitchen/active-orders", methods=["GET"])
    @role_required("kitchen", "admin")
    def kitchen_active_orders():
        """Returns active orders with zero PII — kitchen screen safe."""
        orders_q = db.session.scalars(
            select(Order)
            .where(Order.order_type == "online", Order.status.in_(["pending", "processing"]))
            .order_by(Order.created_at.asc())
        ).unique().all()
        result = []
        for o in orders_q:
            result.append({
                "id": o.id,
                "ticket_number": f"#{o.id:04d}",
                "status": o.status,
                "order_type": o.order_type,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": [
                    {
                        "name": i.menu_item.name if i.menu_item else "Unknown",
                        "quantity": i.quantity,
                        "notes": getattr(i, "notes", None)
                    }
                    for i in o.items
                ],
                "table_number": getattr(o, "table_number", None),
                "minutes_waiting": round((datetime.now(timezone.utc) - o.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60, 1) if o.created_at else 0
            })
        return jsonify(result), 200

    # --- Staff Management ---
    @app.route("/api/admin/staff", methods=["GET"])
    @role_required("admin", "outlet_owner")
    def admin_get_staff():
        user_id = get_jwt_identity()
        current_user = db.session.get(User, user_id)
        
        query = select(User).where(
            User.role.in_(["staff", "outlet_owner", "kitchen", "customer"]),
            User.deleted_at.is_(None)
        ).order_by(User.created_at.desc())
        
        # Scope to outlet if not admin
        if current_user.role != "admin" and hasattr(current_user, "outlet_id"):
            query = query.outerjoin(Staff, User.id == Staff.id).where(Staff.outlet_id == current_user.outlet_id)

        staff = db.session.scalars(query).all()
        return jsonify([u.to_dict() for u in staff]), 200

    @app.route("/api/admin/staff", methods=["POST"])
    @department_required("HR")
    def admin_create_staff():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        email = (data.get("email") or "").strip().lower()
        password = data.get("password")
        if not password:
            import secrets
            import string
            password = "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
        outlet_id = data.get("outlet_id")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        valid_phone, phone = validate_phone(data.get("phone"))
        if not valid_phone:
            return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
        role = (data.get("role") or "staff").strip().lower()

        if role not in ("staff", "admin", "outlet_owner", "kitchen"):
            return jsonify({"error": "Bad Request", "message": "Invalid role"}), 400

        claims = get_jwt()
        if role == "admin" and not claims.get("is_superadmin"):
            return jsonify({"error": "Forbidden", "message": "Only super-admins can create admin accounts"}), 403
        if role == "outlet_owner" and claims.get("role") != "admin":
            return jsonify({"error": "Forbidden", "message": "Only admins can create outlet owners"}), 403

        if not email:
            return jsonify({"error": "Bad Request", "message": "email required"}), 400
        if db.session.scalars(select(User).where(User.email == email)).first():
            return jsonify({"error": "Conflict", "message": "Email already exists"}), 409

        if role == "admin":
            admin_count = db.session.scalar(
                select(func.count(User.id)).where(User.role == "admin")
            )
            if admin_count >= 3:
                return jsonify({"error": "Conflict", "message": "Maximum of 3 admin accounts allowed."}), 409

        if role == "admin":
            dept = data.get("admin_department")
            if not dept or dept not in ["Finance", "Operations", "HR"]:
                return jsonify({"error": "Bad Request", "message": "admin_department is required and must be Finance, Operations, or HR"}), 400
            user = Admin(email=email, first_name=first_name, last_name=last_name, phone=phone)
            user.admin_department = dept
        elif role == "staff":
            user = Staff(email=email, first_name=first_name, last_name=last_name, phone=phone, outlet_id=outlet_id)
        elif role == "outlet_owner":
            # pyrefly: ignore [unexpected-keyword]
            user = OutletOwner(email=email, first_name=first_name, last_name=last_name, phone=phone, outlet_id=outlet_id)
        elif role == "kitchen":
            user = KitchenStaff(email=email, first_name=first_name, last_name=last_name, phone=phone, outlet_id=outlet_id)
        elif role == "customer":
            user = Customer(email=email, first_name=first_name, last_name=last_name, phone=phone)
        else:
            return jsonify({"error": "Bad Request", "message": "Invalid role"}), 400
        user.set_password(password, bcrypt)
        # Generate 4-digit staff code for staff/kitchen
        if role in ("staff", "kitchen"):
            import random
            while True:
                code = str(random.randint(1000, 9999))
                if not db.session.scalars(select(User).where(User.staff_code == code)).first():
                    user.staff_code = code
                    break
        # Require 4-digit PIN for staff and kitchen
        if role in ("staff", "kitchen"):
            pin = (data.get("pin") or "").strip()
            if not pin or len(pin) != 4 or not pin.isdigit():
                return jsonify({"error": "Bad Request", "message": "A 4-digit PIN is required for staff and kitchen accounts"}), 400
            user.set_pin(pin, bcrypt)

        db.session.add(user)
        db.session.commit()

        if role in ("staff", "outlet_owner"):
            outlet = db.session.get(Outlet, outlet_id) if outlet_id else None
            _send_staff_created_email(app, user, outlet)
        else:
            _send_admin_created_email(app, user)

        return jsonify({"message": f"{role.capitalize()} created", "user": user.to_dict()}), 201

    @app.route("/api/admin/staff/<int:user_id>", methods=["PUT"])
    @department_required("HR")
    def admin_edit_staff(user_id):
        user = db.session.get(User, user_id)
        if not user or user.role not in ("staff", "admin", "outlet_owner", "kitchen", "customer"):
            return jsonify({"error": "Not Found"}), 404
        if getattr(user, 'is_superadmin', False):
            return jsonify({"error": "Forbidden", "message": "Cannot modify a super-admin."}), 403
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("first_name", "last_name"):
            if field in data:
                setattr(user, field, data[field])
        if "phone" in data:
            valid_phone, phone_clean = validate_phone(data["phone"])
            if not valid_phone:
                return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
            user.phone = phone_clean
        if "outlet_id" in data:
            user.outlet_id = data["outlet_id"]
        if "is_active" in data:
            new_active = bool(data["is_active"])
            if user.is_active and not new_active:
                user.bump_token_version()
            user.is_active = new_active
        if "loyalty_points" in data and user.role == "customer":
            claims = get_jwt()
            if not claims.get("is_superadmin"):
                return jsonify({"error": "Forbidden", "message": "Only superadmin can modify loyalty points directly."}), 403
            try:
                new_points = int(data["loyalty_points"])
            except (TypeError, ValueError):
                return jsonify({"error": "Bad Request", "message": "loyalty_points must be an integer"}), 400
            if new_points < 0:
                return jsonify({"error": "Bad Request", "message": "loyalty_points cannot be negative"}), 400
            old_points = user.loyalty_points or 0
            user.loyalty_points = new_points
            # Journal the adjustment so it appears in the user's history.
            delta = new_points - old_points
            if delta != 0:
                db.session.add(WalletTransaction(
                    user_id=user.id,
                    amount=delta,
                    transaction_type="credit" if delta > 0 else "debit",
                    description=f"Admin balance adjustment: {old_points} -> {new_points}"
                ))
            log_admin_action(db.session, get_jwt_identity(), "set_loyalty_points", "User", user.id, f"Loyalty points changed from {old_points} to {user.loyalty_points}")
        if "pin" in data:
            pin = (data["pin"] or "").strip()
            if pin:
                if not pin.isdigit() or len(pin) != 4:
                    return jsonify({"error": "Bad Request", "message": "PIN must be exactly 4 digits"}), 400
                user.set_pin(pin, bcrypt)
            else:
                # Empty string = remove PIN
                user.pin_hash = None
        password_changed = False
        import re
        if "password" in data:
            if len(data["password"]) >= 8 and re.search(r'[A-Za-z]', data["password"]) and re.search(r'[0-9]', data["password"]):
                user.set_password(data["password"], bcrypt)
                password_changed = True
            else:
                return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain both letters and numbers."}), 400
            
        db.session.commit()

        if password_changed and user.role == "admin" and user.email:
            _send_admin_password_changed_email(app, user)

        return jsonify({"message": "Updated", "user": user.to_dict()}), 200

    @app.route("/api/admin/staff/<int:user_id>", methods=["DELETE"])
    @department_required("HR")
    def admin_delete_staff(user_id):
        user = db.session.get(User, user_id)
        if not user or user.role not in ("staff", "admin", "outlet_owner", "kitchen", "customer"):
            return jsonify({"error": "Not Found"}), 404

        if getattr(user, 'is_superadmin', False):
            return jsonify({"error": "Forbidden", "message": "Cannot delete a super-admin."}), 403

        if user.role == "admin":
            admin_count = db.session.scalar(select(func.count(User.id)).where(User.role == "admin"))
            if admin_count <= 1:
                return jsonify({"error": "Conflict", "message": "Cannot delete the last admin account."}), 409

        user.deleted_at = datetime.now(timezone.utc)
        user.bump_token_version() # invalidate existing sessions
        db.session.commit()
        return jsonify({"message": "Staff deleted successfully (soft delete)"}), 200

    # --- Coupons (Admin) ---
    @app.route("/api/admin/coupons", methods=["GET"])
    @role_required("admin", "outlet_owner")
    def admin_get_coupons():
        coupons = db.session.scalars(select(Coupon).where(Coupon.deleted_at.is_(None)).order_by(Coupon.created_at.desc())).all()
        return jsonify([c.to_dict() for c in coupons]), 200

    @app.route("/api/admin/coupons", methods=["POST"])
    @department_required("Finance")
    def admin_add_coupon():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        code = (data.get("code") or "").strip()
        pct = data.get("discount_pct")
        amt = data.get("discount_amount")
        if not code or (pct is None and amt is None):
            return jsonify({"error": "Bad Request", "message": "Code and either discount percentage or flat amount are required."}), 400
        
        expiry_date = None
        if data.get("expiry_date"):
            expiry_date = datetime.strptime(data.get("expiry_date"), "%Y-%m-%d").date()

        coupon = Coupon(
            code=code,
            discount_pct=pct,
            discount_amount=Decimal(str(amt)) if amt else None,
            max_discount_amount=Decimal(str(data["max_discount_amount"])) if data.get("max_discount_amount") else None,
            applicable_menu_item_id=data.get("applicable_menu_item_id") or None,
            applicable_customer_id=data.get("applicable_customer_id") or None,
            expiry_date=expiry_date,
            usage_limit=data.get("usage_limit") or None,
            is_active=bool(data.get("is_active", True)),
            min_order_value=Decimal(str(data["min_order_value"])) if data.get("min_order_value") else Decimal("0"),
            is_first_order_only=bool(data.get("is_first_order_only", False)),
            scope=data.get("scope", "both")
        )
        db.session.add(coupon)
        db.session.commit()
        return jsonify({"message": "Coupon created", "coupon": coupon.to_dict()}), 201

    @app.route("/api/admin/coupons/<int:id>", methods=["PUT"])
    @department_required("Finance")
    def admin_edit_coupon(id):
        coupon = db.session.get(Coupon, id)
        if not coupon:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        if "discount_pct" in data:
            coupon.discount_pct = data["discount_pct"]
        if "discount_amount" in data:
            coupon.discount_amount = Decimal(str(data["discount_amount"])) if data["discount_amount"] else None
        if "max_discount_amount" in data:
            coupon.max_discount_amount = Decimal(str(data["max_discount_amount"])) if data["max_discount_amount"] else None
        if "expiry_date" in data:
            if data["expiry_date"]:
                coupon.expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
            else:
                coupon.expiry_date = None
        if "usage_limit" in data:
            coupon.usage_limit = data["usage_limit"]
        if "is_active" in data:
            coupon.is_active = bool(data["is_active"])
        if "scope" in data:
            coupon.scope = data["scope"] if data["scope"] in ("both", "outlet", "customer") else "both"
        if "min_order_value" in data:
            coupon.min_order_value = Decimal(str(data["min_order_value"])) if data["min_order_value"] else Decimal("0")
        if "is_first_order_only" in data:
            coupon.is_first_order_only = bool(data["is_first_order_only"])
        db.session.commit()
        return jsonify({"message": "Coupon updated", "coupon": coupon.to_dict()}), 200

    @app.route("/api/admin/coupons/<int:id>", methods=["DELETE"])
    @department_required("Finance")
    def admin_delete_coupon(id):
        coupon = db.session.get(Coupon, id)
        if not coupon:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(coupon)
        db.session.commit()
        return jsonify({"message": "Coupon deleted"}), 200

    # --- Suppliers ---
    @app.route("/api/admin/suppliers", methods=["GET"])
    @department_required("Operations")
    def admin_get_suppliers():
        suppliers = db.session.scalars(select(Supplier).order_by(Supplier.name)).all()
        return jsonify([s.to_dict() for s in suppliers]), 200

    @app.route("/api/admin/suppliers", methods=["POST"])
    @department_required("Operations")
    def admin_add_supplier():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Bad Request", "message": "name required"}), 400
        valid_phone, phone_clean = validate_phone(data.get("phone"))
        if not valid_phone:
            return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
        s = Supplier(name=name, contact_name=data.get("contact_name"),
                     phone=phone_clean, email=data.get("email"),
                     address=data.get("address"), notes=data.get("notes"))
        db.session.add(s)
        db.session.commit()
        return jsonify({"message": "Supplier created", "supplier": s.to_dict()}), 201

    @app.route("/api/admin/suppliers/<int:sid>", methods=["PUT"])
    @department_required("Operations")
    def admin_edit_supplier(sid):
        s = db.session.get(Supplier, sid)
        if not s:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for f in ("name", "contact_name", "email", "address", "notes", "is_active"):
            if f in data:
                setattr(s, f, data[f])
        if "phone" in data:
            valid_phone, phone_clean = validate_phone(data["phone"])
            if not valid_phone:
                return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
            s.phone = phone_clean
        db.session.commit()
        return jsonify({"message": "Updated", "supplier": s.to_dict()}), 200

    @app.route("/api/admin/suppliers/<int:sid>", methods=["DELETE"])
    @department_required("Operations")
    def admin_delete_supplier(sid):
        s = db.session.get(Supplier, sid)
        if not s:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(s)
        db.session.commit()
        return jsonify({"message": "Supplier deleted"}), 200

    @app.route("/api/admin/suppliers/<int:sid>/items", methods=["POST"])
    @department_required("Operations")
    def admin_link_supplier_item(sid):
        s = db.session.get(Supplier, sid)
        if not s:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400
        exists = db.session.scalars(
            select(SupplierItem).filter_by(supplier_id=sid, menu_item_id=mid)
        ).first()
        if exists:
            return jsonify({"error": "Conflict", "message": "Already linked"}), 409
        si = SupplierItem(supplier_id=sid, menu_item_id=mid,
                          cost_price=data.get("cost_price"),
                          lead_days=int(data.get("lead_days", 1)))
        db.session.add(si)
        db.session.commit()
        return jsonify({"message": "Linked", "item": si.to_dict()}), 201
    # ============================================================
    # 2.5. KITCHEN ROUTES (role: kitchen)
    # ============================================================
    
    @app.route("/api/kitchen/orders", methods=["GET"])
    @role_required("kitchen", "admin")
    def kitchen_get_orders():
        # Get all online orders that need preparation
        orders = db.session.scalars(
            select(Order)
            .where(Order.order_type == "online", Order.status.in_(["pending", "processing"]))
            .order_by(Order.created_at.asc())
        ).unique().all()
        return jsonify([o.to_dict() for o in orders]), 200

    @app.route("/api/kitchen/orders/<int:order_id>/status", methods=["PUT"])
    @role_required("kitchen", "admin")
    def kitchen_update_order_status(order_id):
        order = db.session.get(Order, order_id)
        if not order:
            return jsonify({"error": "Not Found"}), 404
            
        data = sanitize_input(request.get_json(silent=True)) or {}
        status = data.get("status")
        if status not in ["pending", "processing", "ready"]:
            return jsonify({"error": "Bad Request", "message": "Invalid status"}), 400
            
        order.status = status
        db.session.commit()
        return jsonify({"message": "Status updated", "order": order.to_dict()}), 200

    @app.route("/api/kitchen/stock-requests", methods=["GET"])
    @role_required("kitchen", "admin")
    def get_stock_requests():
        requests = db.session.scalars(select(StockRequest).order_by(StockRequest.created_at.desc())).all()
        return jsonify([req.to_dict() for req in requests]), 200

    @app.route("/api/kitchen/stock-requests", methods=["POST"])
    @jwt_required()
    def create_stock_request():
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user or user.role not in ("staff", "admin", "outlet_owner", "kitchen"):
            return jsonify({"error": "Forbidden"}), 403
            
        data = sanitize_input(request.get_json(silent=True)) or {}
        outlet_id = data.get("outlet_id")
        if not outlet_id and getattr(user, 'outlet_id', None):
            outlet_id = user.outlet_id
        
        if not outlet_id:
            return jsonify({"error": "Bad Request", "message": "outlet_id is required"}), 400
            
        req = StockRequest(
            outlet_id=outlet_id,
            menu_item_id=data.get("menu_item_id"),
            quantity=int(data.get("quantity", 1)),
            staff_id=uid,
            request_type=data.get("type", "Restock")
        )
        db.session.add(req)
        db.session.commit()
        return jsonify({"message": "Request submitted", "stock_request": req.to_dict()}), 201

    @app.route("/api/kitchen/stock-requests/<int:req_id>/status", methods=["PUT"])
    @role_required("kitchen", "admin")
    def update_stock_request_status(req_id):
        data = request.json or {}
        new_status = data.get("status")
        req = db.session.get(StockRequest, req_id)
        if not req:
            return jsonify({"error": "Not Found"}), 404
            
        # Scope authorization to the outlet of the stock request
        user_id = get_jwt_identity()
        current_user = db.session.get(User, user_id)
        if current_user.role != "admin":
            if not hasattr(current_user, "outlet_id") or current_user.outlet_id != req.outlet_id:
                return jsonify({"error": "Forbidden", "message": "Cannot modify stock requests for a different outlet"}), 403

        req.status = new_status
        
        # Auto-update outlet stock only when dispatched/fulfilled
        if new_status in ["Dispatched", "Fulfilled"]:
            stock = db.session.scalars(select(OutletStock).where(OutletStock.outlet_id == req.outlet_id, OutletStock.menu_item_id == req.menu_item_id)).first()
            if stock:
                stock.current_stock += req.quantity
            else:
                stock = OutletStock(outlet_id=req.outlet_id, menu_item_id=req.menu_item_id, current_stock=req.quantity)
                db.session.add(stock)
            
        db.session.commit()
        return jsonify({"message": f"Request {new_status.lower()}", "stock_request": req.to_dict()}), 200

    @app.route("/api/kitchen/produce", methods=["POST"])
    @role_required("kitchen", "admin")
    def kitchen_produce_batch():
        import hashlib, hmac
        uid = int(get_jwt_identity())
        data = sanitize_input(request.get_json(silent=True)) or {}
        
        menu_item_id = data.get("menu_item_id")
        quantity = data.get("quantity")
        expiry_date_str = data.get("expiry_date")
        
        if not menu_item_id or not quantity or not expiry_date_str:
            return jsonify({"error": "Bad Request", "message": "Missing required fields"}), 400
            
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Bad Request", "message": "Invalid expiry_date format. Use YYYY-MM-DD"}), 400
            
        # Generate batch number
        batch_number = f"B-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        
        batch = KitchenProductionBatch(
            menu_item_id=menu_item_id,
            batch_number=batch_number,
            quantity_produced=quantity,
            expiry_date=expiry_date,
            produced_by=uid
        )
        
        db.session.add(batch)
        db.session.flush() # get batch ID
        
        # Generate QR Code Payload
        qr_payload = {
            "action": "receive_batch",
            "batch_number": batch_number,
            "menu_item_id": menu_item_id,
            "quantity": quantity,
            "expiry_date": expiry_date_str
        }
        
        # Sign payload
        serialized = json.dumps(qr_payload, sort_keys=True)
        signature = hmac.new(app.config["SECRET_KEY"].encode(), serialized.encode(), hashlib.sha256).hexdigest()
        qr_payload["signature"] = signature
        
        try:
            payload_str = json.dumps(qr_payload)
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(payload_str)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            # pyrefly: ignore [unexpected-keyword]
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("utf-8")
            
            # Save QR to DB
            batch.qr_code_base64 = f"data:image/png;base64,{b64}"
            
        except Exception as e:
            logger.error(f"QR generation failed in kitchen_produce_batch: {e}")
            
        db.session.commit()
        
        return jsonify({
            "message": "Batch produced successfully", 
            "batch": batch.to_dict()
        }), 201


    # ============================================================
    # 3. ADMIN ROUTES
    # ============================================================

    # --- Analytics ---
    @app.route("/api/admin/audit-logs", methods=["GET"])
    @jwt_required()
    @role_required("admin")
    def get_audit_logs():
        limit = request.args.get("limit", 100, type=int)
        logs = db.session.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).all()
        return jsonify([log.to_dict() for log in logs]), 200

    @app.route("/api/admin/revenue/reset", methods=["POST"])
    @jwt_required()
    @role_required("admin", "outlet_owner")
    def reset_revenue():
        claims = get_jwt()
        role = claims.get("role")
        user_outlet_id = claims.get("outlet_id")
        uid = int(claims.get("sub"))
        
        data = sanitize_input(request.get_json(silent=True)) or {}
        outlet_id = data.get("outlet_id")
        
        if role == "outlet_owner":
            outlet_id = user_outlet_id
            
        if not outlet_id:
            return jsonify({"error": "Bad Request", "message": "outlet_id is required"}), 400
            
        outlet = db.session.get(Outlet, int(outlet_id))
        if not outlet:
            return jsonify({"error": "Not Found", "message": "Outlet not found"}), 404
            
        since = outlet.revenue_cutoff_date or datetime(1970, 1, 1, tzinfo=timezone.utc)
        rev = db.session.scalar(
            select(func.sum(Order.total_price))
            .where(Order.outlet_id == outlet.id, Order.created_at >= since, Order.status != "cancelled")
        ) or 0
        
        if rev > 0:
            month_year = datetime.now(timezone.utc).strftime("%Y-%m")
            history = MonthlyRevenueHistory()
            history.outlet_id = outlet.id
            history.month_year = month_year
            history.total_revenue = rev
            history.reset_by_admin_id = uid
            db.session.add(history)
            
        outlet.revenue_cutoff_date = datetime.now(timezone.utc)
        db.session.commit()
        
        manual_log_audit("reset_revenue", "Outlet", outlet.id, new_value=str(outlet.revenue_cutoff_date))
        return jsonify({"message": "Revenue counter reset successfully", "recorded_revenue": float(rev)}), 200

    @app.route("/api/admin/revenue/history", methods=["GET"])
    @jwt_required()
    @role_required("admin", "outlet_owner")
    def get_revenue_history():
        claims = get_jwt()
        role = claims.get("role")
        user_outlet_id = claims.get("outlet_id")
        
        if role == "admin":
            history = db.session.scalars(select(MonthlyRevenueHistory).order_by(MonthlyRevenueHistory.created_at.desc())).all()
        else:
            history = db.session.scalars(select(MonthlyRevenueHistory).where(MonthlyRevenueHistory.outlet_id == user_outlet_id).order_by(MonthlyRevenueHistory.created_at.desc())).all()
            
        return jsonify([h.to_dict() for h in history]), 200

    @app.route("/api/admin/analytics", methods=["GET"])
    @role_required("admin", "outlet_owner")
    def admin_analytics():
        claims = get_jwt()
        role = claims.get("role")
        user_outlet_id = claims.get("outlet_id")
        share_pct = 0.0

        days = int(request.args.get("days", 30))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Base conditions
        b2c_conditions = [Order.created_at >= since, Order.order_type == "online", Order.status != "cancelled"]
        pos_conditions = [Order.created_at >= since, Order.order_type == "pos", Order.status != "cancelled"]
        
        if role == "outlet_owner" and user_outlet_id:
            b2c_conditions.append(Order.outlet_id == user_outlet_id)
            pos_conditions.append(Order.outlet_id == user_outlet_id)
            outlet_obj = db.session.get(Outlet, user_outlet_id)
            if outlet_obj and outlet_obj.revenue_share_percentage:
                share_pct = float(outlet_obj.revenue_share_percentage)

        # B2C revenue
        b2c_rev = db.session.scalar(
            select(func.sum(Order.total_price))
            .outerjoin(Outlet, Order.outlet_id == Outlet.id)
            .where(*b2c_conditions)
            .where(or_(Outlet.id.is_(None), Outlet.revenue_cutoff_date.is_(None), Order.created_at >= Outlet.revenue_cutoff_date))
        ) or 0

        # POS revenue
        pos_rev = db.session.scalar(
            select(func.sum(Order.total_price))
            .outerjoin(Outlet, Order.outlet_id == Outlet.id)
            .where(*pos_conditions)
            .where(or_(Outlet.id.is_(None), Outlet.revenue_cutoff_date.is_(None), Order.created_at >= Outlet.revenue_cutoff_date))
        ) or 0

        if role == "outlet_owner" and user_outlet_id:
            outlet = db.session.get(Outlet, user_outlet_id)
            brand_share = float(outlet.revenue_share_percentage) if outlet and outlet.revenue_share_percentage is not None else 0.0
            outlet_share = 100.0 - brand_share
            if 0 <= outlet_share <= 100:
                b2c_rev = b2c_rev * (outlet_share / 100.0)
                pos_rev = pos_rev * (outlet_share / 100.0)
            else:
                b2c_rev = 0
                pos_rev = 0

        # Orders count
        b2c_count = db.session.scalar(
            select(func.count(Order.id)).where(*b2c_conditions)
        ) or 0
        pos_count = db.session.scalar(
            select(func.count(Order.id)).where(*pos_conditions)
        ) or 0

        # Top B2C items
        top_b2c = db.session.execute(
            select(MenuItem.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*b2c_conditions)
            .group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5)
        ).fetchall()

        # Top POS items
        top_pos = db.session.execute(
            select(MenuItem.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*pos_conditions)
            .group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5)
        ).fetchall()

        # Outlet revenue
        outlet_rev = db.session.execute(
            select(Outlet.name, func.sum(Order.total_price).label("rev"))
            .join(Order, Order.outlet_id == Outlet.id)
            .where(*pos_conditions)
            .where(or_(Outlet.revenue_cutoff_date.is_(None), Order.created_at >= Outlet.revenue_cutoff_date))
            .group_by(Outlet.name).order_by(func.sum(Order.total_price).desc())
        ).fetchall()

        # Daily B2C & POS revenue (last 7 days)
        daily_data = []
        end_date = datetime.now(timezone.utc)
        start_date = (end_date - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

        d_cond = [Order.created_at >= start_date, Order.status != "cancelled"]
        if role == "outlet_owner" and user_outlet_id:
            d_cond.append(Order.outlet_id == user_outlet_id)

        sales_data = db.session.execute(
            select(
                func.date(Order.created_at).label('sale_date'),
                Order.order_type,
                func.sum(Order.total_price).label('total_rev')
            )
            .where(*d_cond)
            .group_by(func.date(Order.created_at), Order.order_type)
        ).fetchall()

        sales_map = {}
        for row in sales_data:
            date_str = str(row.sale_date)
            if date_str not in sales_map:
                sales_map[date_str] = {"online": 0, "pos": 0}
            
            val = float(row.total_rev or 0)
            if role == "outlet_owner" and user_outlet_id:
                val = val * (share_pct / 100.0)

            if row.order_type in sales_map[date_str]:
                sales_map[date_str][row.order_type] += val

        for i in range(6, -1, -1):
            day = end_date - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            
            daily_data.append({
                "date": day.strftime("%d/%m"),
                "b2c": sales_map.get(day_str, {}).get("online", 0),
                "pos": sales_map.get(day_str, {}).get("pos", 0)
            })

        # Low stock
        low_stock_cond = [OutletStock.current_stock <= OutletStock.restock_limit]
        if role == "outlet_owner" and user_outlet_id:
            low_stock_cond.append(OutletStock.outlet_id == user_outlet_id)
            
        low_stock = db.session.scalars(
            select(OutletStock).where(*low_stock_cond)
        ).all()

        # Expiring batches (within 3 days)
        from datetime import date as date_cls
        today = date_cls.today()
        expiring_cond = [ProductBatch.expiry_date != None, ProductBatch.expiry_date <= today + timedelta(days=3)]
        if role == "outlet_owner" and user_outlet_id:
            expiring_cond.append(ProductBatch.outlet_id == user_outlet_id)
            
        expiring = db.session.scalars(
            select(ProductBatch).where(*expiring_cond)
        ).all()

        outlets_res = []
        for r in outlet_rev:
            val = float(r.rev)
            if role == "outlet_owner" and user_outlet_id:
                val = val * (share_pct / 100.0)
            outlets_res.append({"name": r.name, "revenue": val})

        return jsonify({
            "summary": {
                "b2c_revenue": float(b2c_rev),
                "pos_revenue": float(pos_rev),
                "total_revenue": float(b2c_rev) + float(pos_rev),
                "b2c_orders": b2c_count,
                "pos_sales": pos_count
            },
            "daily": daily_data,
            "top_b2c_items": [{"name": r.name, "qty": r.qty} for r in top_b2c],
            "top_pos_items": [{"name": r.name, "qty": r.qty} for r in top_pos],
            "outlet_revenue": outlets_res,
            "low_stock_count": len(low_stock),
            "expiring_count": len(expiring)
        }), 200

    # --- Stock Audit Log ---
    @app.route("/api/admin/audit-log", methods=["GET"])
    @department_required()
    def admin_audit_log():
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
        logs = db.session.scalars(
            select(StockAuditLog)
            .order_by(StockAuditLog.created_at.desc())
            .limit(per_page).offset((page - 1) * per_page)
        ).all()
        total = db.session.scalar(select(func.count(StockAuditLog.id))) or 0
        return jsonify({"logs": [l.to_dict() for l in logs], "total": total, "page": page}), 200

    # --- Demand Forecast ---
    @app.route("/api/admin/forecast", methods=["GET"])
    @department_required("Finance", "Operations")
    def admin_forecast():
        since = datetime.now(timezone.utc) - timedelta(days=30)
        
        sales_query = db.session.execute(
            select(
                Order.outlet_id, 
                OrderItem.menu_item_id, 
                func.sum(OrderItem.quantity).label('total_sold')
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.created_at >= since,
                Order.order_type == "pos",
                Order.status != "cancelled"
            )
            .group_by(Order.outlet_id, OrderItem.menu_item_id)
        ).fetchall()
        
        sales_map = {(row.outlet_id, row.menu_item_id): row.total_sold or 0 for row in sales_query}
        
        results = []
        stocks = db.session.scalars(select(OutletStock).options(joinedload(OutletStock.outlet), joinedload(OutletStock.menu_item))).unique().all()
        for s in stocks:
            sold = sales_map.get((s.outlet_id, s.menu_item_id), 0)
            daily_rate = round(sold / 30, 2)
            days_left = round(s.current_stock / daily_rate, 1) if daily_rate > 0 else None
            results.append({
                "outlet_id": s.outlet_id,
                "outlet_name": s.outlet.name if s.outlet else None,
                "menu_item_id": s.menu_item_id,
                "menu_item_name": s.menu_item.name if s.menu_item else None,
                "current_stock": s.current_stock,
                "sold_30d": int(sold),
                "daily_rate": daily_rate,
                "days_to_stockout": days_left,
                "restock_urgency": "HIGH" if days_left is not None and days_left < 3
                                   else "MEDIUM" if days_left is not None and days_left < 7
                                   else "LOW"
            })
        results.sort(key=lambda x: (x["days_to_stockout"] is None, x["days_to_stockout"] or 9999))
        return jsonify(results), 200

    # --- Product Batches ---
    @app.route("/api/admin/batches", methods=["GET"])
    @department_required("Operations")
    def admin_get_batches():
        batches = db.session.scalars(
            select(ProductBatch).order_by(ProductBatch.expiry_date.is_(None), ProductBatch.expiry_date.asc())
        ).all()
        return jsonify([b.to_dict() for b in batches]), 200

    # --- QR Code ---
    @app.route("/api/admin/generate-qr", methods=["POST"])
    @department_required("Operations")
    def admin_generate_qr():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        if not data:
            return jsonify({"error": "Bad Request", "message": "Payload required"}), 400
        try:
            # Cryptographically sign the payload for security/authenticity
            sig_payload = {
                "order_id": data.get("order_id"),
                "type": data.get("type"),
                "item": data.get("item"),
                "qty": data.get("qty"),
                "outlet_id": data.get("outlet_id"),
                "destination": data.get("destination"),
                "batch_number": data.get("batch_number"),
                "expiry_date": data.get("expiry_date")
            }
            import hmac
            import hashlib
            serialized = json.dumps(sig_payload, sort_keys=True)
            signature = hmac.new(app.config["SECRET_KEY"].encode(), serialized.encode(), hashlib.sha256).hexdigest()
            data["signature"] = signature

            payload_str = json.dumps(data)
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(payload_str)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            # pyrefly: ignore [unexpected-keyword]
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("utf-8")
            return jsonify({"qr_image": f"data:image/png;base64,{b64}", "payload": data}), 200
        except Exception as e:
            logger.error(f"QR generation failed: {e}")
            return jsonify({"error": "Server Error", "message": "Internal server error"}), 500

    # --- Users list ---
    @app.route("/api/admin/users", methods=["GET"])
    @department_required("HR")
    def admin_get_users():
        users = db.session.scalars(
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
        ).all()
        return jsonify([u.to_dict() for u in users]), 200

    @app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
    @department_required("HR")
    def admin_update_user(user_id):
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404

        if getattr(user, 'is_superadmin', False):
            return jsonify({"error": "Forbidden", "message": "Cannot modify a super-admin."}), 403

        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        if "loyalty_points" in data:
            if not get_jwt().get("is_superadmin"):
                return jsonify({"error": "Forbidden", "message": "Only superadmin can modify loyalty points directly."}), 403
            try:
                new_points = int(data["loyalty_points"])
            except (TypeError, ValueError):
                return jsonify({"error": "Bad Request", "message": "loyalty_points must be an integer"}), 400
            if new_points < 0:
                return jsonify({"error": "Bad Request", "message": "loyalty_points cannot be negative"}), 400
            old_points = user.loyalty_points or 0
            user.loyalty_points = new_points
            # Journal the adjustment so it appears in the user's history.
            delta = new_points - old_points
            if delta != 0:
                db.session.add(WalletTransaction(
                    user_id=user.id,
                    amount=delta,
                    transaction_type="credit" if delta > 0 else "debit",
                    description=f"Admin balance adjustment: {old_points} -> {new_points}"
                ))
            log_admin_action(db.session, get_jwt_identity(), "set_loyalty_points", "User", user.id, f"Loyalty points changed from {old_points} to {user.loyalty_points}")

        if "is_active" in data:
            user.is_active = bool(data["is_active"])
        if "role" in data:
            new_role = data["role"]
            if new_role in ("customer", "staff", "outlet_owner", "admin"):
                if new_role == "admin":
                    admin_count = db.session.scalar(
                        select(func.count(User.id)).where(User.role == "admin")
                    )
                    if admin_count >= 3:
                        return jsonify({"error": "Conflict", "message": "Maximum of 3 admin accounts allowed."}), 409
                    dept = data.get("admin_department") or getattr(user, 'admin_department', None)
                    if not dept or dept not in ["Finance", "Operations", "HR"]:
                        return jsonify({"error": "Bad Request", "message": "admin_department is required for admin role"}), 400
                user.role = new_role
        if "outlet_id" in data:
            oid = data["outlet_id"]
            user.outlet_id = int(oid) if oid is not None else None
            
        if "admin_department" in data:
            dept = data["admin_department"]
            if dept and dept not in ["Finance", "Operations", "HR"]:
                return jsonify({"error": "Bad Request", "message": "admin_department must be Finance, Operations, or HR"}), 400
            user.admin_department = dept if dept else None
        
        password_changed = False
        import re
        if "password" in data and data["password"]:
            new_pwd = data["password"]
            if len(new_pwd) >= 8 and re.search(r'[A-Za-z]', new_pwd) and re.search(r'[0-9]', new_pwd):
                user.set_password(new_pwd, bcrypt)
                user.set_pin(new_pwd, bcrypt)
                user.bump_token_version()
                password_changed = True
            else:
                return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain both letters and numbers."}), 400

        db.session.commit()

        if password_changed and user.role == "admin" and user.email:
            _send_admin_password_changed_email(app, user)

        return jsonify({"message": "User updated successfully", "user": user.to_dict()}), 200

    @app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
    @department_required("HR")
    def admin_delete_user(user_id):
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "Not Found", "message": "User not found"}), 404

        if getattr(user, 'is_superadmin', False):
            return jsonify({"error": "Forbidden", "message": "Cannot delete a super-admin."}), 403

        if user.role == "admin":
            admin_count = db.session.scalar(select(func.count(User.id)).where(User.role == "admin"))
            if admin_count <= 1:
                return jsonify({"error": "Conflict", "message": "Cannot delete the last admin account."}), 409

        user.deleted_at = datetime.now(timezone.utc)
        user.bump_token_version() # invalidate existing sessions
        db.session.commit()
        return jsonify({"message": "User deleted successfully (soft delete)"}), 200

    # ============================================================
    # 4. STAFF / POS ROUTES
    # ============================================================

    @app.route("/api/pos/outlet", methods=["GET"])
    @role_required("staff")
    def pos_get_outlet():
        claims = get_jwt()
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden", "message": "No outlet assigned"}), 403
        outlet = db.session.get(Outlet, int(oid))
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        return jsonify(outlet.to_dict()), 200

    # FIX: Added /api/pos/menu route — returns items assigned to the staff's outlet
    @app.route("/api/pos/menu", methods=["GET"])
    @role_required("staff")
    def pos_get_menu():
        """Returns the outlet stock items (with price & current_stock) for the POS register."""
        claims = get_jwt()
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden", "message": "No outlet assigned"}), 403
        oid = int(oid)
        stocks = db.session.scalars(
            select(OutletStock).where(OutletStock.outlet_id == oid)
        ).all()
        result = []
        for s in stocks:
            if s.menu_item and s.menu_item.is_active:
                result.append({
                    "id": s.menu_item.id,
                    "name": s.menu_item.name,
                    "price": float(s.menu_item.price),
                    "description": s.menu_item.description,
                    "category": s.menu_item.category,
                    "current_stock": s.current_stock,
                    "restock_limit": s.restock_limit,
                    "needs_restock": s.needs_restock
                })
        return jsonify(result), 200

    # FIX: Added /api/pos/sell alias that frontend uses
    @app.route("/api/pos/sell", methods=["POST"])
    @role_required("staff")
    def pos_sell():
        """Alias endpoint for pos_complete_sale — frontend calls /api/pos/sell."""
        return pos_complete_sale()

    @app.route("/api/pos/sale", methods=["POST"])
    @role_required("staff")
    def pos_complete_sale():
        # TRANSACTION BOUNDARY: single transaction — outlet stock decrements,
        # coupon usage and loyalty updates commit together at the end.
        claims = get_jwt()
        staff_id = int(get_jwt_identity())
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden", "message": "No outlet assigned"}), 403
        oid = int(oid)
        data = (sanitize_input(request.get_json(silent=True)) or {})
        items_data = data.get("items", [])
        payment_method = data.get("payment_method", "cash")
        coupon_code = data.get("coupon_code")
        # CRM: optional customer email to link the sale for loyalty tracking
        customer_email = (data.get("customer_email") or "").strip().lower()
        # Loyalty: optional points to redeem (staff toggles this per customer request)
        redeem_points = int(data.get("redeem_loyalty_points") or 0)

        if not items_data:
            return jsonify({"error": "Bad Request", "message": "No items"}), 400

        # Resolve customer (optional)
        customer = None
        if customer_email:
            customer = db.session.scalars(
                select(User).where(User.email == customer_email, User.role == "customer").with_for_update()
            ).first()
            # Silently ignore if not found — sale still proceeds

        total = Decimal("0.00")
        sale_items = []
        for it in items_data:
            mid = int(it.get("menu_item_id"))
            qty = int(it.get("quantity", 1))
            stock = db.session.scalars(
                select(OutletStock).filter_by(outlet_id=oid, menu_item_id=mid)
            ).first()
            if not stock:
                db.session.rollback()
                return jsonify({"error": "Not Found", "message": f"Item {mid} not assigned to outlet"}), 404
            before = stock.current_stock
            result = db.session.execute(
                update(OutletStock).where(OutletStock.outlet_id == oid, OutletStock.menu_item_id == mid, OutletStock.current_stock >= qty)
                .values(current_stock=OutletStock.current_stock - qty)
            )
            if result.rowcount != 1:
                db.session.rollback()
                mi = db.session.get(MenuItem, mid)
                return jsonify({"error": "Conflict", "message": f"Insufficient stock for {mi.name if mi else mid}"}), 409
            db.session.refresh(stock)
            price = stock.menu_item.price
            total += price * qty
            sale_items.append(OrderItem(menu_item_id=mid, price=price, quantity=qty))
            log_stock_change(db.session, outlet_id=oid, menu_item_id=mid,
                             change_qty=-qty, change_type="sale",
                             stock_before=before, stock_after=stock.current_stock,
                             performed_by=staff_id)

        discount_pct = 0
        coupon = None
        if coupon_code:
            coupon = db.session.scalars(
                select(Coupon).where(Coupon.code == coupon_code.upper().strip(), Coupon.is_active == True).with_for_update()
            ).first()
            if coupon:
                if coupon.expiry_date and coupon.expiry_date < datetime.now(timezone.utc).date():
                    return jsonify({"error": "Bad Request", "message": "Coupon has expired"}), 400
                if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
                    return jsonify({"error": "Bad Request", "message": "Coupon usage limit reached"}), 400
                # Check scope
                if coupon.scope == 'customer':
                    return jsonify({"error": "Bad Request", "message": "This coupon is only valid for online delivery orders"}), 400

                # Check min order value
                if coupon.min_order_value and total < Decimal(str(coupon.min_order_value)):
                    return jsonify({"error": "Bad Request", "message": f"Minimum order value of ₹{coupon.min_order_value} required"}), 400

                # Check if first order only
                if coupon.is_first_order_only:
                    if customer:
                        has_orders = db.session.scalars(select(Order).where(Order.customer_id == customer.id)).first()
                        if has_orders:
                            return jsonify({"error": "Bad Request", "message": "This coupon is only valid for a customer's first order"}), 400
                    else:
                        return jsonify({"error": "Bad Request", "message": "This coupon requires a registered customer account"}), 400

                # Check if this customer already used it
                if customer:
                    used = db.session.scalars(select(Order).where(Order.customer_id == customer.id, Order.applied_coupon_code == coupon.code)).first()
                    if used:
                        return jsonify({"error": "Bad Request", "message": "You have already used this coupon. Sorry, try other options."}), 400
                stmt = update(Coupon).where(
                    Coupon.id == coupon.id,
                    or_(Coupon.usage_limit == None, Coupon.usage_count < Coupon.usage_limit)
                ).values(usage_count=Coupon.usage_count + 1)
                res = db.session.execute(stmt)
                if res.rowcount == 0:
                    return jsonify({"error": "Bad Request", "message": "Coupon usage limit reached during checkout"}), 400
                
                # Apply discount
                if coupon.discount_amount and coupon.discount_amount > 0:
                    total = max(Decimal("0.00"), total - Decimal(str(coupon.discount_amount)))
                elif coupon.discount_pct and coupon.discount_pct > 0:
                    discount_pct = min(100, coupon.discount_pct)
                    discount_value = total * (Decimal(str(discount_pct)) / Decimal("100"))
                    if coupon.max_discount_amount and discount_value > Decimal(str(coupon.max_discount_amount)):
                        discount_value = Decimal(str(coupon.max_discount_amount))
                    total = max(Decimal("0.00"), total - discount_value)

        earn_rate, redeem_rate = get_loyalty_settings()
        
        # Loyalty points: redemption
        points_redeemed = 0
        if customer and redeem_points > 0:
            max_redeem_allowed = int(total / Decimal(str(redeem_rate))) if redeem_rate > 0 else 0
            actual_redeem = min(redeem_points, customer.loyalty_points, max_redeem_allowed)
            
            if actual_redeem > 0:
                points_discount = Decimal(str(actual_redeem * redeem_rate))
                total -= points_discount
                total = max(Decimal("0.00"), total)
                # Atomic, guarded decrement (customer row already locked via
                # with_for_update at lookup; this guards against drift).
                from sqlalchemy import update as _sa_update
                redeem_res = db.session.execute(
                    _sa_update(Customer).where(Customer.id == customer.id, Customer.loyalty_points >= actual_redeem)
                    .values(loyalty_points=Customer.loyalty_points - actual_redeem)
                )
                if redeem_res.rowcount != 1:
                    db.session.rollback()
                    return jsonify({"error": "Conflict", "message": "Loyalty points changed during checkout. Please retry."}), 409
                db.session.refresh(customer)
                points_redeemed = actual_redeem

        # Loyalty points: earning
        points_earned = 0
        if customer:
            points_earned = int(total * Decimal(str(earn_rate)))
            customer.loyalty_points = (customer.loyalty_points or 0) + points_earned

        sale = Order(
            order_type='pos',
            outlet_id=oid,
            staff_id=staff_id,
            total_price=total,
            status='delivered',
            payment_method=payment_method,
            items=sale_items,
            customer_id=customer.id if customer else None,
            loyalty_points_earned=points_earned,
            loyalty_points_redeemed=points_redeemed,
            applied_coupon_code=coupon.code if coupon else None
        )
        db.session.add(sale)
        db.session.flush() # ensure we have sale.id
        
        _generate_order_qr(app, sale)
        db.session.commit()

        # Send email alerts if low stock threshold is reached
        _check_and_send_alert(app, oid)

        # Check if any item is now below restock limit
        outlet_obj = db.session.get(Outlet, oid)
        restock_alert = outlet_obj.needs_restock if outlet_obj else False

        return jsonify({
            "message": "Sale recorded",
            "sale": sale.to_dict(),
            "remaining_stock": outlet_obj.current_stock if outlet_obj else 0,
            "restock_alert": restock_alert,
            "loyalty_points_earned": points_earned,
            "loyalty_points_redeemed": points_redeemed,
            "customer_loyalty_balance": customer.loyalty_points if customer else None
        }), 201

    # --- POS: Staff Shift (Clock-In / Clock-Out) ---
    @app.route("/api/pos/shift/clock-in", methods=["POST"])
    @role_required("staff")
    def pos_clock_in():
        """Verify staff email + PIN and open a new shift. Reject if shift already active."""
        claims = get_jwt()
        staff_id = int(get_jwt_identity())
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden", "message": "No outlet assigned"}), 403
        oid = int(oid)

        data = (sanitize_input(request.get_json(silent=True)) or {})
        email = (data.get("email") or "").strip().lower()
        pin = (data.get("pin") or "").strip()

        if not email or not pin:
            return jsonify({"error": "Bad Request", "message": "Email and PIN are required"}), 400

        # Validate PIN belongs to the currently logged-in staff
        staff = db.session.get(User, staff_id)
        if not staff or staff.email.lower() != email:
            return jsonify({"error": "Unauthorized", "message": "Email does not match your account"}), 401

        if not staff.pin_hash:
            return jsonify({"error": "Forbidden", "message": "No PIN set. Contact your administrator."}), 403

        if not staff.check_pin(pin, bcrypt):
            return jsonify({"error": "Unauthorized", "message": "Incorrect PIN"}), 401

        # Check for already active shift
        active = db.session.scalars(
            select(StaffShift).where(
                StaffShift.staff_id == staff_id,
                StaffShift.status == "active"
            )
        ).first()
        if active:
            return jsonify({
                "error": "Conflict",
                "message": "You already have an active shift. Please clock out first.",
                "shift": active.to_dict()
            }), 409

        shift = StaffShift(staff_id=staff_id, outlet_id=oid)
        db.session.add(shift)
        db.session.commit()
        return jsonify({"message": "Clocked in successfully", "shift": shift.to_dict()}), 201

    @app.route("/api/pos/shift/active", methods=["GET"])
    @role_required("staff")
    def pos_get_active_shift():
        """Returns the currently active shift for this staff, or null."""
        staff_id = int(get_jwt_identity())
        shift = db.session.scalars(
            select(StaffShift).where(
                StaffShift.staff_id == staff_id,
                StaffShift.status == "active"
            )
        ).first()
        return jsonify({"shift": shift.to_dict() if shift else None}), 200

    @app.route("/api/pos/sales/history", methods=["GET"])
    @role_required("staff")
    def pos_sales_history():
        """Returns sales for the currently active shift to compute shift totals."""
        staff_id = int(get_jwt_identity())
        shift = db.session.scalars(
            select(StaffShift).where(
                StaffShift.staff_id == staff_id,
                StaffShift.status == "active"
            )
        ).first()
        
        if not shift:
            return jsonify([]), 200

        orders = db.session.scalars(
            select(Order).where(
                Order.staff_id == staff_id,
                Order.created_at >= shift.clock_in_time,
                Order.order_type == "pos",
                Order.status != "cancelled"
            ).order_by(Order.created_at.desc())
        ).unique().all()
        
        # Format for frontend expecting total_amount instead of total_price just to be safe
        result = []
        for o in orders:
            d = o.to_dict()
            d["total_amount"] = d["total_price"]
            result.append(d)
        
        return jsonify(result), 200

    @app.route("/api/pos/shift/clock-out", methods=["POST"])
    @role_required("staff")
    def pos_clock_out():
        """Close the active shift; record cash drawer count and compute discrepancy."""
        staff_id = int(get_jwt_identity())
        claims = get_jwt()
        oid = int(claims.get("outlet_id", 0))

        data = (sanitize_input(request.get_json(silent=True)) or {})
        
        shift = db.session.scalars(
            select(StaffShift).where(
                StaffShift.staff_id == staff_id,
                StaffShift.status == "active"
            )
        ).first()
        if not shift:
            return jsonify({"error": "Not Found", "message": "No active shift found"}), 404

        # Sum cash sales made during this shift
        expected_cash = db.session.scalar(
            select(func.sum(Order.total_price)).where(
                Order.staff_id == staff_id,
                Order.outlet_id == oid,
                Order.payment_method.in_(["cash", "Cash", "CASH"]),
                Order.created_at >= shift.clock_in_time,
                Order.order_type == "pos",
                Order.status != "cancelled"
            )
        ) or Decimal("0.00")

        actual_cash_raw = data.get("actual_cash")
        if actual_cash_raw is None:
            actual_cash = expected_cash  # Auto-clockout assumes expected cash
        else:
            try:
                actual_cash = Decimal(str(actual_cash_raw))
                if actual_cash < 0:
                    raise ValueError()
            except (ValueError, Exception):
                return jsonify({"error": "Bad Request", "message": "actual_cash must be a non-negative number"}), 400

        shift.close_shift(actual_cash=actual_cash, expected_cash=expected_cash)
        if data.get("notes"):
            shift.notes = str(data["notes"])[:500]
        db.session.commit()

        return jsonify({
            "message": "Shift closed successfully",
            "shift": shift.to_dict()
        }), 200

    # --- POS: Customer CRM Lookup ---
    @app.route("/api/pos/customer/lookup", methods=["GET"])
    @role_required("staff")
    def pos_customer_lookup():
        """Look up a customer by email: returns profile, loyalty balance, and top items."""
        email = (request.args.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "Bad Request", "message": "email query param required"}), 400

        customer = db.session.scalars(
            select(User).where(User.email == email, User.role == "customer")
        ).first()
        if not customer:
            return jsonify({"error": "Not Found", "message": "Customer not found"}), 404

        # Get purchase history (top 5 items by frequency from both POS and B2C orders)
        from sqlalchemy import desc
        pos_items = db.session.execute(
            select(OrderItem.menu_item_id, func.sum(OrderItem.quantity).label("qty"))
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.customer_id == customer.id, Order.status != "cancelled")
            .group_by(OrderItem.menu_item_id)
            .order_by(desc("qty"))
            .limit(5)
        ).all()

        top_items = []
        for mid, qty in pos_items:
            mi = db.session.get(MenuItem, mid)
            if mi:
                top_items.append({"name": mi.name, "total_ordered": int(qty), "price": float(mi.price)})

        return jsonify({
            "customer": {
                "id": customer.id,
                "email": customer.email,
                "name": f"{customer.first_name or ''} {customer.last_name or ''}".strip() or customer.email,
                "loyalty_points": customer.loyalty_points or 0,
            },
            "top_items": top_items
        }), 200

    @app.route("/api/pos/my-shifts", methods=["GET"])
    @role_required("staff")
    def pos_my_shifts():
        """Returns the staff member's own shifts and sales summary."""
        staff_id = int(get_jwt_identity())
        shifts = db.session.scalars(
            select(StaffShift)
            .where(StaffShift.staff_id == staff_id)
            .order_by(StaffShift.clock_in_time.desc())
        ).all()
        
        result = []
        for s in shifts:
            s_dict = s.to_dict()
            end_time = s.clock_out_time or datetime.now(timezone.utc)
            sales = db.session.execute(
                select(
                    MenuItem.name.label("menu_item_name"),
                    func.sum(OrderItem.quantity).label("total_qty"),
                    func.sum(OrderItem.price * OrderItem.quantity).label("total_revenue")
                )
                .join(Order, Order.id == OrderItem.order_id)
                .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
                .where(
                    Order.staff_id == s.staff_id,
                    Order.outlet_id == s.outlet_id,
                    Order.created_at >= s.clock_in_time,
                    Order.created_at <= end_time,
                    Order.status != "cancelled"
                )
                .group_by(MenuItem.name)
            ).all()
            
            s_dict["sales_summary"] = [
                {
                    "item_name": row.menu_item_name,
                    "total_qty": int(row.total_qty),
                    "total_revenue": float(row.total_revenue)
                } for row in sales
            ]
            result.append(s_dict)
            
        return jsonify(result), 200

    # --- Admin: Staff Timesheets ---
    @app.route("/api/admin/shifts", methods=["GET"])
    @department_required("HR")
    def admin_get_shifts():
        """Returns all staff shifts for timesheet management with pagination and filtering."""
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        outlet_id = request.args.get("outlet_id")

        query = select(StaffShift)
        
        if outlet_id and str(outlet_id).lower() != "all" and str(outlet_id).strip() != "":
            query = query.where(StaffShift.outlet_id == int(outlet_id))
            
        if start_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                query = query.where(StaffShift.clock_in_time >= sd)
            except ValueError:
                pass
                
        if end_date:
            try:
                ed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                ed = ed + timedelta(days=1)
                query = query.where(StaffShift.clock_in_time < ed)
            except ValueError:
                pass
                
        total = db.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        shifts = db.session.scalars(
            query.order_by(StaffShift.clock_in_time.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        
        result = []
        for s in shifts:
            s_dict = s.to_dict()
            
            # Fetch sales summary for this shift
            end_time = s.clock_out_time or datetime.now(timezone.utc)
            sales = db.session.execute(
                select(
                    MenuItem.name.label("menu_item_name"),
                    func.sum(OrderItem.quantity).label("total_qty"),
                    func.sum(OrderItem.price * OrderItem.quantity).label("total_revenue")
                )
                .join(Order, Order.id == OrderItem.order_id)
                .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
                .where(
                    Order.staff_id == s.staff_id,
                    Order.outlet_id == s.outlet_id,
                    Order.created_at >= s.clock_in_time,
                    Order.created_at <= end_time,
                    Order.status != "cancelled"
                )
                .group_by(MenuItem.name)
            ).all()
            
            s_dict["sales_summary"] = [
                {
                    "item_name": row.menu_item_name,
                    "total_qty": int(row.total_qty),
                    "total_revenue": float(row.total_revenue)
                } for row in sales
            ]
            
            result.append(s_dict)
            
        return jsonify({
            "shifts": result,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 1,
            "current_page": page
        }), 200

    @app.route("/api/admin/shifts/<int:shift_id>", methods=["DELETE"])
    @department_required("HR")
    def admin_delete_shift(shift_id):
        shift = db.session.get(StaffShift, shift_id)
        if not shift:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(shift)
        db.session.commit()
        return jsonify({"message": "Shift record deleted"}), 200

    @app.route("/api/pos/scan-arrival", methods=["POST"])
    @role_required("staff")
    def pos_scan_arrival():
        claims = get_jwt()
        staff_id = int(get_jwt_identity())
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden", "message": "No outlet assigned"}), 403
        oid = int(oid)
        data = (sanitize_input(request.get_json(silent=True)) or {})
        qr_raw = data.get("qr_data", "")
        batch_number = data.get("batch_number")
        expiry_date_str = data.get("expiry_date")

        try:
            payload = json.loads(qr_raw)
        except (json.JSONDecodeError, TypeError):
            return jsonify({"error": "Bad Request", "message": "Invalid QR — not a dispatch label"}), 400

        # Cryptographically verify the QR code signature to prevent forgery
        sig = payload.get("signature")
        if not sig:
            return jsonify({"error": "Bad Request", "message": "Untrusted QR code — missing signature"}), 400
        
        sig_payload = {
            "order_id": payload.get("order_id"),
            "type": payload.get("type"),
            "item": payload.get("item"),
            "qty": payload.get("qty"),
            "outlet_id": payload.get("outlet_id"),
            "destination": payload.get("destination"),
            "batch_number": payload.get("batch_number"),
            "expiry_date": payload.get("expiry_date")
        }
        import hmac
        import hashlib
        serialized = json.dumps(sig_payload, sort_keys=True)
        computed = hmac.new(app.config["SECRET_KEY"].encode(), serialized.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, computed):
            return jsonify({"error": "Bad Request", "message": "Untrusted QR code — invalid signature"}), 400

        item_name = payload.get("item")
        qty = payload.get("qty")
        if not item_name or not qty:
            return jsonify({"error": "Bad Request", "message": "QR missing item or qty"}), 400
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            return jsonify({"error": "Bad Request", "message": "qty must be a number"}), 400

        menu_item = db.session.scalars(
            select(MenuItem).where(MenuItem.name.ilike(item_name))
        ).first()
        if not menu_item:
            return jsonify({"error": "Not Found", "message": f"Item '{item_name}' not in catalog"}), 404

        stock = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=oid, menu_item_id=menu_item.id)
        ).first()
        if not stock:
            return jsonify({"error": "Not Found", "message": f"'{item_name}' not assigned to your outlet"}), 404

        before = stock.current_stock
        stock.current_stock += qty
        log_stock_change(db.session, outlet_id=oid, menu_item_id=menu_item.id,
                         change_qty=qty, change_type="qr_arrival",
                         stock_before=before, stock_after=stock.current_stock,
                         performed_by=staff_id, notes=f"QR scan arrival, batch={batch_number}")

        # Record batch if expiry provided
        expiry_date = None
        if expiry_date_str:
            try:
                from datetime import date as date_cls
                expiry_date = date_cls.fromisoformat(expiry_date_str)
            except ValueError:
                pass

        batch = ProductBatch(outlet_stock_id=stock.id, outlet_id=oid,
                             menu_item_id=menu_item.id, qty=qty,
                             batch_number=batch_number, expiry_date=expiry_date,
                             received_by=staff_id)
        db.session.add(batch)
        db.session.commit()

        return jsonify({
            "message": f"+{qty} units of '{menu_item.name}' added",
            "item": menu_item.name,
            "qty_added": qty,
            "new_stock": stock.current_stock,
            "batch_id": batch.id
        }), 200

    @app.route("/api/pos/batches", methods=["GET"])
    @role_required("staff")
    def pos_get_batches():
        claims = get_jwt()
        oid = claims.get("outlet_id")
        if not oid:
            return jsonify({"error": "Forbidden"}), 403
        batches = db.session.scalars(
            select(ProductBatch).where(ProductBatch.outlet_id == int(oid))
            .order_by(ProductBatch.expiry_date.is_(None), ProductBatch.expiry_date.asc())
        ).all()
        return jsonify([b.to_dict() for b in batches]), 200

    @app.route("/api/pos/disposal", methods=["POST"])
    @role_required("staff")
    def pos_log_disposal():
        claims = get_jwt()
        oid = claims.get("outlet_id")
        staff_id = int(get_jwt_identity())
        if not oid:
            return jsonify({"error": "Forbidden", "message": "Staff not assigned to any outlet"}), 403

        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        qty = data.get("quantity")
        reason = (data.get("reason") or "damaged").strip()

        if not mid or qty is None or int(qty) <= 0:
            return jsonify({"error": "Bad Request", "message": "menu_item_id and positive quantity are required"}), 400

        qty = int(qty)
        stock = db.session.scalars(
            select(OutletStock).filter_by(outlet_id=int(oid), menu_item_id=int(mid))
        ).first()

        if not stock:
            return jsonify({"error": "Not Found", "message": "Item not found in outlet inventory"}), 404

        before = stock.current_stock
        stmt = update(OutletStock).where(
            OutletStock.outlet_id == int(oid),
            OutletStock.menu_item_id == int(mid),
            OutletStock.current_stock >= qty
        ).values(current_stock=OutletStock.current_stock - qty)
        res = db.session.execute(stmt)
        if res.rowcount == 0:
            return jsonify({"error": "Conflict", "message": "Insufficient stock to dispose due to concurrent update."}), 409
            
        db.session.refresh(stock)
        
        log_stock_change(db.session, outlet_id=int(oid), menu_item_id=int(mid),
                         change_qty=-qty, change_type="waste",
                         stock_before=before, stock_after=stock.current_stock,
                         performed_by=staff_id, notes=f"Disposal: {reason}")
        db.session.commit()
        _check_and_send_alert(app, int(oid))
        return jsonify({"message": f"Successfully logged disposal of {qty} units", "new_stock": stock.current_stock}), 200




    # ============================================================
    # 5. OUTLET OWNER ROUTES
    # ============================================================

    @app.route("/api/owner/dashboard", methods=["GET"])
    @role_required("outlet_owner")
    def owner_dashboard():
        uid = int(get_jwt_identity())
        outlets = db.session.scalars(
            select(Outlet).where(Outlet.owner_id == uid)
        ).all()
        return jsonify([o.to_dict() for o in outlets]), 200

    @app.route("/api/owner/outlets", methods=["POST"])
    @role_required("outlet_owner")
    def owner_create_outlet():
        uid = int(get_jwt_identity())
        data = (sanitize_input(request.get_json(silent=True)) or {})
        name = (data.get("name") or "").strip()
        address = (data.get("address") or "").strip()
        if not name or not address:
            return jsonify({"error": "Bad Request", "message": "name and address required"}), 400
        outlet = Outlet(name=name, address=address,
                        latitude=data.get("latitude"), longitude=data.get("longitude"),
                        owner_id=uid)
        db.session.add(outlet)
        db.session.commit()
        return jsonify({"message": "Outlet registered", "outlet": outlet.to_dict()}), 201

    @app.route("/api/owner/outlets/<int:outlet_id>", methods=["PUT"])
    @role_required("outlet_owner")
    def owner_edit_outlet(outlet_id):
        uid = int(get_jwt_identity())
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet or outlet.owner_id != uid:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for f in ("name", "address", "latitude", "longitude"):
            if f in data:
                setattr(outlet, f, data[f])
        db.session.commit()
        return jsonify({"message": "Updated", "outlet": outlet.to_dict()}), 200

    @app.route("/api/owner/outlets/<int:outlet_id>/stock", methods=["GET"])
    @role_required("outlet_owner")
    def owner_get_stock(outlet_id):
        uid = int(get_jwt_identity())
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet or outlet.owner_id != uid:
            return jsonify({"error": "Not Found"}), 404
        return jsonify(outlet.to_dict()), 200

    # ============================================================
    # 6. DAILY REPORT (triggered manually or scheduled)
    # ============================================================

    @app.route("/api/reviews/recent", methods=["GET"])
    def get_recent_reviews():
        # Fetch the top 5-star or 4-star reviews
        reviews = db.session.scalars(
            select(Review)
            .where(Review.is_hidden == False)
            .where(Review.rating >= 4)
            .order_by(Review.created_at.desc())
            .limit(6)
        ).all()
        return jsonify([r.to_dict() for r in reviews]), 200

    @app.route("/api/foods/menu-items/<int:item_id>/reviews", methods=["GET"])
    def get_menu_item_reviews(item_id):
        reviews = db.session.scalars(
            select(Review).where(Review.menu_item_id == item_id, Review.is_hidden == False).order_by(Review.created_at.desc())
        ).all()
        return jsonify([r.to_dict() for r in reviews]), 200

    @app.route("/api/foods/menu-items/<int:item_id>/reviews", methods=["POST"])
    @jwt_required()
    def create_menu_item_review(item_id):
        uid = int(get_jwt_identity())
        user = db.session.get(User, uid)
        if not user or user.role != "customer":
            return jsonify({"error": "Forbidden", "message": "Only customers can submit reviews"}), 403
        
        item = db.session.get(MenuItem, item_id)
        if not item:
            return jsonify({"error": "Not Found", "message": "Menu item not found"}), 404
        
        data = (sanitize_input(request.get_json(silent=True)) or {})
        rating = data.get("rating")
        comment = data.get("comment", "")
        
        if rating is None:
            return jsonify({"error": "Bad Request", "message": "Rating is required"}), 400
        try:
            rating_val = int(rating)
            if not (1 <= rating_val <= 5):
                raise ValueError()
        except ValueError:
            return jsonify({"error": "Bad Request", "message": "Rating must be between 1 and 5"}), 400
        
        existing_review = db.session.scalars(select(Review).where(
            Review.customer_id == uid,
            Review.menu_item_id == item_id,
            
        )).first()
        
        if existing_review:
            return jsonify({"error": "Conflict", "message": "You have already reviewed this item "}), 409

        # Ensure user has actually ordered this item before and it has been delivered
        # Find the most recent order where they bought this
        has_ordered = db.session.scalars(
            select(Order).join(OrderItem).where(
                Order.customer_id == uid,
                OrderItem.menu_item_id == item_id,
                Order.is_received == True
            ).order_by(Order.created_at.desc())
        ).first()

        if not has_ordered:
            return jsonify({"error": "Forbidden", "message": "You can only review items you have ordered and received"}), 403

        review = Review(menu_item_id=item_id, customer_id=uid, rating=rating_val, comment=comment, order_id=has_ordered.id)
        db.session.add(review)
        
        enabled = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == 'enable_loyalty_program')).first()
        if enabled and enabled.setting_value == 'false':
            points = 0
        else:
            review_points_setting = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == 'loyalty_review_points')).first()
            try:
                pct = float(review_points_setting.setting_value) if review_points_setting else 10.0
            except ValueError:
                pct = 10.0
                
            points = int((pct / 100.0) * float(item.price)) if item.price else 0

        if points > 0:
            user.loyalty_points = (user.loyalty_points or 0) + points
            history_entry = WalletTransaction(
                user_id=uid, transaction_type='credit', amount=points,
                description=f"Earned {pct}% points for reviewing {item.name}"
            )
            db.session.add(history_entry)
            
        db.session.commit()
        
        msg = f"Review submitted successfully! You earned {points} loyalty points." if points > 0 else "Review submitted successfully"
        return jsonify({"message": msg, "review": review.to_dict(), "loyalty_points_earned": points, "new_balance": user.loyalty_points}), 201

    @app.route("/api/customer/reviews", methods=["GET"])
    @role_required("customer")
    def get_customer_reviews():
        user_id = int(get_jwt_identity())
        reviews = db.session.scalars(
            select(Review).where(Review.customer_id == user_id).order_by(Review.created_at.desc())
        ).all()
        return jsonify([r.to_dict() for r in reviews]), 200

    @app.route("/api/customer/reviews/<int:review_id>", methods=["DELETE"])
    @role_required("customer")
    def delete_customer_review(review_id):
        user_id = int(get_jwt_identity())
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"error": "Not Found", "message": "Review not found"}), 404
        if review.customer_id != user_id:
            return jsonify({"error": "Forbidden", "message": "You can only delete your own reviews"}), 403
            
        db.session.delete(review)
        db.session.commit()
        return jsonify({"message": "Review deleted successfully"}), 200

    @app.route("/api/admin/reviews", methods=["GET"])
    @role_required("admin", "outlet_owner")
    def admin_get_reviews():
        reviews = db.session.scalars(
            select(Review).order_by(Review.created_at.desc())
        ).all()
        return jsonify([r.to_dict() for r in reviews]), 200

    @app.route("/api/admin/reviews/<int:review_id>", methods=["PATCH", "PUT"])
    @department_required("Operations")
    def admin_update_review(review_id):
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"error": "Not Found", "message": "Review not found"}), 404
        
        data = (sanitize_input(request.get_json(silent=True)) or {})
        if "is_hidden" in data:
            review.is_hidden = bool(data["is_hidden"])
        if "admin_reply" in data:
            review.admin_reply = data["admin_reply"]
            
        db.session.commit()
        return jsonify({"message": "Review updated successfully", "review": review.to_dict()}), 200

    @app.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
    @department_required("Operations")
    def admin_delete_review(review_id):
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"error": "Not Found", "message": "Review not found"}), 404
        db.session.delete(review)
        db.session.commit()
        return jsonify({"message": "Review deleted successfully"}), 200

    @app.route("/api/whatsapp/webhook", methods=["GET", "POST"])
    @limiter.limit("30 per minute")
    def whatsapp_webhook():
        """
        Endpoint for WhatsApp Business API integration.
        GET: Handles Meta's webhook verification challenge.
        POST: Handles incoming messages/orders from WhatsApp.
        """
        if request.method == "GET":
            # Meta verification challenge
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            
            # Verify against token in Meta Dashboard (via env vars)
            if mode == "subscribe" and token == os.getenv("WHATSAPP_VERIFY_TOKEN"):
                return challenge, 200
            else:
                return jsonify({"error": "Forbidden"}), 403
                
        elif request.method == "POST":
            # Receive incoming messages/orders
            
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                return jsonify({"error": "Forbidden", "message": "Missing signature"}), 403
                
            import hmac
            import hashlib
            secret = os.getenv("WHATSAPP_APP_SECRET") or os.getenv("APP_SECRET")
            if not secret:
                return jsonify({"error": "Server Configuration Error", "message": "Missing Meta app secret"}), 500
            expected_signature = 'sha256=' + hmac.new(
                secret.encode('utf-8'),
                request.get_data(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return jsonify({"error": "Forbidden", "message": "Invalid signature"}), 403
                
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"error": "Bad Request", "message": "Empty payload"}), 400
            
            if data.get("object") == "whatsapp_business_account":
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        if "messages" in value:
                            for msg in value["messages"]:
                                if msg.get("type") == "text":
                                    phone_number = msg.get("from")
                                    text = msg["text"]["body"]
                                    
                                    # Save inbound message
                                    from models import WhatsAppMessage
                                    inbound_msg = WhatsAppMessage(phone_number=phone_number, message_body=text, direction='inbound')
                                    db.session.add(inbound_msg)
                                    
                                    # Parse logic
                                    import re
                                    matches = re.findall(r'(\d+)\s+([a-zA-Z\s]+)', text)
                                    
                                    reply_text = ""
                                    if not matches:
                                        reply_text = "Hi! To order, please say the quantity and item name, e.g., '1 burger and 2 pizzas'."
                                    else:
                                        active_items = db.session.execute(db.select(MenuItem).where(MenuItem.is_active == True, MenuItem.deleted_at.is_(None))).scalars().all()
                                        order_items = []
                                        total_price = Decimal("0.00")
                                        not_found = []
                                        
                                        for qty_str, item_name in matches:
                                            qty = int(qty_str)
                                            item_name_lower = item_name.strip().lower()
                                            
                                            # Match item
                                            matched_item = None
                                            # Exact or partial match
                                            for i in active_items:
                                                if i.name.lower() in item_name_lower or item_name_lower in i.name.lower():
                                                    matched_item = i
                                                    break
                                                    
                                            if matched_item:
                                                order_items.append({"item": matched_item, "qty": qty})
                                                total_price += matched_item.price * qty
                                            else:
                                                not_found.append(item_name.strip())
                                                
                                        if order_items and not not_found:
                                            # Find or create user
                                            customer = db.session.scalars(db.select(User).where(User.phone == phone_number)).first()
                                            if not customer:
                                                customer = Customer(phone=phone_number, first_name="WhatsApp", last_name="Customer")
                                                db.session.add(customer)
                                                db.session.flush()
                                                
                                            new_order = Order(
                                                customer_id=customer.id,
                                                order_type="online",
                                                status="pending",
                                                total_price=total_price,
                                                payment_method="COD"
                                            )
                                            db.session.add(new_order)
                                            db.session.flush()
                                            
                                            for oi in order_items:
                                                new_order.items.append(OrderItem(menu_item_id=oi["item"].id, quantity=oi["qty"], price=oi["item"].price))
                                                
                                            items_str = ", ".join([f"{oi['qty']}x {oi['item'].name}" for oi in order_items])
                                            reply_text = f"Order received! Your total is ₹{total_price} for {items_str}. We will prepare it right away."
                                        elif order_items and not_found:
                                            reply_text = f"We found some items, but couldn't find: {', '.join(not_found)}. Please try again with our exact menu names."
                                        else:
                                            reply_text = "Sorry, we couldn't find any of those items on our menu. Please try again."
                                            
                                    outbound_msg = WhatsAppMessage(phone_number=phone_number, message_body=reply_text, direction='outbound')
                                    db.session.add(outbound_msg)
                                    db.session.commit()
                                    
                                    # Send reply
                                    import requests
                                    wa_token = os.getenv("WHATSAPP_API_TOKEN")
                                    phone_number_id = value.get("metadata", {}).get("phone_number_id")
                                    
                                    if wa_token and phone_number_id:
                                        try:
                                            url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                            headers = {
                                                "Authorization": f"Bearer {wa_token}",
                                                "Content-Type": "application/json"
                                            }
                                            payload = {
                                                "messaging_product": "whatsapp",
                                                "to": phone_number,
                                                "text": {"body": reply_text}
                                            }
                                            resp = requests.post(url, headers=headers, json=payload, timeout=5)
                                            if resp.status_code in (200, 201):
                                                outbound_msg.status = 'sent'
                                                db.session.commit()
                                            else:
                                                logger.error(f"WhatsApp API error: {resp.text}")
                                        except Exception as e:
                                            logger.error(f"Error sending WhatsApp reply: {e}")
                                    else:
                                        logger.info(f"MOCK WhatsApp Reply to {phone_number}: {reply_text}")
                                        outbound_msg.status = 'sent'
                                        db.session.commit()
            
            return jsonify({"status": "EVENT_RECEIVED"}), 200


    @app.route("/api/admin/whatsapp", methods=["GET"])
    @role_required("admin")
    def admin_get_whatsapp_messages():
        from models import WhatsAppMessage
        messages = db.session.execute(db.select(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc())).scalars().all()
        return jsonify([m.to_dict() for m in messages]), 200

    # Intentionally public (storefront) but rate-limited
    @app.route("/api/coupons/active", methods=["GET"])
    @limiter.limit("30 per minute")
    def get_active_coupons():
        # Intentionally public but rate-limited
        """Return all active public coupons. Optionally filter by scope query param."""
        from datetime import date
        today = date.today()
        scope = request.args.get("scope")  # 'customer', 'outlet', or None for all
        query = select(Coupon).where(
            Coupon.is_active == True,
            (Coupon.expiry_date.is_(None)) | (Coupon.expiry_date >= today),
            Coupon.applicable_customer_id.is_(None)
        )
        if scope == "customer":
            query = query.where(Coupon.scope.in_(["customer", "both"]))
        elif scope == "outlet":
            query = query.where(Coupon.scope.in_(["outlet", "both"]))
        coupons = db.session.scalars(query).all()
        return jsonify([c.to_dict() for c in coupons]), 200

    @app.route("/api/outlet/coupons", methods=["GET"])
    @role_required("staff", "admin", "outlet_owner")
    def get_outlet_coupons():
        """Return active coupons available for the outlet POS terminal."""
        from datetime import date
        today = date.today()
        coupons = db.session.scalars(
            select(Coupon).where(
                Coupon.is_active == True,
                (Coupon.expiry_date.is_(None)) | (Coupon.expiry_date >= today),
                Coupon.applicable_customer_id.is_(None),
                Coupon.scope.in_(["outlet", "both"])
            )
        ).all()
        return jsonify([c.to_dict() for c in coupons]), 200

    # Intentionally public (storefront) but rate-limited
    @app.route("/api/coupons/<string:code>", methods=["GET"])
    @limiter.limit("30 per minute")
    def get_coupon(code):
        # Intentionally public but rate-limited
        """Validate and return coupon details."""
        coupon = db.session.scalars(
            select(Coupon).where(Coupon.code == code.upper().strip(), Coupon.is_active == True)
        ).first()
        if not coupon:
            return jsonify({"error": "Not Found", "message": "Invalid or inactive coupon code"}), 404
        return jsonify(coupon.to_dict()), 200


    # ============================================================
    # WALLET & CRM ROUTES
    # ============================================================
    
    @app.route("/api/admin/wallet/credit", methods=["POST"])
    @role_required("admin")
    @department_required("finance", "operations")
    def credit_wallet():
        data = sanitize_input(request.get_json(silent=True)) or {}
        user_id = data.get("user_id")
        amount = data.get("amount")
        description = data.get("description", "Wallet Credit")
        if not user_id or not amount:
            return jsonify({"error": "Bad Request", "message": "user_id and amount are required"}), 400
        try:
            amount = int(amount)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            return jsonify({"error": "Bad Request", "message": "Amount must be a positive integer"}), 400
        
        try:
            user = db.session.get(User, user_id, with_for_update=True)
            if not user:
                return jsonify({"error": "Not Found", "message": "User not found"}), 404
            
            user.loyalty_points = (user.loyalty_points or 0) + int(amount)
            tx = WalletTransaction(user_id=user.id, amount=int(amount), transaction_type="credit", description=description)
            db.session.add(tx)
            
            log_admin_action(db.session, get_jwt_identity(), "credit_wallet", "User", user.id, f"Credited {amount} points")
            db.session.commit()
            return jsonify({"message": "Wallet credited successfully", "new_balance": user.loyalty_points}), 200
        except sqlalchemy.exc.SQLAlchemyError:
            db.session.rollback()
            return jsonify({"error": "Server Error"}), 500

    @app.route("/api/admin/wallet/debit", methods=["POST"])
    @role_required("admin")
    @department_required("finance", "operations")
    def debit_wallet():
        data = sanitize_input(request.get_json(silent=True)) or {}
        user_id = data.get("user_id")
        amount = data.get("amount")
        description = data.get("description", "Wallet Debit")
        if not user_id or not amount:
            return jsonify({"error": "Bad Request", "message": "user_id and amount are required"}), 400
        try:
            amount = int(amount)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            return jsonify({"error": "Bad Request", "message": "Amount must be a positive integer"}), 400
        
        try:
            user = db.session.get(User, user_id, with_for_update=True)
            if not user:
                return jsonify({"error": "Not Found", "message": "User not found"}), 404
            
            if (user.loyalty_points or 0) < int(amount):
                return jsonify({"error": "Bad Request", "message": "Insufficient wallet balance"}), 400
                
            user.loyalty_points = (user.loyalty_points or 0) - int(amount)
            tx = WalletTransaction(user_id=user.id, amount=int(amount), transaction_type="debit", description=description)
            db.session.add(tx)
            
            log_admin_action(db.session, get_jwt_identity(), "debit_wallet", "User", user.id, f"Debited {amount} points")
            db.session.commit()
            return jsonify({"message": "Wallet debited successfully", "new_balance": user.loyalty_points}), 200
        except sqlalchemy.exc.SQLAlchemyError:
            db.session.rollback()
            return jsonify({"error": "Server Error"}), 500

    @app.route("/api/admin/wallet/transactions/<int:user_id>", methods=["GET"])
    @role_required("admin")
    def get_wallet_transactions(user_id):
        txs = db.session.scalars(
            select(WalletTransaction).where(WalletTransaction.user_id == user_id).order_by(WalletTransaction.created_at.desc())
        ).all()
        return jsonify([t.to_dict() for t in txs]), 200

    @app.route("/api/admin/customers/segments", methods=["GET"])
    @department_required("Operations", "Finance")
    def get_customer_segments():
        # A simple dynamic segmentation for now
        # High Value: Total spent > 5000
        # Frequent Buyers: Order count > 5
        # Inactive for 30 days
        customers = db.session.scalars(select(User).where(User.role == 'customer').options(joinedload(User.orders))).unique().all()
        
        segments = {
            "all": [],
            "frequent_buyers": [],
            "high_value": [],
            "inactive_30_days": []
        }
        
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        for c in customers:
            c_dict = c.to_dict()
            orders = c.orders
            
            c_dict['order_count'] = len(orders)
            c_dict['total_spent'] = sum(float(o.total_price) for o in orders)
            
            # Find last order date, handle timezone aware/naive
            c_dict['last_order_date'] = max([o.created_at for o in orders]) if orders else None
            if c_dict['last_order_date'] and c_dict['last_order_date'].tzinfo is None:
                c_dict['last_order_date'] = c_dict['last_order_date'].replace(tzinfo=timezone.utc)
            
            segments["all"].append(c_dict)
            
            if c_dict['order_count'] >= 5:
                segments["frequent_buyers"].append(c_dict)
            if c_dict['total_spent'] >= 5000:
                segments["high_value"].append(c_dict)
            
            if c_dict['last_order_date']:
                if c_dict['last_order_date'] < thirty_days_ago:
                    segments["inactive_30_days"].append(c_dict)
            else:
                # If they never ordered
                segments["inactive_30_days"].append(c_dict)
                
        return jsonify(segments), 200

    @app.route("/api/admin/bulk-coupons", methods=["POST"])
    @role_required("admin")
    def bulk_coupons():
        data = sanitize_input(request.get_json(silent=True)) or {}
        min_loyalty_points = data.get("min_loyalty_points")
        coupon_data = data.get("coupon")
        
        if min_loyalty_points is None or not coupon_data:
            return jsonify({"error": "Bad Request", "message": "min_loyalty_points and coupon data are required"}), 400
            
        customers = db.session.scalars(
            select(User).where(User.role == 'customer', Customer.loyalty_points >= int(min_loyalty_points))
        ).all()
        
        # Create a single coupon that can be used multiple times
        from decimal import Decimal
        from datetime import datetime
        coupon = Coupon(
            code=coupon_data.get("code"),
            discount_pct=coupon_data.get("discount_pct", 0),
            discount_amount=Decimal(str(coupon_data.get("discount_amount"))) if coupon_data.get("discount_amount") else None,
            usage_limit=len(customers),
            expiry_date=datetime.strptime(coupon_data["expires_at"], "%Y-%m-%d").date() if coupon_data.get("expires_at") else None,
            is_active=True
        )
        db.session.add(coupon)
        db.session.commit()
        
        # In a real app, we would send an email/SMS broadcast to `customers` here.
        log_admin_action(db.session, get_jwt_identity(), "bulk_coupons", "Coupon", coupon.id, f"Created coupon {coupon.code} for {len(customers)} users with >={min_loyalty_points} points")
        
        return jsonify({"message": f"Coupon {coupon.code} generated and assigned to {len(customers)} customers.", "matched_customers": len(customers)}), 201

    @app.route("/api/admin/broadcast", methods=["POST"])
    @role_required("admin")
    def send_broadcast():
        data = sanitize_input(request.get_json(silent=True)) or {}
        target_segment = data.get("segment")
        message = data.get("message")
        medium = data.get("medium")
        
        if not target_segment or not message or not medium:
            return jsonify({"error": "Bad Request", "message": "segment, message, and medium are required"}), 400
            
        broadcast = BroadcastMessage(target_segment=target_segment, message=message, medium=medium, status="sent")
        db.session.add(broadcast)
        
        log_admin_action(db.session, get_jwt_identity(), "send_broadcast", "BroadcastMessage", None, f"Sent {medium} to {target_segment}")
        db.session.commit()
        
        return jsonify({"message": "Broadcast scheduled/sent successfully", "broadcast": broadcast.to_dict()}), 201

    # ============================================================
    # BANNERS & STORE SETTINGS ROUTES
    # ============================================================

    @app.route("/api/public/banners", methods=["GET"])
    def get_public_banners():
        zone = request.args.get("zone")
        location = request.args.get("location") # Keeping location for backward compatibility
        user_id = request.args.get("user_id", type=int)
        
        now = datetime.now(timezone.utc)
        
        # Base query
        query = select(Banner).where(Banner.is_active == True)
        
        # Time logic
        query = query.where(
            db.or_(
                Banner.start_date == None,
                Banner.start_date <= now
            )
        ).where(
            db.or_(
                Banner.end_date == None,
                Banner.end_date >= now
            )
        )
        
        # Zone/Location logic
        if zone:
            query = query.where(Banner.placement_zone == zone)
        elif location:
            query = query.where(Banner.display_location == location)
            
        # Execute to get initial list
        banners = db.session.scalars(query.order_by(Banner.display_order.asc())).all()
        
        # Audience logic
        filtered_banners = []
        is_new_user = False
        is_inactive = False
        
        if user_id:
            # Check user stats
            user_orders_count = db.session.query(Order).filter(Order.customer_id == user_id).count()
            if user_orders_count == 0:
                is_new_user = True
            else:
                last_order = db.session.query(Order).filter(Order.customer_id == user_id).order_by(Order.created_at.desc()).first()
                if last_order and (now - last_order.created_at.replace(tzinfo=timezone.utc)).days > 30:
                    is_inactive = True
                    
        for banner in banners:
            # Check audience
            if banner.target_audience == 'new_user' and not is_new_user:
                continue
            if banner.target_audience == 'inactive_30_days' and not is_inactive:
                continue
                
            # Check inventory if linked to a product
            if banner.linked_product_id:
                product = db.session.get(MenuItem, banner.linked_product_id)
                if not product or not product.is_active:
                    continue
                if product.global_stock is not None and product.global_stock <= 0:
                    continue
            
            filtered_banners.append(banner)
            
        return jsonify([b.to_dict() for b in filtered_banners]), 200

    @app.route("/api/public/banners/<int:id>/impression", methods=["POST"])
    def track_banner_impression(id):
        banner = db.session.get(Banner, id)
        if banner:
            db.session.execute(update(Banner).where(Banner.id == id).values(impressions=Banner.impressions + 1))
            db.session.commit()
        return jsonify({"success": True}), 200

    @app.route("/api/public/banners/<int:id>/click", methods=["POST"])
    def track_banner_click(id):
        banner = db.session.get(Banner, id)
        if banner:
            db.session.execute(update(Banner).where(Banner.id == id).values(clicks=Banner.clicks + 1))
            db.session.commit()
        return jsonify({"success": True}), 200

    @app.route("/api/admin/upload_image", methods=["POST"])
    @limiter.limit("20 per minute")
    @role_required("admin")
    def admin_upload_image():
        if "file" not in request.files:
            return jsonify({"error": "Bad Request", "message": "No file part in the request"}), 400
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Bad Request", "message": "No file selected for uploading"}), 400
            
        if file:
            filename = secure_filename(file.filename)
            import os
            import uuid
            # Ensure upload directory exists
            upload_dir = os.path.join(app.root_path, "static", "uploads", "images")
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename
            ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            file.save(file_path)
            
            # Return public path
            public_path = f"/static/uploads/images/{unique_filename}"
            return jsonify({"success": True, "path": public_path}), 200

    @app.route("/api/admin/audit_logs", methods=["GET"])
    @role_required("admin")
    def admin_get_audit_logs():
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        logs = db.session.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)).all()
        return jsonify([log.to_dict() for log in logs]), 200

    @app.route("/api/admin/banners", methods=["GET"])
    @role_required("admin")
    def admin_get_banners():
        banners = db.session.scalars(select(Banner).order_by(Banner.display_order.asc())).all()
        return jsonify([b.to_dict() for b in banners]), 200
        
    @app.route("/api/admin/banners", methods=["POST"])
    @limiter.limit("10 per minute")
    @role_required("admin")
    def admin_create_banner():
        data = sanitize_input(request.get_json(silent=True)) or {}
        title = data.get("title")
        image_url = data.get("image_url")
        if not title or not image_url:
            return jsonify({"error": "Bad Request", "message": "title and image_url are required"}), 400
            
        if image_url and image_url.startswith("data:image/"):
            return jsonify({"error": "Bad Request", "message": "Base64 image uploads are not allowed. Please use the file upload component."}), 400
            
        # Parse dates
        start_date = datetime.fromisoformat(data["start_date"].replace('Z', '+00:00')) if data.get("start_date") else None
        end_date = datetime.fromisoformat(data["end_date"].replace('Z', '+00:00')) if data.get("end_date") else None
        countdown_end_time = datetime.fromisoformat(data["countdown_end_time"].replace('Z', '+00:00')) if data.get("countdown_end_time") else None

        banner = Banner(
            title=title,
            description=data.get("description"),
            eyebrow_text=data.get("eyebrow_text"),
            button_text=data.get("button_text"),
            image_url=image_url,
            target_url=data.get("target_url"),
            is_active=data.get("is_active", True),
            display_order=data.get("display_order", 0),
            display_location=data.get("display_location", "home"),
            start_date=start_date,
            end_date=end_date,
            target_audience=data.get("target_audience", "all"),
            placement_zone=data.get("placement_zone", "hero_carousel"),
            display_style=data.get("display_style", "cinematic_21_9"),
            has_countdown=data.get("has_countdown", False),
            countdown_end_time=countdown_end_time,
            linked_product_id=data.get("linked_product_id"),
            linked_coupon_code=data.get("linked_coupon_code")
        )
        db.session.add(banner)
        log_admin_action(db.session, get_jwt_identity(), "create_banner", "Banner", None, f"Created banner {title}")
        db.session.commit()
        return jsonify(banner.to_dict()), 201
        
    @app.route("/api/admin/banners/<int:id>", methods=["PUT"])
    @limiter.limit("10 per minute")
    @role_required("admin")
    def admin_update_banner(id):
        banner = db.session.get(Banner, id)
        if not banner:
            return jsonify({"error": "Not Found", "message": "Banner not found"}), 404
            
        data = sanitize_input(request.get_json(silent=True)) or {}
        if "title" in data: banner.title = data["title"]
        if "description" in data: banner.description = data["description"]
        if "eyebrow_text" in data: banner.eyebrow_text = data["eyebrow_text"]
        if "button_text" in data: banner.button_text = data["button_text"]
        if "image_url" in data: 
            if data["image_url"] and data["image_url"].startswith("data:image/"):
                return jsonify({"error": "Bad Request", "message": "Base64 image uploads are not allowed. Please use the file upload component."}), 400
            banner.image_url = data["image_url"]
        if "target_url" in data: banner.target_url = data["target_url"]
        if "is_active" in data: banner.is_active = data["is_active"]
        if "display_order" in data: banner.display_order = data["display_order"]
        if "display_location" in data: banner.display_location = data["display_location"]
        if "target_audience" in data: banner.target_audience = data["target_audience"]
        if "placement_zone" in data: banner.placement_zone = data["placement_zone"]
        if "display_style" in data: banner.display_style = data["display_style"]
        if "has_countdown" in data: banner.has_countdown = data["has_countdown"]
        if "linked_product_id" in data: banner.linked_product_id = data["linked_product_id"]
        if "linked_coupon_code" in data: banner.linked_coupon_code = data["linked_coupon_code"]

        if "start_date" in data:
            banner.start_date = datetime.fromisoformat(data["start_date"].replace('Z', '+00:00')) if data["start_date"] else None
        if "end_date" in data:
            banner.end_date = datetime.fromisoformat(data["end_date"].replace('Z', '+00:00')) if data["end_date"] else None
        if "countdown_end_time" in data:
            banner.countdown_end_time = datetime.fromisoformat(data["countdown_end_time"].replace('Z', '+00:00')) if data["countdown_end_time"] else None
        
        db.session.commit()
        return jsonify(banner.to_dict()), 200

    @app.route("/api/admin/banners/<int:id>", methods=["DELETE"])
    @role_required("admin")
    def admin_delete_banner(id):
        banner = db.session.get(Banner, id)
        if not banner:
            return jsonify({"error": "Not Found", "message": "Banner not found"}), 404
            
        db.session.delete(banner)
        db.session.commit()
        return jsonify({"message": "Banner deleted"}), 200

    @app.route("/api/public/store-settings", methods=["GET"])
    def get_public_store_settings():
        settings = db.session.scalars(select(StoreSetting)).all()
        # Return as key-value pairs
        return jsonify({s.setting_key: s.setting_value for s in settings}), 200

    @app.route("/api/admin/store-settings", methods=["GET"])
    @role_required("admin")
    def admin_get_store_settings():
        settings = db.session.scalars(select(StoreSetting)).all()
        return jsonify({s.setting_key: s.setting_value for s in settings}), 200

    @app.route("/api/admin/store-settings", methods=["PUT"])
    @role_required("admin")
    def admin_update_store_settings():
        data = sanitize_input(request.get_json(silent=True)) or {}

        # Validate loyalty rate keys BEFORE touching anything (atomic reject).
        for key, (lo, hi) in LOYALTY_SETTING_KEYS.items():
            if key in data:
                try:
                    num = float(data[key])
                except (TypeError, ValueError):
                    return jsonify({"error": "Bad Request",
                                    "message": f"{key} must be a number"}), 400
                if not (lo <= num <= hi):
                    return jsonify({"error": "Bad Request",
                                    "message": f"{key} must be between {lo} and {hi}"}), 400

        for k, v in data.items():
            # Convert python booleans to JSON-compatible lowercase strings
            if isinstance(v, bool):
                val_str = "true" if v else "false"
            else:
                val_str = str(v)
                
            setting = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == k)).first()
            if not setting:
                setting = StoreSetting(setting_key=k, setting_value=val_str)
                db.session.add(setting)
            else:
                setting.setting_value = val_str
        
        log_admin_action(db.session, get_jwt_identity(), "update_store_settings", "StoreSetting", None, "Updated store settings")
        db.session.commit()
        return jsonify({"message": "Settings updated successfully"}), 200

    # ---------------------------------------------------------------------------
    # Payment gateway settings (Razorpay) — Finance/Owner departments only.
    # Secrets stored Fernet-encrypted; responses never include them.
    # ---------------------------------------------------------------------------
    @app.route("/api/admin/settings/payment", methods=["GET"])
    @role_required("admin")
    @department_required("Finance", "Owner")
    def admin_get_payment_settings():
        has_secret = _setting_value("razorpay_key_secret") is not None
        last4 = _setting_value("razorpay_key_last4")
        env_configured = bool(os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET"))
        source = "database" if has_secret else ("environment" if env_configured else "none")
        return jsonify({
            "razorpay_key_id": _setting_value("razorpay_key_id", ""),
            "razorpay_key_masked": ("••••••••" + last4) if (has_secret and last4) else "",
            "razorpay_key_secret_set": has_secret,
            "razorpay_webhook_secret_set": _setting_value("razorpay_webhook_secret") is not None,
            "razorpay_mode": _setting_value("razorpay_mode", "test"),
            "razorpay_enabled": (_setting_value("razorpay_enabled", "false") == "true"),
            "encryption_configured": bool(os.getenv("PAYMENT_ENCRYPTION_KEY")),
            "source": source,
        }), 200

    @app.route("/api/admin/settings/payment", methods=["POST"])
    @role_required("admin")
    @department_required("Finance", "Owner")
    def admin_update_payment_settings():
        data = sanitize_input(request.get_json(silent=True)) or {}

        mode = str(data.get("razorpay_mode") or _setting_value("razorpay_mode", "test")).lower()
        if mode not in ("test", "live"):
            return jsonify({"error": "Bad Request", "message": "razorpay_mode must be 'test' or 'live'"}), 400

        enabled_raw = data.get("razorpay_enabled")
        if enabled_raw is None:
            enabled_str = _setting_value("razorpay_enabled", "false") or "false"
        else:
            enabled_str = "true" if (enabled_raw is True or str(enabled_raw).lower() in ("true", "1", "yes")) else "false"

        key_id = str(data.get("razorpay_key_id") or _setting_value("razorpay_key_id") or "").strip()

        new_secret = (data.get("razorpay_key_secret") or "").strip()
        new_webhook = (data.get("razorpay_webhook_secret") or "").strip()

        if key_id and not key_id.startswith(("rzp_test_", "rzp_live_")):
            return jsonify({"error": "Bad Request", "message": "Razorpay Key ID must start with rzp_test_ or rzp_live_"}), 400
        if key_id and key_id.startswith("rzp_live_") != (mode == "live"):
            return jsonify({"error": "Bad Request",
                            "message": f"Key ID prefix does not match {mode} mode (expected {'rzp_live_' if mode == 'live' else 'rzp_test_'}...)"}), 400

        if (new_secret or new_webhook) and _fernet() is None:
            return jsonify({"error": "Bad Request",
                            "message": "Server is missing PAYMENT_ENCRYPTION_KEY - cannot store secrets securely."}), 400

        if key_id:
            _set_setting("razorpay_key_id", key_id)
        _set_setting("razorpay_mode", mode)
        _set_setting("razorpay_enabled", enabled_str)
        secret_changed = False
        if new_secret:
            _set_setting("razorpay_key_secret", _encrypt_secret(new_secret))
            _set_setting("razorpay_key_last4", new_secret[-4:])
            secret_changed = True
        if new_webhook:
            _set_setting("razorpay_webhook_secret", _encrypt_secret(new_webhook))

        log_admin_action(db.session, get_jwt_identity(), "update_payment_settings",
                         "StoreSetting", None,
                         f"Razorpay settings saved (mode={mode}, enabled={enabled_str}, secret_changed={secret_changed})")
        db.session.commit()
        clear_razorpay_cache()

        last4 = _setting_value("razorpay_key_last4")
        return jsonify({
            "message": "Payment settings saved successfully",
            "razorpay_key_id": _setting_value("razorpay_key_id", ""),
            "razorpay_key_masked": ("••••••••" + last4) if (_setting_value("razorpay_key_secret") and last4) else "",
            "razorpay_mode": mode,
            "razorpay_enabled": enabled_str == "true",
            "secret_changed": secret_changed,
        }), 200

    @app.route("/api/payments/razorpay/order", methods=["POST"])
    @jwt_required()
    def create_razorpay_order():
        """Create a Razorpay order for one of this customer's pending orders."""
        uid = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        order_id = data.get("order_id")
        if not order_id:
            return jsonify({"error": "Bad Request", "message": "order_id is required"}), 400

        order = db.session.get(Order, int(order_id))
        if not order or order.customer_id != uid:
            return jsonify({"error": "Not Found", "message": "Order not found"}), 404
        if order.status != "pending":
            return jsonify({"error": "Bad Request", "message": "Order is not awaiting payment"}), 400

        try:
            creds = get_razorpay_credentials(force_refresh=True)
        except RuntimeError as e:
            return jsonify({"error": "Service Unavailable", "message": str(e)}), 503
        if not creds:
            return jsonify({"error": "Service Unavailable",
                            "message": "Payment gateway is not configured yet. Please contact support."}), 503
        if not creds.get("enabled"):
            return jsonify({"error": "Bad Request",
                            "message": "Online payments are currently disabled."}), 400

        import requests as _requests
        try:
            rp_resp = _requests.post(
                "https://api.razorpay.com/v1/orders",
                auth=(creds["key_id"], creds["key_secret"]),
                json={
                    "amount": int((order.total_price or 0) * 100),  # paise
                    "currency": "INR",
                    "receipt": f"order_{order.id}",
                    "notes": {"order_id": str(order.id)},
                },
                timeout=15,
            )
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            return jsonify({"error": "Service Unavailable",
                            "message": "Payment gateway unreachable"}), 502

        if rp_resp.status_code not in (200, 201):
            logger.error(f"Razorpay API error {rp_resp.status_code}: {rp_resp.text[:300]}")
            return jsonify({"error": "Bad Gateway",
                            "message": "Payment gateway rejected the request"}), 502

        rp_order = rp_resp.json()
        rp_order_id = rp_order.get("id")
        order.razorpay_order_id = rp_order_id
        db.session.add(PaymentTransaction(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=rp_order_id,
            amount=order.total_price,
            currency=rp_order.get("currency", "INR"),
            status="created",
            event="order_created",
            source="checkout",
        ))
        db.session.commit()
        return jsonify({
            "razorpay_order_id": rp_order.get("id"),
            "amount": rp_order.get("amount"),
            "currency": rp_order.get("currency"),
            "key_id": creds["key_id"],   # public key - safe for checkout.js
            "mode": creds["mode"],
        }), 201

    @app.route("/api/payments/razorpay/verify", methods=["POST"])
    @jwt_required()
    @limiter.limit("20 per minute")
    def verify_razorpay_payment():
        """Verify the checkout.js signature (HMAC of order_id|payment_id with the key secret)
        and mark the order as paid. Idempotent."""
        uid = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        try:
            order_id = int(data.get("order_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "Bad Request", "message": "order_id is required"}), 400

        rp_order_id = (data.get("razorpay_order_id") or "").strip()
        rp_payment_id = (data.get("razorpay_payment_id") or "").strip()
        rp_signature = (data.get("razorpay_signature") or "").strip()
        if not rp_order_id or not rp_payment_id or not rp_signature:
            return jsonify({"error": "Bad Request",
                            "message": "razorpay_order_id, razorpay_payment_id and razorpay_signature are required"}), 400

        order = db.session.get(Order, order_id)
        if not order or order.customer_id != uid:
            return jsonify({"error": "Not Found", "message": "Order not found"}), 404

        # Idempotency: a webhook may have beaten the client to it.
        if order.payment_status == "paid":
            return jsonify({"message": "Order already marked as paid", "already_paid": True,
                            "order": order.to_dict()}), 200

        if order.razorpay_order_id and order.razorpay_order_id != rp_order_id:
            logger.warning(f"[PAYMENT] Order #{order.id}: razorpay_order_id mismatch "
                           f"(expected {order.razorpay_order_id}, got {rp_order_id})")
            return jsonify({"error": "Bad Request", "message": "Payment order mismatch"}), 400

        try:
            creds = get_razorpay_credentials(force_refresh=True)
        except RuntimeError as e:
            return jsonify({"error": "Service Unavailable", "message": str(e)}), 503
        if not creds:
            return jsonify({"error": "Service Unavailable",
                            "message": "Payment gateway is not configured yet. Please contact support."}), 503

        expected_sig = hmac.new(
            creds["key_secret"].encode(),
            f"{rp_order_id}|{rp_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        signature_valid = hmac.compare_digest(expected_sig, rp_signature)

        db.session.add(PaymentTransaction(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=rp_order_id,
            provider_payment_id=rp_payment_id,
            amount=order.total_price,
            currency="INR",
            status="captured" if signature_valid else "failed",
            event="checkout_verify",
            signature_valid=signature_valid,
            source="checkout",
        ))

        if not signature_valid:
            db.session.commit()
            logger.warning(f"[PAYMENT] Order #{order.id}: INVALID checkout signature for payment {rp_payment_id}")
            return jsonify({"error": "Bad Request", "message": "Payment signature verification failed"}), 400

        order.payment_status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        order.razorpay_payment_id = rp_payment_id
        order.razorpay_order_id = order.razorpay_order_id or rp_order_id
        db.session.commit()
        logger.info(f"[PAYMENT] Order #{order.id} marked PAID via checkout verify ({rp_payment_id})")
        return jsonify({"message": "Payment verified", "already_paid": False, "order": order.to_dict()}), 200

    @app.route("/api/payments/razorpay/webhook", methods=["POST"])
    @limiter.limit("120 per minute")
    def razorpay_webhook():
        """Razorpay server-to-server events. Public route — authenticated by the
        X-Razorpay-Signature HMAC header instead of a JWT."""
        raw_body = request.get_data(cache=False)
        signature = request.headers.get("X-Razorpay-Signature", "")
        try:
            creds = get_razorpay_credentials()
        except RuntimeError as e:
            return jsonify({"error": "Service Unavailable", "message": str(e)}), 503
        if not creds:
            return jsonify({"error": "Service Unavailable",
                            "message": "Payment gateway is not configured"}), 503
        webhook_secret = creds.get("webhook_secret")
        if not webhook_secret:
            logger.error("[PAYMENT] Webhook received but no webhook secret is configured")
            return jsonify({"error": "Service Unavailable",
                            "message": "Webhook secret is not configured"}), 503

        if not verify_razorpay_webhook_signature(raw_body, signature, webhook_secret):
            logger.warning("[PAYMENT] Webhook rejected: invalid X-Razorpay-Signature")
            return jsonify({"error": "Bad Request", "message": "Invalid signature"}), 400

        # Parse from the raw bytes we already read (get_data with cache=False
        # consumes the stream, so request.get_json() would return None).
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except (ValueError, TypeError):
            logger.warning("[PAYMENT] Webhook rejected: body is not valid JSON")
            return jsonify({"error": "Bad Request", "message": "Invalid JSON body"}), 400
        event = payload.get("event", "")
        entities = payload.get("payload") or {}
        payment_entity = (entities.get("payment") or {}).get("entity") or {}
        order_entity = (entities.get("order") or {}).get("entity") or {}

        rp_payment_id = payment_entity.get("id")
        rp_order_id = payment_entity.get("order_id") or order_entity.get("id")
        notes = payment_entity.get("notes") or {}
        local_order_id = notes.get("order_id")

        order = None
        if local_order_id:
            try:
                order = db.session.get(Order, int(local_order_id))
            except (TypeError, ValueError):
                order = None
        if not order and rp_order_id:
            order = db.session.scalars(
                select(Order).where(Order.razorpay_order_id == rp_order_id)
            ).first()

        amount_paise = payment_entity.get("amount")
        amount = (Decimal(str(amount_paise)) / 100) if amount_paise is not None else None

        txn_status_map = {
            "payment.captured": "captured",
            "payment.failed": "failed",
            "refund.processed": "refunded",
            "order.paid": "captured",
        }
        db.session.add(PaymentTransaction(
            order_id=order.id if order else None,
            provider="razorpay",
            provider_order_id=rp_order_id,
            provider_payment_id=rp_payment_id,
            amount=amount if amount is not None else Decimal("0.00"),
            currency=payment_entity.get("currency", "INR"),
            status=txn_status_map.get(event, "unknown"),
            event=event or "unknown",
            signature_valid=True,
            source="webhook",
            raw_payload=json.dumps(payload)[:4000],
        ))

        if order:
            if event in ("payment.captured", "order.paid"):
                # Idempotent: safe even if checkout verify already ran.
                if order.payment_status != "paid":
                    order.payment_status = "paid"
                    order.paid_at = datetime.now(timezone.utc)
                    order.razorpay_order_id = order.razorpay_order_id or rp_order_id
                    order.razorpay_payment_id = rp_payment_id
                    logger.info(f"[PAYMENT] Order #{order.id} marked PAID via webhook ({rp_payment_id})")
            elif event == "payment.failed":
                if order.payment_status != "paid":
                    order.payment_status = "failed"
                    logger.info(f"[PAYMENT] Order #{order.id} payment FAILED via webhook")
            elif event in ("refund.processed", "refund.created"):
                order.payment_status = "refunded"
                order.refund_status = "processed"

        db.session.commit()
        return jsonify({"status": "ok"}), 200

    # ---------------------------------------------------------------------------
    # Market Purchases API
    # ---------------------------------------------------------------------------
    @app.route('/api/admin/market-purchases', methods=['GET'])
    @role_required("admin")
    def admin_get_market_purchases():
        try:
            purchases = MarketPurchase.query.order_by(MarketPurchase.purchased_at.desc()).all()
            return jsonify([p.to_dict() for p in purchases]), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/market-purchases', methods=['POST'])
    @role_required("admin")
    def admin_add_market_purchase():
        data = request.json
        try:
            current_user = get_jwt_identity()
            admin_id_val = current_user.get('id') if isinstance(current_user, dict) else current_user
            
            purchase = MarketPurchase(
                ingredient_name=data.get('ingredient_name'),
                cost=data.get('cost'),
                quantity=data.get('quantity'),
                unit=data.get('unit'),
                category=data.get('category'),
                expiration_date=data.get('expiration_date'),
                receipt_url=data.get('receipt_url'),
                notes=data.get('notes'),
                admin_id=admin_id_val
            )
            db.session.add(purchase)
            db.session.commit()
            return jsonify(purchase.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400


    @app.route('/api/admin/market-purchases/<int:id>', methods=['PUT'])
    @jwt_required()
    @role_required('admin')
    def admin_edit_market_purchase(id):
        data = request.json
        try:
            purchase = MarketPurchase.query.get(id)
            if not purchase:
                return jsonify({'error': 'Purchase not found'}), 404
                
            purchase.ingredient_name = data.get('ingredient_name', purchase.ingredient_name)
            purchase.cost = data.get('cost', purchase.cost)
            purchase.quantity = data.get('quantity', purchase.quantity)
            purchase.unit = data.get('unit', purchase.unit)
            purchase.category = data.get('category', purchase.category)
            purchase.expiration_date = data.get('expiration_date', purchase.expiration_date)
            purchase.receipt_url = data.get('receipt_url', purchase.receipt_url)
            purchase.notes = data.get('notes', purchase.notes)
            
            db.session.commit()
            return jsonify(purchase.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    @app.route('/api/admin/market-purchases/<int:id>', methods=['DELETE'])
    @jwt_required()
    @role_required('admin')
    def admin_delete_market_purchase(id):
        try:
            purchase = MarketPurchase.query.get(id)
            if not purchase:
                return jsonify({'error': 'Purchase not found'}), 404
            
            db.session.delete(purchase)
            db.session.commit()
            return jsonify({'message': 'Purchase deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    return app


# ============================================================
# PRIVATE HELPERS
# ============================================================

def _seed_admin(app):
    with app.app_context():
        if os.environ.get("FLASK_ENV") == "production":
            logger.info("Skipping _seed_admin in production mode")
            return

        # 1. Seed Admin
        admin = db.session.scalars(select(User).where(User.email == "admin")).first()
        
        seed_pwd = os.environ.get("ADMIN_SEED_PASSWORD")
        if not seed_pwd:
            seed_pwd = "admin123"
            
        if not admin:
            admin = Admin(email="admin", first_name="System", last_name="Admin")
            admin.is_superadmin = True
            admin.set_password(seed_pwd, bcrypt)
            admin.is_first_login = True
            db.session.add(admin)
            db.session.commit()
            logger.info(f"Admin account seeded: admin / {seed_pwd} (first login reset forced)")
        else:
            if admin.check_password("admin", bcrypt) and not admin.is_first_login:
                admin.is_first_login = True
                db.session.commit()
                logger.info("Forced is_first_login = True on admin because default password is still active")

        # 1.5. Seed Coupons
        if db.session.scalar(select(func.count(Coupon.id))) == 0:
            coupons_to_seed = [
                Coupon(code="WELCOME10", discount_pct=10),
                Coupon(code="FESTIVE20", discount_pct=20),
                Coupon(code="HALFOFF", discount_pct=50)
            ]
            for c in coupons_to_seed:
                db.session.add(c)
            db.session.commit()
            logger.info("Default discount coupons seeded")

        # 2. Seed Outlets if none exist
        if db.session.scalar(select(func.count(Outlet.id))) == 0:
            outlets_to_seed = [
                Outlet(name="Outlet 1: Connaught Place Corner", address="Connaught Place, New Delhi", latitude=28.6304, longitude=77.2177),
                Outlet(name="Outlet 2: Vashi Express Supply", address="Vashi, Navi Mumbai", latitude=19.0748, longitude=73.0011),
                Outlet(name="Outlet 3: Indiranagar Stall", address="Indiranagar, Bengaluru", latitude=12.9719, longitude=77.6412),
            ]
            for o in outlets_to_seed:
                db.session.add(o)
            db.session.commit()
            logger.info("Default outlets seeded")

        # 3. Seed MenuItems if Kobbari Karam is missing
        if not db.session.scalars(select(MenuItem).where(MenuItem.name == "Kobbari Karam 250g")).first():
            menu_items = [
                # Spice Powders
                MenuItem(name="Kobbari Karam 250g", price=Decimal("200.00"), business_type="home_foods", category="Spice Powders", description="Homemade Kobbari Karam — rich coconut spice powder made from fresh coconut and red chillies.", image_url="https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=200&q=80"),
                MenuItem(name="Pappula Podi 250g", price=Decimal("159.00"), business_type="home_foods", category="Spice Powders", description="Homemade Pappula Podi — traditional lentil spice powder for rice and idli.", image_url="https://images.unsplash.com/photo-1615485290382-441e4d049cb5?w=200&q=80"),
                MenuItem(name="Karvepaku Karram 250g", price=Decimal("159.00"), business_type="home_foods", category="Spice Powders", description="Karivepaku Karam — authentic curry leaf spice powder with a pungent aroma.", image_url="https://images.unsplash.com/photo-1599909613253-f3b3a5f7b33f?w=200&q=80"),
                MenuItem(name="Nuvvula Podi 250g", price=Decimal("169.00"), business_type="home_foods", category="Spice Powders", description="Nuvvula Podi (Roasted Sesame Powder) — nutrient-rich sesame spice blend.", image_url="https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?w=200&q=80"),
                MenuItem(name="Munagaku Podi 250g", price=Decimal("160.00"), business_type="home_foods", category="Spice Powders", description="Suggula's Kitchen Munagaku Podi — drumstick leaves powder packed with nutrients.", image_url="https://images.unsplash.com/photo-1583394293214-0b3f8ed6e0ab?w=200&q=80"),
                MenuItem(name="Kandi Podi 250g", price=Decimal("179.00"), business_type="home_foods", category="Spice Powders", description="సాంప్రదాయ రుచికి అసలైన కందిపప్పు పొడి — traditional toor dal spice powder.", image_url="https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=200&q=80"),
                MenuItem(name="Curry Leaves Herbal Powder 250g", price=Decimal("289.00"), business_type="home_foods", category="Spice Powders", description="Curry Leaves Herbal Powder — natural health supplement and flavour enhancer.", image_url="https://images.unsplash.com/photo-1591189824344-d7e6c2440e4a?w=200&q=80"),
                MenuItem(name="Andhra Nallakaram Podi 250g", price=Decimal("140.00"), business_type="home_foods", category="Spice Powders", description="Experience the authentic Andhra Nallakaram podi — fiery and aromatic.", image_url="https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=200&q=80"),
                MenuItem(name="Andhra Koora Karam 250g", price=Decimal("120.00"), business_type="home_foods", category="Spice Powders", description="అమ్మ చేతి కూర కారం — the special Andhra vegetable spice blend.", image_url="https://images.unsplash.com/photo-1615485290382-441e4d049cb5?w=200&q=80"),
                MenuItem(name="Pallila Karam 250g", price=Decimal("180.00"), business_type="home_foods", category="Spice Powders", description="నాన్నేమైన వేరుసేనగలు, సం... — peanut-based Andhra spice powder.", image_url="https://images.unsplash.com/photo-1599909613253-f3b3a5f7b33f?w=200&q=80"),

                # Pickles
                MenuItem(name="Pandu Mirchi Gongura 250g", price=Decimal("199.00"), business_type="home_foods", category="Pickles", description="Traditional Andhra Pandu Mirchi Gongura pickle — tangy red chilli sorrel blend.", image_url="https://images.unsplash.com/photo-1567982047351-76b6f93e38ee?w=200&q=80"),
                MenuItem(name="Pandumirchi Tamota Pickle 250g", price=Decimal("199.00"), business_type="home_foods", category="Pickles", description="Traditional Andhra Pandumirchi Tomato pickle — a classic tangy combination.", image_url="https://images.unsplash.com/photo-1567982047351-76b6f93e38ee?w=200&q=80"),
                MenuItem(name="Allam Pandumirchi Pickle 250g", price=Decimal("199.00"), business_type="home_foods", category="Pickles", description="Traditional Andhra Allam Chilli pickle — spicy ginger and chilli blend.", image_url="https://images.unsplash.com/photo-1589916836867-5208c1f74e23?w=200&q=80"),
                MenuItem(name="Pandu Mirchi Pickle 250g", price=Decimal("229.00"), business_type="home_foods", category="Pickles", description="పండిన ఎర్ర మిర్చితో, నాన్చు... — slow-fermented red chilli pickle.", image_url="https://images.unsplash.com/photo-1567982047351-76b6f93e38ee?w=200&q=80"),
                MenuItem(name="Kothimera Pickle 250g", price=Decimal("189.00"), business_type="home_foods", category="Pickles", description="తాజా కొత్తిమేర సువాస... — fresh coriander leaves pickle.", image_url="https://images.unsplash.com/photo-1589916836867-5208c1f74e23?w=200&q=80"),
                MenuItem(name="Classic Avakaya 250g", price=Decimal("299.00"), business_type="home_foods", category="Pickles", description="అసలైన ఆంధ్ర ఆవకాయ... — the king of Andhra pickles, raw mango.", image_url="https://images.unsplash.com/photo-1567982047351-76b6f93e38ee?w=200&q=80"),

                # Snacks & Savories
                MenuItem(name="Challa Chakralu 250g", price=Decimal("120.00"), business_type="home_foods", category="Snacks & Savories", description="Traditional Challa Chakralu — crispy butter rice rings, a timeless Andhra snack.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
                MenuItem(name="Rice Vadiyalu 250g", price=Decimal("120.00"), business_type="home_foods", category="Snacks & Savories", description="సాంప్రదాయ ఆంధ్ర రుచితో... — traditional sun-dried rice crackers.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
                MenuItem(name="Chekkarala Vadiyalu 250g", price=Decimal("150.00"), business_type="home_foods", category="Snacks & Savories", description="అమ్మ చేతి రుచితో, సాంప్రదా... — handmade chekkarala vadiyalu.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
                MenuItem(name="Sagubiyam Vadiyalu 250g", price=Decimal("120.00"), business_type="home_foods", category="Snacks & Savories", description="ఎండలో సహజంగా ఆరబెట్టి... — sago sun-dried crackers.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
                MenuItem(name="Bellam Gavvalu 250g", price=Decimal("195.00"), business_type="home_foods", category="Snacks & Savories", description="Fresh & Crunchy Bellam Gavvalu — sweet jaggery shells, a traditional treat.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
                MenuItem(name="Karram Gavvalu 250g", price=Decimal("159.00"), business_type="home_foods", category="Snacks & Savories", description="Karam Gavvalu — spicy shell-shaped crispy snack from Andhra.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),

                # Sweets & Treats
                MenuItem(name="Palli Patti 250g", price=Decimal("169.00"), business_type="home_foods", category="Sweets & Treats", description="Peanut Chikki / Palli Patti — crunchy peanut brittle with jaggery.", image_url="https://images.unsplash.com/photo-1551024601-bec78aea704b?w=200&q=80"),
                MenuItem(name="Pala Penilu 250g", price=Decimal("249.00"), business_type="home_foods", category="Sweets & Treats", description="Experience the authentic taste of Pala Penilu — milk-based traditional sweet.", image_url="https://images.unsplash.com/photo-1551024601-bec78aea704b?w=200&q=80"),
                MenuItem(name="Royal Honey Cashew 250g", price=Decimal("319.00"), business_type="home_foods", category="Sweets & Treats", description="Every bite is rich, crunchy, and coated in pure honey — premium cashew delight.", image_url="https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=200&q=80"),
                MenuItem(name="Gondhu Laddu 250g", price=Decimal("319.00"), business_type="home_foods", category="Sweets & Treats", description="ఈ గొంధు (కృఫ్ల్) నెయ్యిలో... — traditional Gondhu Laddu with pure ghee.", image_url="https://images.unsplash.com/photo-1551024601-bec78aea704b?w=200&q=80"),
                MenuItem(name="Suggula's Kitchen Sweet 250g", price=Decimal("369.00"), business_type="home_foods", category="Sweets & Treats", description="Suggula's Kitchen Sweet & Special — traditional handmade sweet boxes.", image_url="https://images.unsplash.com/photo-1551024601-bec78aea704b?w=200&q=80"),

                # Mixes & Instant
                MenuItem(name="Instant Rasam Mix 250g", price=Decimal("140.00"), business_type="home_foods", category="Mixes & Instant", description="Instant Rasam Mix — Bring the warmth of homemade rasam to your table instantly.", image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?w=200&q=80"),
                MenuItem(name="Karram Charu Mix 250g", price=Decimal("165.00"), business_type="home_foods", category="Mixes & Instant", description="Karam Charu Mix (Instant Rasam Powder) — spicy pepper rasam mix.", image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?w=200&q=80"),
                MenuItem(name="Chinthapandu Pulihora Mix 250g", price=Decimal("165.00"), business_type="home_foods", category="Mixes & Instant", description="Chinthapandu Pulihora Mix — tamarind rice spice blend for perfect pulihora.", image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?w=200&q=80"),
                MenuItem(name="Instant Gravy Mix 250g", price=Decimal("149.00"), business_type="home_foods", category="Mixes & Instant", description="రెస్తారెంట్ స్టైల్ కర్రీ... — restaurant-style instant curry gravy mix.", image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?w=200&q=80"),

                # Special Products
                MenuItem(name="Suggula's Kitchen Traditional 250g", price=Decimal("349.00"), business_type="home_foods", category="Special Products", description="Suggula's Kitchen Traditional — handcrafted special recipe from grandma's kitchen.", image_url="https://images.unsplash.com/photo-1606914501449-5a96b6ce24ca?w=200&q=80"),
                MenuItem(name="Ashadam Special Neeyi Annam Podi 250g", price=Decimal("449.00"), business_type="home_foods", category="Special Products", description="Neeyi Annam Podi Ashadam Special — pure ghee rice powder for festive occasions.", image_url="https://images.unsplash.com/photo-1606914501449-5a96b6ce24ca?w=200&q=80"),
                MenuItem(name="Saddu Baby Bottu 5g", price=Decimal("99.00"), business_type="home_foods", category="Special Products", description="Saddu Baby Bottu — traditional herbal bottu for infants, a heritage product.", image_url="https://images.unsplash.com/photo-1606914501449-5a96b6ce24ca?w=200&q=80"),
                MenuItem(name="Herbal Sunnipindi 250g", price=Decimal("299.00"), business_type="home_foods", category="Special Products", description="Sunni Pindi Herbal Bath Powder — natural herbal body cleansing powder.", image_url="https://images.unsplash.com/photo-1606914501449-5a96b6ce24ca?w=200&q=80"),
                MenuItem(name="Snack Supply Samosa 250g", price=Decimal("20.00"), business_type="snack_supply", category="Snacks & Savories", description="Crisp pastry filled with spiced potatoes and peas — B2B2C snack supply.", image_url="https://images.unsplash.com/photo-1601000157769-35ac8d01c9d0?w=200&q=80"),
            ]
            for m in menu_items:
                db.session.add(m)
            db.session.commit()
            logger.info("Menu catalog items seeded successfully")

        # 4. Seed Staff & Customer Users if missing
        staff_user = db.session.scalars(select(User).where(User.email == "staff@brand.com")).first()
        if not staff_user:
            staff_user = Staff(email="staff@brand.com", outlet_id=1, first_name="Alex", last_name="Staff", phone="9848022338")
            staff_user.set_password("staff", bcrypt)
            db.session.add(staff_user)
            db.session.commit()
            logger.info("Default staff seeded: staff@brand.com / staff")

        cust_user = db.session.scalars(select(User).where(User.email == "customer@gmail.com")).first()
        if not cust_user:
            cust_user = Customer(email="customer@gmail.com", first_name="Sarah", last_name="Customer", phone="9999999999")
            cust_user.set_password("customer", bcrypt)
            cust_user.referral_code = "SARAHCUST1"
            cust_user.loyalty_points = 1500
            db.session.add(cust_user)
            db.session.commit()
            
            # Generate dummy loyalty history
            tx1 = WalletTransaction(user_id=cust_user.id, amount=1000, transaction_type="credit", description="Signup Bonus")
            tx2 = WalletTransaction(user_id=cust_user.id, amount=500, transaction_type="credit", description="Referral Bonus for inviting John")
            db.session.add(tx1)
            db.session.add(tx2)
            db.session.commit()
            logger.info("Default customer seeded: customer@gmail.com / customer")

        owner_user = db.session.scalars(select(User).where(User.email == "owner@brand.com")).first()
        if not owner_user:
            owner_user = User(email="owner@brand.com", role="outlet_owner", first_name="Rajesh", last_name="Owner", phone="9848022339")
            owner_user.set_password("owner", bcrypt)
            db.session.add(owner_user)
            db.session.commit()
            logger.info("Default owner seeded: owner@brand.com / owner")

        # Associate existing outlets to this owner if they aren't owned yet
        if owner_user:
            o1 = db.session.get(Outlet, 1)
            o2 = db.session.get(Outlet, 2)
            if o1 and o1.owner_id is None:
                o1.owner_id = owner_user.id
            if o2 and o2.owner_id is None:
                o2.owner_id = owner_user.id
            db.session.commit()

        # 5. Seed stock items to first available outlet if empty
        if db.session.scalar(select(func.count(OutletStock.id))) == 0:
            first_outlet = db.session.scalars(select(Outlet)).first()
            if first_outlet:
                samosa = db.session.scalars(select(MenuItem).where(MenuItem.name == "Snack Supply Samosa 250g")).first()
                chakralu = db.session.scalars(select(MenuItem).where(MenuItem.name == "Challa Chakralu 250g")).first()
                if samosa and chakralu:
                    db.session.add(OutletStock(outlet_id=first_outlet.id, menu_item_id=samosa.id, current_stock=20, restock_limit=10))
                    db.session.add(OutletStock(outlet_id=first_outlet.id, menu_item_id=chakralu.id, current_stock=15, restock_limit=10))
                    db.session.commit()
                    logger.info(f"Default outlet stocks seeded for {first_outlet.name}")



def _check_and_send_alert(app, outlet_id):
    """Send low-stock email alert if configured."""
    try:
        admin_email = app.config.get("ADMIN_EMAIL")
        if not admin_email or not app.config.get("MAIL_USERNAME"):
            return
        low = db.session.scalars(
            select(OutletStock).where(
                OutletStock.outlet_id == outlet_id,
                OutletStock.current_stock <= OutletStock.restock_limit
            )
        ).all()
        if low:
            outlet = db.session.get(Outlet, outlet_id)
            lines = [f"  - {s.menu_item.name}: {s.current_stock}/{s.restock_limit}" for s in low]
            body = f"⚠️ Low Stock Alert — {outlet.name if outlet else outlet_id}\n\n" + "\n".join(lines)
            msg = Message(subject=f"Low Stock Alert: {outlet.name if outlet else outlet_id}",
                          recipients=[admin_email], body=body)
            mail.send(msg)
    except Exception as e:
        logger.warning(f"Alert email failed: {e}")


def get_frontend_url(user_role):
    import os
    urls = [u.strip() for u in os.environ.get('FRONTEND_URL', 'http://localhost:5173,http://localhost:5174').split(',')]
    # Enforce standard ports if found
    if user_role == 'customer':
        for u in urls:
            if '5174' in u: return u
    elif user_role in ['admin', 'staff', 'outlet_owner', 'kitchen']:
        for u in urls:
            if '5173' in u: return u
    return urls[0]

def _get_email_html_wrapper(title, content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f7f9fc;
                color: #2D3748;
                margin: 0;
                padding: 40px 20px;
            }}
            .card {{
                max-width: 600px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 16px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
                overflow: hidden;
                border: 1px solid #E2E8F0;
            }}
            .header {{
                background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
                padding: 30px;
                text-align: center;
                color: white;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
            .body {{
                padding: 40px 30px;
                line-height: 1.6;
                font-size: 15px;
            }}
            .footer {{
                background: #f1f5f9;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #64748b;
                border-top: 1px solid #E2E8F0;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #f97316;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                margin-top: 20px;
            }}
            .table-container {{
                margin-top: 20px;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                overflow: hidden;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th {{
                background-color: #f8fafc;
                text-align: left;
                padding: 10px 15px;
                font-size: 13px;
                color: #64748b;
                border-bottom: 1px solid #E2E8F0;
            }}
            td {{
                padding: 12px 15px;
                font-size: 14px;
                border-bottom: 1px solid #F1F5F9;
            }}
            .total-row {{
                font-weight: bold;
                background-color: #f8fafc;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1>🍱 Suggula\'s Kitchen</h1>
            </div>
            <div class="body">
                {content}
            </div>
            <div class="footer">
                &copy; {datetime.now().year} Suggula\'s Kitchen ERP. All rights reserved.<br>
                This is an automated operational email.
            </div>
        </div>
    </body>
    </html>
    """



def _send_verification_email(app, user):
    try:
        serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        token = serializer.dumps(user.email, salt="email-verify-salt")
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Verify your Email - Suggula\'s Kitchen 🧡", sender=sender, recipients=[user.email])
        
        # Determine base URL for frontend
        frontend_url = get_frontend_url(user.role)
        verify_link = f"{frontend_url}/verify-email?token={token}"
        
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Verify your email address, {user.first_name or 'Friend'}! 👋</h2>
        <p>Thank you for signing up to <strong>Suggula\'s Kitchen</strong>! To activate your account and place your first order, please verify your email address.</p>
        <p>Click the button below to verify your email:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_link}" class="btn" style="background: #10b981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">Verify My Email</a>
        </div>
        <p>If you did not sign up for this account, please ignore this email.</p>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Email Verification", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send verification email: {e}")


def _send_welcome_email(app, user):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Welcome to Suggula\'s Kitchen! 🧡", sender=sender, recipients=[user.email])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Welcome to the Family, {user.first_name or 'Friend'}! 👋</h2>
        <p>We are absolutely thrilled to welcome you to <strong>Suggula\'s Kitchen</strong>! Thank you for signing up and joining our community of food lovers.</p>
        <p>Our kitchen is always busy preparing the warmest, freshest, and most delicious home-cooked meals, ready to be delivered straight to your doorstep.</p>
        <p>Here are your account details:</p>
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
            <strong>Email/Username:</strong> {user.email}<br>
            <strong>Role:</strong> B2C Customer
        </div>
        <p>Go ahead and browse our kitchen catalog to place your very first order!</p>
        <div style="text-align: center;">
            <a href="{get_frontend_url(user.role)}" class="btn">Explore the Shop</a>
        </div>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Welcome", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send welcome email: {e}")


def _send_order_placed_email(app, order, customer):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject=f"We've Received Your Order! #{order.id} 🍕", sender=sender, recipients=[customer.email])
        
        rows = ""
        for it in order.items:
            rows += f"""
            <tr>
                <td>{it.menu_item.name}</td>
                <td>{it.quantity}</td>
                <td>₹{it.price * it.quantity:.2f}</td>
            </tr>
            """
        
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Thank you for your order! 🧡</h2>
        <p>Hi {customer.first_name or 'there'}, we've received your order and our chefs are already prepping it with love.</p>
        <p>Here is your order summary:</p>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Price</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                    <tr class="total-row">
                        <td colspan="2">Total Amount</td>
                        <td>₹{order.total_price:.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <h3 style="margin-top: 25px; color: #1e293b;">Delivery Information</h3>
        <p style="background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 14px;">
            <strong>Deliver To:</strong> {order.delivery_address or 'Not specified'}<br>
            <strong>Payment Method:</strong> {order.payment_method}
        </p>
        <p>We'll notify you as soon as your delicious box is dispatched and on its way!</p>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Order Confirmed", content)
        
        import threading
        def send_async():
            with app.app_context():
                try:
                    mail.send(msg)
                except Exception as ex:
                    logger.warning(f"Failed to send order placed email async: {ex}")
        threading.Thread(target=send_async).start()
    except Exception as e:
        logger.warning(f"Failed to setup order placed email: {e}")


def _send_order_shipped_email(app, order, customer, tracking_code):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Your Suggula\'s Kitchen Box is on its way! 📦", sender=sender, recipients=[customer.email])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Your food is on the way! 🛵</h2>
        <p>Hi {customer.first_name or 'there'}, your order #{order.id} has been packed, handed over to our delivery partner, and is officially en route!</p>
        <p>Get ready for a warm, delightful feast.</p>
        
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 25px; text-align: center;">
            <div style="font-size: 13px; color: #64748b; margin-bottom: 5px;">SHIPPING TRACKING CODE</div>
            <div style="font-size: 22px; font-weight: 800; color: #f97316; letter-spacing: 1px; margin: 5px 0;">{tracking_code}</div>
            <div style="font-size: 12px; color: #94a3b8; margin-bottom: 15px;">Use this code to track delivery with our logistics partner.</div>
            
            <div style="border-top: 1px dashed #cbd5e1; margin: 15px 0;"></div>
            
            <div style="font-size: 13px; color: #64748b; margin-bottom: 5px;">DELIVERY CONFIRMATION PIN</div>
            <div style="font-size: 26px; font-weight: 900; color: #22c55e; letter-spacing: 3px; margin: 5px 0;">{order.delivery_confirmation_code}</div>
            <div style="font-size: 12px; color: #94a3b8;">Enter this PIN in your order history to confirm receipt!</div>
        </div>
        
        <p>If you have any questions or need to make last-minute changes, please contact our support team immediately.</p>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Order Shipped", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send order shipped email: {e}")


def _send_admin_created_email(app, admin):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Welcome to Suggula\'s Kitchen Admin Team! 🛡️", sender=sender, recipients=[admin.email])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Welcome to the Admin Team, {admin.first_name or 'Admin'}! 🛡️</h2>
        <p>Your administrator profile has been successfully set up on the Suggula\'s Kitchen ERP platform.</p>
        <p>Please use the temporary credentials provided to you securely by the system administrator to log in.</p>
        
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px; line-height: 1.8;">
            <strong>Role:</strong> Administrator<br>
            <strong>Username/Email:</strong> {admin.email}<br>
        </div>
        
        <div style="text-align: center;">
            <a href="{get_frontend_url(admin.role)}" class="btn">Launch Admin Dashboard</a>
        </div>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Admin Onboarding", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send admin onboarding email: {e}")


def _send_admin_password_changed_email(app, admin):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Suggula\'s Kitchen Admin Password Update 🔐", sender=sender, recipients=[admin.email])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Password Successfully Updated 🔐</h2>
        <p>Hi {admin.first_name or 'Admin'}, the password for your Suggula\'s Kitchen administrator account has been changed.</p>
        
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px; line-height: 1.8;">
            <strong>Username/Email:</strong> {admin.email}<br>
        </div>
        
        <p>If you did not request this change, please contact support immediately.</p>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Password Changed", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send password changed email: {e}")


def _send_staff_created_email(app, staff, outlet):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject="Welcome to Suggula\'s Kitchen POS Team! 🏪", sender=sender, recipients=[staff.email])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Welcome to the Team, {staff.first_name or 'Partner'}! 🏪</h2>
        <p>Your cashier profile has been successfully set up on the Suggula\'s Kitchen ERP platform.</p>
        <p>Please use the temporary credentials provided to you securely by the system administrator to log in.</p>
        
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px; line-height: 1.8;">
            <strong>Assigned Outlet:</strong> {outlet.name if outlet else 'Not Assigned'}<br>
            <strong>Username/Email:</strong> {staff.email}<br>
        </div>
        
        <p style="font-size: 13px; color: #64748b; font-style: italic;">* Note: You will be prompted to set a secure password of your own upon your very first login.</p>
        
        <div style="text-align: center;">
            <a href="{get_frontend_url(staff.role)}" class="btn">Launch Cashier POS Terminal</a>
        </div>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Staff Onboarding", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send staff onboarding email: {e}")


def _send_daily_digest_email(app, report, email_address):
    try:
        sender = app.config.get("MAIL_DEFAULT_SENDER") or "noreply@fooderp.local"
        msg = Message(subject=f"Daily Revenue Digest — {report.get('date')} 📈", sender=sender, recipients=[email_address])
        content = f"""
        <h2 style="color: #f97316; margin-top: 0;">Operational Daily Report</h2>
        <p>Here is the business performance summary for today, <strong>{report.get('date')}</strong>:</p>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>🛒 B2C Orders Placed</td>
                        <td>{report.get('b2c_orders')} orders</td>
                    </tr>
                    <tr>
                        <td>🥡 B2C Sales Revenue</td>
                        <td>₹{report.get('b2c_revenue'):.2f}</td>
                    </tr>
                    <tr>
                        <td>🏪 POS Outlet Revenue</td>
                        <td>₹{report.get('pos_revenue'):.2f}</td>
                    </tr>
                    <tr class="total-row">
                        <td>📈 Combined Total Revenue</td>
                        <td>₹{report.get('total_revenue'):.2f}</td>
                    </tr>
                    <tr>
                        <td>⚠️ Low Stock Warnings</td>
                        <td style="color: { '#ef4444' if report.get('low_stock_items', 0) > 0 else '#10b981' }; font-weight: 600;">
                            {report.get('low_stock_items')} items need attention
                        </td>
                    </tr>
                    <tr>
                        <td>🕒 Expiring Batches</td>
                        <td style="color: { '#f59e0b' if report.get('expiring_batches', 0) > 0 else '#10b981' }; font-weight: 600;">
                            {report.get('expiring_batches')} batches expiring soon
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <p style="margin-top: 25px;">Please check the central admin console for specific inventory and auditing reports.</p>
        """
        msg.body = 'Please view this email in an HTML-compatible client.\n\nThanks, Suggula\'s Kitchen'
        msg.html = _get_email_html_wrapper("Daily Digest", content)
        mail.send(msg)
    except Exception as e:
        logger.warning(f"Failed to send daily digest email: {e}")


def _generate_daily_report():
    """Generate a daily report dict and optionally save to file."""
    try:
        from datetime import date as date_cls
        today = date_cls.today()
        since = datetime.now(timezone.utc) - timedelta(hours=24)

        b2c_rev = db.session.scalar(
            select(func.sum(Order.total_price)).where(
                Order.created_at >= since, Order.status != "cancelled"
            )
        ) or 0
        pos_rev = db.session.scalar(
            select(func.sum(Order.total_price)).where(
                Order.created_at >= since,
                Order.order_type == "pos",
                Order.status != "cancelled"
            )
        ) or 0 or 0
        b2c_cnt = db.session.scalar(
            select(func.count(Order.id)).where(Order.created_at >= since, Order.status != "cancelled")
        ) or 0
        low_stock = db.session.scalars(
            select(OutletStock).where(OutletStock.current_stock <= OutletStock.restock_limit)
        ).all()
        expiring = db.session.scalars(
            select(ProductBatch).where(
                ProductBatch.expiry_date != None,
                ProductBatch.expiry_date <= today + timedelta(days=3)
            )
        ).all()

        report = {
            "date": today.isoformat(),
            "b2c_revenue": float(b2c_rev),
            "pos_revenue": float(pos_rev),
            "total_revenue": float(b2c_rev) + float(pos_rev),
            "b2c_orders": b2c_cnt,
            "low_stock_items": len(low_stock),
            "expiring_batches": len(expiring)
        }

        # Save to file
        os.makedirs("reports", exist_ok=True)
        with open(f"reports/daily_{today.isoformat()}.json", "w") as f:
            json.dump(report, f, indent=2)

        # Send daily digest email to admin
        admin_email = app.config.get("ADMIN_EMAIL")
        if admin_email:
            _send_daily_digest_email(app, report, admin_email)
        
        # Send daily digest email to all outlet owners
        owners = db.session.scalars(select(User).where(User.role == "outlet_owner")).all()
        for owner in owners:
            if owner.email:
                _send_daily_digest_email(app, report, owner.email)

        logger.info(f"Daily report generated: {report}")
        return report
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {"error": str(e)}

def _purge_old_ticket_attachments(app):
    """Purge attachment FILES from closed/resolved tickets older than
    TICKET_RETENTION_DAYS (default 90) and null out their references.
    Module-level so it can be tested/imported independently of the scheduler."""
    retention_days = int(os.getenv("TICKET_RETENTION_DAYS", "90"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with app.app_context():
        old_tickets = db.session.scalars(
            select(SupportTicket).where(
                SupportTicket.attachment_filename.is_not(None),
                SupportTicket.status.in_(["Resolved", "Closed"]),
                SupportTicket.updated_at < cutoff,
            )
        ).all()
        if not old_tickets:
            return 0
        removed = 0
        for t in old_tickets:
            p = os.path.join(TICKETS_UPLOAD_FOLDER, t.attachment_filename)
            if os.path.exists(p):
                try:
                    os.remove(p)
                    removed += 1
                except Exception as e:
                    logger.error(f"Ticket cleanup: failed to remove {p}: {e}")
            t.attachment_filename = None
            t.attachment_url = None
        db.session.commit()
        logger.info(
            f"Ticket cleanup: purged attachments from {len(old_tickets)} "
            f"closed tickets ({removed} files removed, retention={retention_days}d)"
        )
        return len(old_tickets)


def _start_scheduler(app):
    import atexit
    
    # Try to use a file lock so only one Gunicorn worker starts the scheduler
    try:
        import fcntl
        import os
        import tempfile
        lock_file = os.path.join(tempfile.gettempdir(), 'food_scheduler.lock')
        lock_fp = open(lock_file, 'w')
        try:
            fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            logger.info("Scheduler is already running in another process. Skipping start in this worker.")
            return
            
        def unlock():
            try:
                fcntl.flock(lock_fp, fcntl.LOCK_UN)
                lock_fp.close()
            except Exception:
                pass
        atexit.register(unlock)
        
    except ImportError:
        # On Windows (no fcntl) during local dev, just proceed without lock
        logger.info("fcntl not available (likely Windows), starting scheduler without cross-process lock.")

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    def run_report():
        with app.app_context():
            _generate_daily_report()

    def cleanup_ticket_attachments():
        try:
            _purge_old_ticket_attachments(app)
        except Exception as e:
            logger.error(f"Ticket attachment cleanup failed: {e}")

    scheduler.add_job(run_report, "cron", hour=22, minute=0, id="daily_report")
    scheduler.add_job(cleanup_ticket_attachments, "cron", hour=3, minute=15, id="ticket_attachment_cleanup")
    scheduler.start()
    logger.info("Scheduler started — daily report at 22:00 IST, ticket cleanup at 03:15 IST")

if __name__ == "__main__":
    app = create_app()
    debug_mode = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)


