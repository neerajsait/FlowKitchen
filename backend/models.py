from datetime import datetime, timezone
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Numeric, Boolean, Float, Date, UniqueConstraint, CheckConstraint, Index, Enum
from sqlalchemy.orm import relationship
from constants import (
    OrderStatus, PaymentStatus, RefundStatus, TransactionStatus, 
    StaffShiftStatus, ProductionBatchStatus, BroadcastMessageStatus, 
    SupportTicketStatus, StockRequestStatus
)

db = SQLAlchemy()

# ===========================================================================
# IMPORTANT: REDIS ARCHITECTURE NOTE
# ===========================================================================
# The application uses Redis for JWT blocklisting and real-time state.
# While a fallback `MemoryRedis` exists in `redis_client.py` for local 
# development (using `memory://`), it is STRICTLY a single-process constraint.
# In a multi-process environment (like Gunicorn/uWSGI) or multi-node setup,
# `MemoryRedis` will fail to share state between workers, leading to critical
# bugs such as security token leaks and desynchronized caches.
# For production deployments, a real Redis server (e.g., redis-server) is REQUIRED.
# ===========================================================================


# ---------------------------------------------------------------------------
# Outlet — physical snack supply station
# ---------------------------------------------------------------------------
class Outlet(db.Model):
    __tablename__ = 'outlets'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL', use_alter=True, name='fk_outlet_owner_id'), nullable=True)
    revenue_share_percentage = Column(Numeric(5, 2), nullable=True, default=0.00)
    revenue_cutoff_date = Column(DateTime, nullable=True, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship('User', foreign_keys=[owner_id], backref='owned_outlets')

    def __init__(self, name, address, latitude=None, longitude=None, owner_id=None):
        self.name = name
        self.address = address
        self.latitude = latitude
        self.longitude = longitude
        self.owner_id = owner_id

    @property
    def current_stock(self):
        return sum(s.current_stock for s in self.stocks)

    @property
    def needs_restock(self):
        return any(s.needs_restock for s in self.stocks)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "current_stock": self.current_stock,
            "needs_restock": self.needs_restock,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "owner_id": self.owner_id,
            "revenue_share_percentage": float(self.revenue_share_percentage) if self.revenue_share_percentage is not None else 0.0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "items": [s.to_dict() for s in self.stocks]
        }


# ---------------------------------------------------------------------------
# User — admin / customer / staff / outlet_owner
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    role = Column(String(20), nullable=False, default='customer')
    
    __table_args__ = (
        CheckConstraint('loyalty_points >= 0', name='chk_user_loyalty_points'),
    )

    __mapper_args__ = {
        'polymorphic_on': role,
        'polymorphic_identity': 'user'
    }

    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expiry = Column(DateTime, nullable=True)
    is_first_login = Column(Boolean, default=False, nullable=False)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # --- New Security & Admin Fields ---
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    emergency_contact = Column(String(100), nullable=True)
    is_superadmin = Column(Boolean, default=False, nullable=False)
    admin_department = Column(String(50), nullable=True)

    # --- STI Subclass Fields ---
    rfid_tag = Column(String(50), unique=True, nullable=True)
    loyalty_points = Column(Integer, default=0, nullable=False)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='SET NULL'), nullable=True)
    pin_hash = Column(String(100), nullable=True)
    staff_code = Column(String(10), unique=True, nullable=True)
    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    outlet = relationship('Outlet', foreign_keys=[outlet_id], backref='staff')

    def __init__(self, email, role='customer', first_name=None, last_name=None, phone=None, address=None):
        self.email = email
        self.role = role
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.address = address
        self.is_first_login = False

    def set_password(self, password: str, bcrypt):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        self.bump_token_version()

    def bump_token_version(self):
        if getattr(self, 'token_version', None) is None:
            self.token_version = 0
        self.token_version += 1
        try:
            from redis_client import get_redis
            rc = get_redis()
            if rc and getattr(self, 'id', None):
                rc.setex(f"user_tv:{self.id}", 2 * 86400, self.token_version)
        except Exception:
            pass

    def check_password(self, password: str, bcrypt) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_pin(self, pin: str, bcrypt):
        self.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')
        self.bump_token_version()

    def check_pin(self, pin: str, bcrypt) -> bool:
        if not self.pin_hash:
            return False
        return bcrypt.check_password_hash(self.pin_hash, pin)

    def to_dict(self):
        d = {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "address": self.address,
            "is_active": self.is_active,
            "is_first_login": self.is_first_login,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_banned": self.is_banned,
            "ban_reason": self.ban_reason,
            "is_email_verified": self.is_email_verified,
            "emergency_contact": self.emergency_contact,
            "is_superadmin": self.is_superadmin,
            "admin_department": self.admin_department,
            "referral_code": self.referral_code,
            "referred_by_id": self.referred_by_id,
            "deleted_at": self.deleted_at.isoformat() if getattr(self, "deleted_at", None) else None
        }
        if hasattr(self, 'outlet_id'):
            d["outlet_id"] = self.outlet_id
            d["outlet_name"] = self.outlet.name if getattr(self, 'outlet', None) else None
        if hasattr(self, 'pin_hash'):
            d["has_pin"] = self.pin_hash is not None
        if hasattr(self, 'staff_code'):
            d["staff_code"] = self.staff_code
        if hasattr(self, 'loyalty_points'):
            d["loyalty_points"] = self.loyalty_points or 0
        return d


class Customer(User):
    __mapper_args__ = { 'polymorphic_identity': 'customer' }
    
    def __init__(self, email, first_name=None, last_name=None, phone=None, address=None):
        super().__init__(email=email, role='customer', first_name=first_name, last_name=last_name, phone=phone, address=address)
        self.loyalty_points = 0


class Staff(User):
    __mapper_args__ = { 'polymorphic_identity': 'staff' }
    
    def __init__(self, email, first_name=None, last_name=None, phone=None, outlet_id=None, address=None):
        super().__init__(email=email, role='staff', first_name=first_name, last_name=last_name, phone=phone, address=address)
        self.outlet_id = outlet_id
    
    def set_pin(self, pin: str, bcrypt):
        self.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')

    def check_pin(self, pin: str, bcrypt) -> bool:
        if not self.pin_hash:
            return False
        return bcrypt.check_password_hash(self.pin_hash, pin)


class Admin(User):
    __mapper_args__ = { 'polymorphic_identity': 'admin' }
    def __init__(self, email, first_name=None, last_name=None, phone=None, address=None):
        super().__init__(email=email, role='admin', first_name=first_name, last_name=last_name, phone=phone, address=address)


class OutletOwner(User):
    __mapper_args__ = { 'polymorphic_identity': 'outlet_owner' }
    def __init__(self, email, first_name=None, last_name=None, phone=None, outlet_id=None, address=None):
        super().__init__(email=email, role='outlet_owner', first_name=first_name, last_name=last_name, phone=phone, address=address)
        self.outlet_id = outlet_id

class KitchenStaff(User):
    __mapper_args__ = { 'polymorphic_identity': 'kitchen' }
    def __init__(self, email, first_name=None, last_name=None, phone=None, outlet_id=None, address=None):
        super().__init__(email=email, role='kitchen', first_name=first_name, last_name=last_name, phone=phone, address=address)
        self.outlet_id = outlet_id  # Can be None if central kitchen
        
    def set_pin(self, pin: str, bcrypt):
        self.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')

    def check_pin(self, pin: str, bcrypt) -> bool:
        if not self.pin_hash:
            return False
        return bcrypt.check_password_hash(self.pin_hash, pin)



# ---------------------------------------------------------------------------
# MenuItem — global food catalog
# ---------------------------------------------------------------------------
class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    __table_args__ = (
        CheckConstraint('price >= 0', name='chk_menu_item_price'),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=True)  # auto-generated 8-digit product code
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    business_type = Column(String(20), nullable=False)  # 'home_foods', 'snack_supply', 'both'
    category = Column(String(50), nullable=True)
    image_url = Column(String(255), nullable=True)
    global_stock = Column(Integer, nullable=True)  # None = unlimited
    is_active = Column(Boolean, default=True)
    is_veg = Column(Boolean, default=True)
    is_gluten_free = Column(Boolean, default=False)
    spice_level = Column(String(20), default='medium')
    tag = Column(String(50), nullable=True)
    admin_rating = Column(Float, nullable=True)
    is_best_seller = Column(Boolean, default=False)
    is_popular = Column(Boolean, default=False)
    ingredients = Column(Text, nullable=True)
    nutritional_info = Column(Text, nullable=True)
    dietary_guidelines = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    def __init__(self, name, price, business_type, code=None, description=None, category=None, image_url=None, global_stock=None, is_active=True, is_veg=True, is_gluten_free=False, spice_level='medium', tag=None, admin_rating=None, is_popular=False, ingredients=None, nutritional_info=None, dietary_guidelines=None):
        self.code = code
        self.name = name
        self.price = price
        self.business_type = business_type
        self.description = description
        self.category = category
        self.image_url = image_url
        self.global_stock = global_stock
        self.is_active = is_active
        self.is_veg = is_veg
        self.is_gluten_free = is_gluten_free
        self.spice_level = spice_level
        self.tag = tag
        self.admin_rating = admin_rating
        self.is_popular = is_popular
        self.ingredients = ingredients
        self.nutritional_info = nutritional_info
        self.dietary_guidelines = dietary_guidelines

    @property
    def visible_reviews(self):
        if getattr(self, 'reviews', None):
            return [r for r in self.reviews if not r.is_hidden]
        return []

    @property
    def average_rating(self):
        v_reviews = self.visible_reviews
        if v_reviews:
            avg = round(sum(r.rating for r in v_reviews) / len(v_reviews), 1)
            return avg
        if self.admin_rating is not None:
            return float(self.admin_rating)
        return 4.0

    @property
    def reviews_count(self):
        return len(self.visible_reviews)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "price": float(self.price),
            "business_type": self.business_type,
            "category": self.category,
            "image_url": self.image_url,
            "global_stock": self.global_stock,
            "is_active": self.is_active,
            "is_veg": self.is_veg,
            "is_gluten_free": self.is_gluten_free,
            "spice_level": self.spice_level,
            "tag": self.tag,
            "admin_rating": self.admin_rating,
            "is_best_seller": self.is_best_seller,
            "is_popular": self.is_popular,
            "average_rating": self.average_rating,
            "reviews_count": self.reviews_count,
            "ingredients": self.ingredients,
            "nutritional_info": self.nutritional_info,
            "dietary_guidelines": self.dietary_guidelines,
            "deleted_at": self.deleted_at.isoformat() if getattr(self, "deleted_at", None) else None
        }


# ---------------------------------------------------------------------------
# OutletStock — per-item inventory at each outlet
# ---------------------------------------------------------------------------
class OutletStock(db.Model):
    __tablename__ = 'outlet_stocks'
    __table_args__ = (
        CheckConstraint('current_stock >= 0', name='chk_outlet_stock_current'),
        CheckConstraint('restock_limit >= 0', name='chk_outlet_stock_limit'),
    )

    id = Column(Integer, primary_key=True)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    current_stock = Column(Integer, nullable=False, default=0)
    restock_limit = Column(Integer, nullable=False, default=10)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    outlet = relationship('Outlet', backref=db.backref('stocks', cascade='all, delete-orphan'))
    menu_item = relationship('MenuItem', backref='outlet_stocks', lazy='joined')

    def __init__(self, outlet_id, menu_item_id, current_stock=0, restock_limit=10):
        self.outlet_id = outlet_id
        self.menu_item_id = menu_item_id
        self.current_stock = current_stock
        self.restock_limit = restock_limit

    @property
    def needs_restock(self):
        return self.current_stock <= self.restock_limit

    def to_dict(self):
        return {
            "id": self.id,
            "outlet_id": self.outlet_id,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "menu_item_price": float(self.menu_item.price) if self.menu_item else 0.0,
            "current_stock": self.current_stock,
            "restock_limit": self.restock_limit,
            "needs_restock": self.needs_restock
        }


# ---------------------------------------------------------------------------
# Supplier / Vendor Master
# ---------------------------------------------------------------------------
class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact_name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship('SupplierItem', backref='supplier', cascade='all, delete-orphan')

    def __init__(self, name, contact_name=None, phone=None, email=None, address=None, notes=None):
        self.name = name
        self.contact_name = contact_name
        self.phone = phone
        self.email = email
        self.address = address
        self.notes = notes

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_name": self.contact_name,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "notes": self.notes,
            "is_active": self.is_active,
            "item_count": len(self.items),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ---------------------------------------------------------------------------
# SupplierItem — link between Supplier and MenuItem
# ---------------------------------------------------------------------------
class SupplierItem(db.Model):
    __tablename__ = 'supplier_items'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=True)
    lead_days = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    menu_item = relationship('MenuItem', backref='supplier_links')

    def __init__(self, supplier_id, menu_item_id, cost_price=None, lead_days=1):
        self.supplier_id = supplier_id
        self.menu_item_id = menu_item_id
        self.cost_price = cost_price
        self.lead_days = lead_days

    def to_dict(self):
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "cost_price": float(self.cost_price) if self.cost_price else None,
            "lead_days": self.lead_days
        }


# ---------------------------------------------------------------------------
# StockAuditLog — every stock movement logged
# ---------------------------------------------------------------------------
class StockAuditLog(db.Model):
    __tablename__ = 'stock_audit_logs'

    id = Column(Integer, primary_key=True)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='SET NULL'), nullable=True)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='SET NULL'), nullable=True)
    change_qty = Column(Integer, nullable=False)
    change_type = Column(String(30), nullable=False)  # 'sale', 'qr_arrival', 'manual', 'assign', 'return'
    stock_before = Column(Integer, nullable=True)
    stock_after = Column(Integer, nullable=True)
    reference_id = Column(Integer, nullable=True)
    performed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    outlet = relationship('Outlet', foreign_keys=[outlet_id])
    menu_item = relationship('MenuItem', foreign_keys=[menu_item_id])
    user = relationship('User', foreign_keys=[performed_by])

    def __init__(self, change_qty, change_type, outlet_id=None, menu_item_id=None,
                 stock_before=None, stock_after=None, reference_id=None, performed_by=None, notes=None):
        self.outlet_id = outlet_id
        self.menu_item_id = menu_item_id
        self.change_qty = change_qty
        self.change_type = change_type
        self.stock_before = stock_before
        self.stock_after = stock_after
        self.reference_id = reference_id
        self.performed_by = performed_by
        self.notes = notes

    def to_dict(self):
        return {
            "id": self.id,
            "outlet_id": self.outlet_id,
            "outlet_name": self.outlet.name if self.outlet else None,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "change_qty": self.change_qty,
            "change_type": self.change_type,
            "stock_before": self.stock_before,
            "stock_after": self.stock_after,
            "reference_id": self.reference_id,
            "performed_by": self.performed_by,
            "performed_by_email": self.user.email if self.user else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ---------------------------------------------------------------------------
# ProductBatch — expiry / batch tracking per stock arrival
# ---------------------------------------------------------------------------
class ProductBatch(db.Model):
    __tablename__ = 'product_batches'

    id = Column(Integer, primary_key=True)
    outlet_stock_id = Column(Integer, ForeignKey('outlet_stocks.id', ondelete='CASCADE'), nullable=False)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    batch_number = Column(String(50), nullable=True)
    qty = Column(Integer, nullable=False, default=0)
    expiry_date = Column(Date, nullable=True)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    received_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    outlet_stock = relationship('OutletStock', backref='batches')
    outlet = relationship('Outlet', foreign_keys=[outlet_id])
    menu_item = relationship('MenuItem', foreign_keys=[menu_item_id])
    receiver = relationship('User', foreign_keys=[received_by])

    def __init__(self, outlet_stock_id, outlet_id, menu_item_id, qty, batch_number=None, expiry_date=None, received_by=None):
        self.outlet_stock_id = outlet_stock_id
        self.outlet_id = outlet_id
        self.menu_item_id = menu_item_id
        self.qty = qty
        self.batch_number = batch_number
        self.expiry_date = expiry_date
        self.received_by = received_by

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < datetime.now(timezone.utc).date()

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - datetime.now(timezone.utc).date()
        return delta.days

    def to_dict(self):
        return {
            "id": self.id,
            "outlet_stock_id": self.outlet_stock_id,
            "outlet_id": self.outlet_id,
            "outlet_name": self.outlet.name if self.outlet else None,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "batch_number": self.batch_number,
            "qty": self.qty,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "days_to_expiry": self.days_to_expiry,
            "is_expired": self.is_expired,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "received_by": self.received_by
        }


# ---------------------------------------------------------------------------
# Order — B2C home foods order
# ---------------------------------------------------------------------------
class Order(db.Model):
    __tablename__ = 'orders'
    __table_args__ = (
        Index('ix_order_status_payment', 'status', 'payment_status'),
        Index('ix_order_outlet_created', 'outlet_id', 'created_at'),
        CheckConstraint('total_price >= 0', name='chk_order_total_price'),
        CheckConstraint('delivery_charge >= 0', name='chk_order_delivery_charge'),
        CheckConstraint('tax_amount >= 0', name='chk_order_tax_amount'),
        CheckConstraint('discount_amount >= 0', name='chk_order_discount_amount'),
    )

    id = Column(Integer, primary_key=True)
    order_number = Column(String(30), unique=True, nullable=False)
    order_type = Column(String(20), nullable=False, default='online', index=True) # 'online' or 'pos'
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True) # Nullable for guest POS sales
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='SET NULL'), nullable=True, index=True)
    staff_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    total_price = Column(Numeric(10, 2), nullable=False, default=0.00)
    
    # Guest Checkout Details
    guest_name = Column(String(100), nullable=True)
    guest_email = Column(String(120), nullable=True)
    guest_phone = Column(String(20), nullable=True)

    tracking_code = Column(String(100), nullable=True)
    tracking_label = Column(Text, nullable=True)
    tracking_link = Column(String(500), nullable=True)  # 3rd party tracking URL
    is_received = Column(Boolean, default=False)
    cancel_reason = Column(String(255), nullable=True)
    refund_status = Column(Enum(RefundStatus), nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True, default=0.00)
    delivery_address = Column(String(500), nullable=True)
    delivery_charge = Column(Numeric(10, 2), default=0.00, nullable=False)
    payment_method = Column(String(50), nullable=False, default='COD')

    # Online payment tracking (Razorpay)
    razorpay_order_id = Column(String(64), nullable=True, index=True)
    razorpay_payment_id = Column(String(64), nullable=True)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.UNPAID, index=True)
    paid_at = Column(DateTime, nullable=True)

    loyalty_points_earned = Column(Integer, default=0, nullable=False)
    loyalty_points_redeemed = Column(Integer, default=0, nullable=False)
    applied_coupon_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    tax_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    discount_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    review_code = Column(String(20), unique=True, nullable=True) # Code required to leave a review
    delivery_confirmation_code = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship('User', foreign_keys=[customer_id], backref='orders')
    outlet = relationship('Outlet', backref='orders')
    staff = relationship('User', foreign_keys=[staff_id], backref='staff_orders')
    items = relationship('OrderItem', backref='order', cascade="all, delete-orphan", lazy='joined')

    def __init__(self, total_price=0.00, status='pending', items=None, payment_method='COD', 
                 order_type='online', customer_id=None, outlet_id=None, staff_id=None, delivery_address=None,
                 delivery_charge=0.00, loyalty_points_earned=0, loyalty_points_redeemed=0, applied_coupon_code=None, 
                 review_code=None, guest_name=None, guest_email=None, guest_phone=None,
                 notes=None, tax_amount=0.00, discount_amount=0.00):
        self.order_type = order_type
        self.customer_id = customer_id
        self.outlet_id = outlet_id
        self.staff_id = staff_id
        self.total_price = total_price
        self.status = status
        self.delivery_address = delivery_address
        self.delivery_charge = delivery_charge
        self.payment_method = payment_method
        self.loyalty_points_earned = loyalty_points_earned
        self.loyalty_points_redeemed = loyalty_points_redeemed
        self.applied_coupon_code = applied_coupon_code
        self.review_code = review_code
        self.guest_name = guest_name
        self.guest_email = guest_email
        self.guest_phone = guest_phone
        self.notes = notes
        self.tax_amount = tax_amount
        self.discount_amount = discount_amount
        self.delivery_confirmation_code = None
        self.order_number = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        if items:
            self.items = items

    def to_dict(self):
        d = {
            "id": self.id,
            "order_number": self.order_number,
            "order_type": self.order_type,
            "customer_id": self.customer_id,
            "customer_email": self.customer.email if self.customer else self.guest_email,
            "customer_name": f"{self.customer.first_name or ''} {self.customer.last_name or ''}".strip() if self.customer else self.guest_name,
            "customer_phone": self.customer.phone if self.customer else self.guest_phone,
            "outlet_id": self.outlet_id,
            "outlet_name": self.outlet.name if self.outlet else None,
            "staff_id": self.staff_id,
            "staff_email": self.staff.email if self.staff else None,
            "status": self.status,
            "total_price": float(self.total_price),
            "tax_amount": float(self.tax_amount),
            "discount_amount": float(self.discount_amount),
            "refund_status": self.refund_status,
            "refund_amount": float(self.refund_amount) if self.refund_amount is not None else 0.0,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status or "unpaid",
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "loyalty_points_earned": self.loyalty_points_earned,
            "loyalty_points_redeemed": self.loyalty_points_redeemed,
            "qr_code_base64": getattr(self, 'qr_code_base64', None),
            "review_code": self.review_code,
            "delivery_confirmation_code": self.delivery_confirmation_code,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if getattr(self, "deleted_at", None) else None
        }
        if self.order_type == 'online':
            d.update({
                "tracking_code": self.tracking_code,
                "tracking_label": self.tracking_label,
                "tracking_link": self.tracking_link,
                "is_received": self.is_received,
                "cancel_reason": self.cancel_reason,
                "notes": self.notes,
                "delivery_address": self.delivery_address,
                "delivery_charge": float(self.delivery_charge) if self.delivery_charge else 0,
                "feedback_submitted": self.review is not None
            })
        return d


# ---------------------------------------------------------------------------
# PaymentTransaction — immutable audit trail of every payment event
# ---------------------------------------------------------------------------
class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=True, index=True)
    provider = Column(String(30), nullable=False, default='razorpay')
    provider_order_id = Column(String(64), nullable=True)
    provider_payment_id = Column(String(64), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False, default=0.00)  # in major units (INR)
    currency = Column(String(10), nullable=False, default='INR')
    status = Column(Enum(TransactionStatus), nullable=False)
    event = Column(String(50), nullable=False)           # checkout_verify | payment.captured | ...
    signature_valid = Column(Boolean, nullable=True)
    source = Column(String(20), nullable=False, default='checkout')  # checkout | webhook
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship('Order', backref='payment_transactions')

    def __init__(self, order_id=None, provider='razorpay', provider_order_id=None,
                 provider_payment_id=None, amount=0.00, currency='INR', status=None,
                 event=None, signature_valid=None, source='checkout', raw_payload=None):
        self.order_id = order_id
        self.provider = provider
        self.provider_order_id = provider_order_id
        self.provider_payment_id = provider_payment_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.event = event
        self.signature_valid = signature_valid
        self.source = source
        self.raw_payload = raw_payload

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "provider": self.provider,
            "provider_order_id": self.provider_order_id,
            "provider_payment_id": self.provider_payment_id,
            "amount": float(self.amount) if self.amount is not None else 0.0,
            "currency": self.currency,
            "status": self.status,
            "event": self.event,
            "signature_valid": self.signature_valid,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------
class Refund(db.Model):
    __tablename__ = 'refunds'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(RefundStatus), nullable=False, default=RefundStatus.PENDING)
    processed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    order = relationship('Order', backref=db.backref('refunds', cascade="all, delete-orphan"))
    processor = relationship('User', foreign_keys=[processed_by])

    def __init__(self, order_id, amount, reason=None, status='pending', processed_by=None):
        self.order_id = order_id
        self.amount = amount
        self.reason = reason
        self.status = status
        self.processed_by = processed_by

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "amount": float(self.amount),
            "reason": self.reason,
            "status": self.status,
            "processed_by": self.processed_by,
            "processor_name": f"{self.processor.first_name} {self.processor.last_name}" if self.processor else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------
class OrderItem(db.Model):
    __tablename__ = 'order_items'
    __table_args__ = (
        CheckConstraint('quantity > 0', name='chk_order_item_qty'),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2), nullable=True)

    menu_item = relationship('MenuItem')

    def __init__(self, menu_item_id, price, quantity=1, order_id=None, original_price=None):
        self.menu_item_id = menu_item_id
        self.price = price
        self.original_price = original_price
        self.quantity = quantity
        if order_id:
            self.order_id = order_id

    def to_dict(self):
        return {
            "id": self.id,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "quantity": self.quantity,
            "price": float(self.price),
            "original_price": float(self.original_price) if self.original_price is not None else None
        }


# ---------------------------------------------------------------------------
# Review — Consolidated feedback and menu item reviews
# ---------------------------------------------------------------------------
class Review(db.Model):
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=True)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=True)
    
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    is_hidden = Column(Boolean, default=False)
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    customer = relationship('User', backref='reviews')
    order = relationship('Order', backref=db.backref('review', uselist=False))
    menu_item = relationship('MenuItem', backref='reviews')

    def __init__(self, customer_id, rating, comment=None, order_id=None, menu_item_id=None, is_hidden=False, admin_reply=None):
        self.customer_id = customer_id
        self.rating = rating
        self.comment = comment
        self.order_id = order_id
        self.menu_item_id = menu_item_id
        self.is_hidden = is_hidden
        self.admin_reply = admin_reply

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": f"{self.customer.first_name or ''} {self.customer.last_name or ''}".strip() or self.customer.email,
            "order_id": self.order_id,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "rating": self.rating,
            "comment": self.comment,
            "is_hidden": self.is_hidden,
            "admin_reply": self.admin_reply,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ---------------------------------------------------------------------------
# Coupon — B2C & POS Discount Coupon
# ---------------------------------------------------------------------------
class Coupon(db.Model):
    __tablename__ = 'coupons'
    __table_args__ = (
        CheckConstraint('discount_pct IS NOT NULL OR discount_amount IS NOT NULL', name='chk_coupon_discount'),
        CheckConstraint('discount_amount >= 0', name='chk_coupon_discount_amount'),
        CheckConstraint('discount_pct >= 0 AND discount_pct <= 100', name='chk_coupon_discount_pct'),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    discount_pct = Column(Integer, nullable=True)
    discount_amount = Column(Numeric(10, 2), nullable=True)
    max_discount_amount = Column(Numeric(10, 2), nullable=True)
    applicable_menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=True)
    applicable_customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    expiry_date = Column(Date, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    min_order_value = Column(Numeric(10, 2), default=0.00)
    is_first_order_only = Column(Boolean, default=False)
    scope = Column(String(20), default='both')  # 'both', 'outlet', 'customer'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    def __init__(self, code, discount_pct=None, discount_amount=None, max_discount_amount=None, 
                 applicable_menu_item_id=None, applicable_customer_id=None,
                 expiry_date=None, usage_limit=None, is_active=True, 
                 min_order_value=0.00, is_first_order_only=False, scope='both'):
        
        if discount_pct is None and discount_amount is None:
            raise ValueError("Coupon must have either discount_pct or discount_amount.")

        self.code = code.upper().strip()
        self.discount_pct = int(discount_pct) if discount_pct is not None and str(discount_pct).strip() != "" else None
        self.discount_amount = discount_amount
        self.max_discount_amount = max_discount_amount
        self.applicable_menu_item_id = applicable_menu_item_id
        self.applicable_customer_id = applicable_customer_id
        self.expiry_date = expiry_date
        self.usage_limit = usage_limit
        self.usage_count = 0
        self.is_active = is_active
        self.min_order_value = min_order_value
        self.is_first_order_only = is_first_order_only
        self.scope = scope if scope in ('both', 'outlet', 'customer') else 'both'

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "discount_pct": self.discount_pct,
            "discount_amount": float(self.discount_amount) if self.discount_amount is not None else None,
            "max_discount_amount": float(self.max_discount_amount) if self.max_discount_amount is not None else None,
            "applicable_menu_item_id": self.applicable_menu_item_id,
            "applicable_customer_id": self.applicable_customer_id,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "usage_limit": self.usage_limit,
            "usage_count": self.usage_count,
            "is_active": self.is_active,
            "min_order_value": float(self.min_order_value) if self.min_order_value is not None else 0.0,
            "is_first_order_only": self.is_first_order_only,
            "scope": self.scope or "both",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if getattr(self, "deleted_at", None) else None
        }


# ---------------------------------------------------------------------------
# StaffShift — clock-in / clock-out attendance tracking
# ---------------------------------------------------------------------------
class StaffShift(db.Model):
    __tablename__ = 'staff_shifts'

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False)
    clock_in_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    clock_out_time = Column(DateTime, nullable=True)
    # Expected cash = sum of all cash POS sales during this shift
    expected_cash = Column(Numeric(10, 2), nullable=True)
    # Actual cash counted by the staff at shift end
    actual_cash = Column(Numeric(10, 2), nullable=True)
    # cash_discrepancy = actual_cash - expected_cash (negative = short)
    cash_discrepancy = Column(Numeric(10, 2), nullable=True)
    status = Column(Enum(StaffShiftStatus), nullable=False, default=StaffShiftStatus.ACTIVE)
    notes = Column(Text, nullable=True)

    staff = relationship('User', foreign_keys=[staff_id], backref='shifts')
    outlet = relationship('Outlet', foreign_keys=[outlet_id], backref='shifts')

    def __init__(self, staff_id, outlet_id):
        self.staff_id = staff_id
        self.outlet_id = outlet_id
        self.status = StaffShiftStatus.ACTIVE
        self.clock_in_time = datetime.now(timezone.utc)

    @property
    def duration_hours(self):
        if not self.clock_out_time:
            return None
        end = self.clock_out_time
        start = self.clock_in_time
        # Ensure both are offset-aware for comparison
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - start
        return round(delta.total_seconds() / 3600, 2)

    def close_shift(self, actual_cash, expected_cash):
        self.clock_out_time = datetime.now(timezone.utc)
        self.actual_cash = actual_cash
        self.expected_cash = expected_cash
        self.cash_discrepancy = float(actual_cash) - float(expected_cash)
        self.status = StaffShiftStatus.CLOSED

    def to_dict(self):
        return {
            "id": self.id,
            "staff_id": self.staff_id,
            "staff_email": self.staff.email if self.staff else None,
            "staff_name": f"{self.staff.first_name or ''} {self.staff.last_name or ''}".strip() if self.staff else None,
            "outlet_id": self.outlet_id,
            "outlet_name": self.outlet.name if self.outlet else None,
            "clock_in_time": self.clock_in_time.isoformat() if self.clock_in_time else None,
            "clock_out_time": self.clock_out_time.isoformat() if self.clock_out_time else None,
            "duration_hours": self.duration_hours,
            "expected_cash": float(self.expected_cash) if self.expected_cash is not None else None,
            "actual_cash": float(self.actual_cash) if self.actual_cash is not None else None,
            "cash_discrepancy": float(self.cash_discrepancy) if self.cash_discrepancy is not None else None,
            "status": self.status,
            "notes": self.notes
        }


# ---------------------------------------------------------------------------
# Address — User address book
# ---------------------------------------------------------------------------
class Address(db.Model):
    __tablename__ = 'addresses'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(50), nullable=False)
    address_line = Column(String(500), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship('User', backref=db.backref('address_book', cascade='all, delete-orphan'))

    def __init__(self, user_id, title, address_line, is_default=False):
        self.user_id = user_id
        self.title = title
        self.address_line = address_line
        self.is_default = is_default

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "address_line": self.address_line,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# ---------------------------------------------------------------------------
# Favorite — Saved menu items
# ---------------------------------------------------------------------------
class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (
        UniqueConstraint('customer_id', 'menu_item_id', name='uix_customer_menu_item'),
    )
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    customer = relationship('User', backref=db.backref('saved_favorites', cascade='all, delete-orphan'))
    menu_item = relationship('MenuItem')

    def __init__(self, customer_id, menu_item_id):
        self.customer_id = customer_id
        self.menu_item_id = menu_item_id

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "menu_item_id": self.menu_item_id,
            "menu_item": self.menu_item.to_dict() if self.menu_item else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# ---------------------------------------------------------------------------
# KitchenProductionBatch — Central kitchen production tracking
# ---------------------------------------------------------------------------
class KitchenProductionBatch(db.Model):
    __tablename__ = 'kitchen_production_batches'
    id = Column(Integer, primary_key=True)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    batch_number = Column(String(50), unique=True, nullable=False)
    quantity_produced = Column(Integer, nullable=False)
    mfg_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expiry_date = Column(Date, nullable=False)
    produced_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = Column(Enum(ProductionBatchStatus), default=ProductionBatchStatus.PRODUCED)
    qr_code_base64 = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    menu_item = relationship('MenuItem')
    producer = relationship('User', foreign_keys=[produced_by])

    def __init__(self, menu_item_id, batch_number, quantity_produced, expiry_date, produced_by=None):
        self.menu_item_id = menu_item_id
        self.batch_number = batch_number
        self.quantity_produced = quantity_produced
        self.expiry_date = expiry_date
        self.produced_by = produced_by
    def to_dict(self):
        return {
            "id": self.id,
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else None,
            "batch_number": self.batch_number,
            "quantity_produced": self.quantity_produced,
            "mfg_date": self.mfg_date.isoformat() if self.mfg_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "produced_by": self.produced_by,
            "producer_email": self.producer.email if self.producer else None,
            "status": self.status        }

# ---------------------------------------------------------------------------
# WalletTransaction — loyalty points / wallet credit and debit history
# ---------------------------------------------------------------------------
class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Integer, nullable=False)  # Points amount
    transaction_type = Column(String(20), nullable=False)  # 'credit' or 'debit'
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship('User', backref=db.backref('wallet_transactions', cascade='all, delete-orphan'))

    def __init__(self, user_id, amount, transaction_type, description=None):
        self.user_id = user_id
        self.amount = amount
        self.transaction_type = transaction_type
        self.description = description

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# ---------------------------------------------------------------------------
# BroadcastMessage — CRM marketing broadcasts
# ---------------------------------------------------------------------------
class BroadcastMessage(db.Model):
    __tablename__ = 'broadcast_messages'
    id = Column(Integer, primary_key=True)
    target_segment = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    medium = Column(String(20), nullable=False) # 'sms', 'email', 'push'
    status = Column(Enum(BroadcastMessageStatus), default=BroadcastMessageStatus.SENT)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __init__(self, target_segment, message, medium, status='sent'):
        self.target_segment = target_segment
        self.message = message
        self.medium = medium
        self.status = status

    def to_dict(self):
        return {
            "id": self.id,
            "target_segment": self.target_segment,
            "message": self.message,
            "medium": self.medium,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None
        }

# ---------------------------------------------------------------------------
# Banner — dynamic promotional banners
# ---------------------------------------------------------------------------
class Banner(db.Model):
    __tablename__ = 'banners'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    eyebrow_text = Column(String(100), nullable=True)
    button_text = Column(String(50), nullable=True)
    image_url = Column(Text, nullable=False)  # Stores path/URL or raw base64
    target_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    display_location = Column(String(100), nullable=False, default='home')
    
    # --- Advanced Marketing Fields ---
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    target_audience = Column(String(50), default='all') # 'all', 'new_user', 'inactive_30_days'
    placement_zone = Column(String(50), default='hero_carousel') # 'hero_carousel', 'mid_feed', 'cart_upsell', 'top_bar'
    display_style = Column(String(50), default='cinematic_21_9') # 'cinematic_21_9', 'square_1_1', 'pill_text', 'story_circle', 'popup_modal'
    has_countdown = Column(Boolean, default=False)
    countdown_end_time = Column(DateTime, nullable=True)
    linked_product_id = Column(Integer, ForeignKey('menu_items.id', ondelete='SET NULL'), nullable=True)
    linked_coupon_code = Column(String(50), nullable=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, title, image_url, description=None, eyebrow_text=None, button_text=None, target_url=None, is_active=True, display_order=0, display_location='home',
                 start_date=None, end_date=None, target_audience='all', placement_zone='hero_carousel', 
                 display_style='cinematic_21_9', has_countdown=False, countdown_end_time=None, 
                 linked_product_id=None, linked_coupon_code=None):
        self.title = title
        self.description = description
        self.eyebrow_text = eyebrow_text
        self.button_text = button_text
        self.image_url = image_url
        self.target_url = target_url
        self.is_active = is_active
        self.display_order = display_order
        self.display_location = display_location
        self.start_date = start_date
        self.end_date = end_date
        self.target_audience = target_audience
        self.placement_zone = placement_zone
        self.display_style = display_style
        self.has_countdown = has_countdown
        self.countdown_end_time = countdown_end_time
        self.linked_product_id = linked_product_id
        self.linked_coupon_code = linked_coupon_code
        self.impressions = 0
        self.clicks = 0

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "eyebrow_text": self.eyebrow_text,
            "button_text": self.button_text,
            "image_url": self.image_url,
            "target_url": self.target_url,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "display_location": self.display_location,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "target_audience": self.target_audience,
            "placement_zone": self.placement_zone,
            "display_style": self.display_style,
            "has_countdown": self.has_countdown,
            "countdown_end_time": self.countdown_end_time.isoformat() if self.countdown_end_time else None,
            "linked_product_id": self.linked_product_id,
            "linked_coupon_code": self.linked_coupon_code,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ---------------------------------------------------------------------------
# StoreSetting — global store configurations (e.g. offline/online)
# ---------------------------------------------------------------------------
class StoreSetting(db.Model):
    __tablename__ = 'store_settings'
    id = Column(Integer, primary_key=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, setting_key, setting_value):
        self.setting_key = setting_key
        self.setting_value = setting_value

    def to_dict(self):
        return {
            "id": self.id,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# ---------------------------------------------------------------------------
# SupportTicket — customer support requests
# ---------------------------------------------------------------------------
class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='SET NULL'), nullable=True)
    issue_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(SupportTicketStatus), default=SupportTicketStatus.OPEN)
    admin_reply = Column(Text, nullable=True)
    attachment_url = Column(Text, nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship('User', foreign_keys=[customer_id])
    order = relationship('Order', foreign_keys=[order_id])

    def __init__(self, customer_id, issue_type, description, order_id=None,
                 attachment_url=None, attachment_filename=None):
        self.customer_id = customer_id
        self.issue_type = issue_type
        self.description = description
        self.order_id = order_id
        self.attachment_url = attachment_url
        self.attachment_filename = attachment_filename
        self.status = SupportTicketStatus.OPEN

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.first_name if self.customer else "Unknown",
            "order_id": self.order_id,
            "issue_type": self.issue_type,
            "description": self.description,
            "status": self.status,
            "admin_reply": self.admin_reply,
            "attachment_url": self.attachment_url,
            "attachment_filename": self.attachment_filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class StockRequest(db.Model):
    __tablename__ = 'stock_requests'
    
    id = Column(Integer, primary_key=True)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False)
    staff_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    menu_item_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(Enum(StockRequestStatus), default=StockRequestStatus.PENDING)
    type = Column(String(20), default='Restock') # Restock, Produce
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    outlet = relationship('Outlet', foreign_keys=[outlet_id])
    staff = relationship('User', foreign_keys=[staff_id])
    menu_item = relationship('MenuItem', foreign_keys=[menu_item_id])
    
    def __init__(self, outlet_id, menu_item_id, quantity, staff_id=None, request_type='Restock'):
        self.outlet_id = outlet_id
        self.menu_item_id = menu_item_id
        self.quantity = quantity
        self.staff_id = staff_id
        self.type = request_type
        
    def to_dict(self):
        return {
            "id": self.id,
            "outlet_id": self.outlet_id,
            "outlet_name": self.outlet.name if self.outlet else "Unknown",
            "staff_id": self.staff_id,
            "staff_name": self.staff.first_name if self.staff else "Admin",
            "menu_item_id": self.menu_item_id,
            "menu_item_name": self.menu_item.name if self.menu_item else "Unknown",
            "quantity": self.quantity,
            "status": self.status,
            "type": self.type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ---------------------------------------------------------------------------
# Market Purchases (B2B Admin Expenses)
# ---------------------------------------------------------------------------
class MarketPurchase(db.Model):
    __tablename__ = 'market_purchases'
    
    id = Column(Integer, primary_key=True)
    ingredient_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=True)
    unit = Column(String(20), nullable=True)
    cost = Column(Numeric(10, 2), nullable=False)
    expiration_date = Column(Date, nullable=True)
    receipt_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    purchased_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    admin_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    admin = relationship('User', foreign_keys=[admin_id])

    def __init__(self, ingredient_name, cost, quantity=None, unit=None, category=None, expiration_date=None, receipt_url=None, notes=None, admin_id=None):
        self.ingredient_name = ingredient_name
        self.cost = cost
        self.quantity = quantity
        self.unit = unit
        self.category = category
        self.expiration_date = expiration_date
        self.receipt_url = receipt_url
        self.notes = notes
        self.admin_id = admin_id

    def to_dict(self):
        return {
            "id": self.id,
            "ingredient_name": self.ingredient_name,
            "category": self.category,
            "quantity": float(self.quantity) if self.quantity is not None else None,
            "unit": self.unit,
            "cost": float(self.cost),
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "receipt_url": self.receipt_url,
            "notes": self.notes,
            "purchased_at": self.purchased_at.isoformat() if self.purchased_at else None,
            "admin_id": self.admin_id,
            "admin_email": getattr(self.admin, 'email', None) if getattr(self, 'admin', None) else None
        }

# ---------------------------------------------------------------------------
# AuditLog — tracks critical system actions
# ---------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    actor = relationship('User', foreign_keys=[actor_id])

    def __init__(self, action, actor_id=None, actor_role=None, resource_type=None, resource_id=None, old_value=None, new_value=None, ip_address=None, user_agent=None):
        self.action = action
        self.actor_id = actor_id
        self.actor_role = actor_role
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.old_value = old_value
        self.new_value = new_value
        self.ip_address = ip_address
        self.user_agent = user_agent

    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_email": self.actor.email if self.actor else None,
            "actor_role": self.actor_role,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

# ---------------------------------------------------------------------------
# MonthlyRevenueHistory — preserves historical monthly revenues
# ---------------------------------------------------------------------------
class MonthlyRevenueHistory(db.Model):
    __tablename__ = 'monthly_revenue_history'

    id = Column(Integer, primary_key=True)
    outlet_id = Column(Integer, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=True)
    month_year = Column(String(20), nullable=False) # e.g., '2026-08'
    total_revenue = Column(Numeric(15, 2), nullable=False, default=0.00)
    reset_by_admin_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    admin = relationship('User', foreign_keys=[reset_by_admin_id])
    outlet = relationship('Outlet', foreign_keys=[outlet_id])

    def to_dict(self):
        return {
            "id": self.id,
            "outlet_id": self.outlet_id,
            "month_year": self.month_year,
            "total_revenue": float(self.total_revenue),
            "reset_by_admin_id": self.reset_by_admin_id,
            "reset_by_admin_email": self.admin.email if self.admin else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }