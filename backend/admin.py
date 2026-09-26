
import io
import os
import base64
import logging
import random
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import qrcode
import sqlalchemy.exc
from sqlalchemy import select, func, update, or_
from sqlalchemy.orm import joinedload
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from models import (
    db, User, Admin, Customer, Staff, OutletOwner, Outlet, MenuItem, OutletStock,
    Supplier, SupplierItem, StockAuditLog, ProductBatch,
    Order, OrderItem, Review, Coupon, StaffShift,
    KitchenStaff, KitchenProductionBatch, WalletTransaction, BroadcastMessage,
    Banner, StoreSetting, SupportTicket, StockRequest, MarketPurchase,
    AuditLog, MonthlyRevenueHistory, PaymentTransaction, Category
)

logger = logging.getLogger(__name__)

# Blueprint — url_prefix="" keeps the exact /api/admin/* paths unchanged.
admin_bp = Blueprint("admin_bp", __name__, url_prefix="")


def _get(name):
    """Lazily get a named helper/object from app module to avoid circular imports."""
    import app as _app_module
    return getattr(_app_module, name)


# ============================================================
# ADMIN ROUTES – Support Tickets
# ============================================================

@admin_bp.route("/api/admin/tickets", methods=["GET"])
def admin_get_tickets():
    role_required = _get("role_required")

    @role_required("admin", "superadmin")
    def _inner():
        tickets = db.session.scalars(select(SupportTicket).order_by(SupportTicket.status.asc(), SupportTicket.created_at.desc())).all()
        return jsonify([t.to_dict() for t in tickets]), 200
    return _inner()


@admin_bp.route("/api/admin/tickets/<int:ticket_id>", methods=["PUT"])
def admin_reply_ticket(ticket_id):
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin", "superadmin")
    def _inner():
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Categories
# ============================================================

@admin_bp.route("/api/admin/categories", methods=["GET"])
def admin_get_categories():
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        cats = db.session.scalars(select(Category).order_by(Category.name)).all()
        return jsonify([c.to_dict() for c in cats]), 200
    return _inner()


@admin_bp.route("/api/admin/categories", methods=["POST"])
def admin_add_category():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
        data = sanitize_input(request.get_json(silent=True) or {})
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Bad Request", "message": "Category name is required"}), 400
        existing = db.session.scalars(select(Category).where(func.lower(Category.name) == name.lower())).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Category already exists"}), 409
        cat = Category(name=name)
        db.session.add(cat)
        db.session.commit()
        return jsonify({"message": "Category created", "category": cat.to_dict()}), 201
    return _inner()


@admin_bp.route("/api/admin/categories/<int:cat_id>", methods=["DELETE"])
def admin_delete_category(cat_id):
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        cat = db.session.get(Category, cat_id)
        if not cat:
            return jsonify({"error": "Not Found", "message": "Category not found"}), 404
        if cat.name.lower() == "uncategorized":
            return jsonify({"error": "Forbidden", "message": "Cannot delete the Uncategorized category"}), 403
        uncategorized = db.session.scalars(select(Category).where(func.lower(Category.name) == "uncategorized")).first()
        if not uncategorized:
            uncategorized = Category(name="Uncategorized")
            db.session.add(uncategorized)
            db.session.flush()
        updated_count = db.session.execute(
            update(MenuItem).where(MenuItem.category_id == cat_id).values(category_id=uncategorized.id)
        ).rowcount
        db.session.delete(cat)
        db.session.commit()
        return jsonify({"message": "Category deleted successfully", "products_moved": updated_count}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Menu Items
# ============================================================

@admin_bp.route("/api/admin/menu", methods=["GET"])
def admin_get_menu():
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        items = db.session.scalars(select(MenuItem).where(MenuItem.is_active == True, MenuItem.deleted_at.is_(None)).order_by(MenuItem.business_type, MenuItem.name)).all()
        return jsonify([i.to_dict() for i in items]), 200
    return _inner()


@admin_bp.route("/api/admin/menu", methods=["POST"])
def admin_add_menu():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")
    _generate_unique_code = _get("_generate_unique_code")

    @department_required("Operations")
    def _inner():
        data = (sanitize_input(request.get_json(silent=True)) or {})
        name = (data.get("name") or "").strip()
        price = data.get("price")
        btype = data.get("business_type", "home_foods")

        if not name or price is None:
            return jsonify({"error": "Bad Request", "message": "name and price are required"}), 400
        if btype not in ("home_foods", "snack_supply", "both"):
            return jsonify({"error": "Bad Request", "message": "Invalid business_type"}), 400

        existing = db.session.scalars(
            select(MenuItem).where(func.lower(MenuItem.name) == name.lower())
        ).first()
        if existing:
            existing.price = Decimal(str(price))
            existing.business_type = btype
            existing.description = data.get("description") or existing.description
            if "category_id" in data:
                existing.category_id = data.get("category_id")
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
            name=name, price=Decimal(str(price)), business_type=btype,
            code=code if code else _generate_unique_code(db.session),
            description=data.get("description"), category_id=data.get("category_id"),
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
    return _inner()


@admin_bp.route("/api/admin/menu/<int:item_id>", methods=["PUT"])
def admin_edit_menu(item_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
        item = db.session.get(MenuItem, item_id)
        if not item:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("name", "code", "description", "category_id", "image_url", "global_stock",
                      "is_veg", "is_gluten_free", "spice_level", "tag", "is_popular",
                      "ingredients", "nutritional_info", "dietary_guidelines"):
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
    return _inner()


@admin_bp.route("/api/admin/menu/<int:item_id>", methods=["DELETE", "POST"])
def admin_delete_menu(item_id):
    department_required = _get("department_required")
    log_admin_action = _get("log_admin_action")

    @department_required("Operations")
    def _inner():
        item = db.session.get(MenuItem, item_id)
        if not item:
            return jsonify({"error": "Not Found"}), 404
        item.is_active = False
        db.session.commit()
        admin_id = int(get_jwt_identity())
        log_admin_action(db.session, admin_id, "Deactivate Menu Item", "MenuItem", item.id, f"Deactivated {item.name}")
        db.session.commit()
        return jsonify({"message": "Item deactivated"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Outlets
# ============================================================

@admin_bp.route("/api/admin/outlets", methods=["GET"])
def admin_get_outlets():
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        outlets = db.session.scalars(select(Outlet).order_by(Outlet.name)).all()
        return jsonify([o.to_dict() for o in outlets]), 200
    return _inner()


@admin_bp.route("/api/admin/outlets", methods=["POST"])
def admin_add_outlet():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
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
        for it in data.get("items", []):
            mid = it.get("menu_item_id")
            if not mid:
                continue
            exists = db.session.scalars(select(OutletStock).filter_by(outlet_id=outlet.id, menu_item_id=mid)).first()
            if not exists:
                stock = OutletStock(outlet_id=outlet.id, menu_item_id=mid,
                                    current_stock=int(it.get("initial_stock", 0)),
                                    restock_limit=int(it.get("threshold", 10)))
                db.session.add(stock)
        db.session.commit()
        return jsonify({"message": "Outlet created", "outlet": outlet.to_dict()}), 201
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>", methods=["PUT"])
def admin_edit_outlet(outlet_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("name", "address", "latitude", "longitude", "owner_id", "revenue_share_percentage"):
            if field in data:
                setattr(outlet, field, data[field])
        db.session.commit()
        return jsonify({"message": "Updated", "outlet": outlet.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>", methods=["DELETE", "POST"])
def admin_delete_outlet(outlet_id):
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        db.session.execute(db.delete(Outlet).where(Outlet.id == outlet_id))
        db.session.commit()
        return jsonify({"message": "Outlet deleted"}), 200
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>/stock", methods=["POST"])
def admin_add_outlet_stock(outlet_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    log_stock_change = _get("log_stock_change")

    @department_required("Operations")
    def _inner():
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400
        exists = db.session.scalars(select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)).first()
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
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>/items", methods=["POST"])
def admin_add_outlet_item(outlet_id):
    """Alias for /stock endpoint — used by the frontend assign-item-to-outlet flow."""
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    log_stock_change = _get("log_stock_change")

    @department_required("Operations")
    def _inner():
        outlet = db.session.get(Outlet, outlet_id)
        if not outlet:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400
        exists = db.session.scalars(select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)).first()
        if exists:
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
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>/items/<int:menu_item_id>", methods=["DELETE"])
def admin_remove_outlet_item(outlet_id, menu_item_id):
    """Remove a specific item from an outlet's stock."""
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        stock = db.session.scalars(select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=menu_item_id)).first()
        if not stock:
            return jsonify({"error": "Not Found", "message": "Item not assigned to this outlet"}), 404
        db.session.delete(stock)
        db.session.commit()
        return jsonify({"message": "Item removed from outlet"}), 200
    return _inner()


@admin_bp.route("/api/admin/outlets/<int:outlet_id>/restock", methods=["POST"])
def admin_restock_outlet(outlet_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    log_stock_change = _get("log_stock_change")

    @department_required("Operations")
    def _inner():
        claims = get_jwt()
        admin_id = claims.get("user_id")
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        qty = int(data.get("qty", 0))
        if qty <= 0:
            return jsonify({"error": "Bad Request", "message": "qty must be > 0"}), 400
        stock = db.session.scalars(select(OutletStock).filter_by(outlet_id=outlet_id, menu_item_id=mid)).first()
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Revenue
# ============================================================

@admin_bp.route("/api/admin/revenue-share", methods=["GET"])
def admin_revenue_share():
    department_required = _get("department_required")

    @department_required("Finance")
    def _inner():
        outlets = db.session.scalars(select(Outlet)).all()
        results = []
        for o in outlets:
            total_sales = db.session.scalar(
                select(func.sum(Order.total_price))
                .where(Order.outlet_id == o.id, Order.status == 'delivered')
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Resets
# ============================================================

@admin_bp.route("/api/admin/reset/orders", methods=["POST"])
def admin_reset_orders():
    department_required = _get("department_required")

    @department_required("IT", "Operations", "Owner")
    def _inner():
        try:
            db.session.query(OrderItem).delete()
            db.session.query(Order).delete()
            db.session.commit()
            return jsonify({"message": "All orders and order items have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


@admin_bp.route("/api/admin/reset/reviews", methods=["POST"])
def admin_reset_reviews():
    department_required = _get("department_required")

    @department_required("IT", "Owner")
    def _inner():
        try:
            db.session.query(Review).delete()
            db.session.commit()
            return jsonify({"message": "All reviews have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


@admin_bp.route("/api/admin/reset/stock", methods=["POST"])
def admin_reset_stock():
    department_required = _get("department_required")

    @department_required("IT", "Operations", "Owner")
    def _inner():
        try:
            db.session.execute(update(MenuItem).values(global_stock=0))
            db.session.commit()
            return jsonify({"message": "All product global stock levels have been set to 0."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


@admin_bp.route("/api/admin/reset/analytics", methods=["POST"])
def admin_reset_analytics():
    department_required = _get("department_required")

    @department_required("IT", "Owner")
    def _inner():
        try:
            db.session.query(OrderItem).delete()
            db.session.query(Order).delete()
            db.session.query(WalletTransaction).delete()
            db.session.commit()
            return jsonify({"message": "Sales, Analytics and Wallets have been reset to zero."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


@admin_bp.route("/api/admin/reset/menu", methods=["POST"])
def admin_reset_menu():
    department_required = _get("department_required")

    @department_required("IT", "Owner")
    def _inner():
        try:
            db.session.query(Review).delete()
            db.session.query(MenuItem).delete()
            db.session.commit()
            return jsonify({"message": "Factory Reset successful: All Menu items and categories have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


@admin_bp.route("/api/admin/reset/customers", methods=["POST"])
def admin_reset_customers():
    department_required = _get("department_required")

    @department_required("IT", "Owner")
    def _inner():
        try:
            db.session.query(User).filter(User.role == 'customer').delete(synchronize_session=False)
            db.session.commit()
            return jsonify({"message": "All customer accounts have been deleted."}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    return _inner()


# ============================================================
# ADMIN ROUTES – Orders
# ============================================================

@admin_bp.route("/api/admin/orders", methods=["GET"])
def admin_get_orders():
    department_required = _get("department_required")

    @department_required("Finance", "Operations")
    def _inner():
        orders = db.session.scalars(
            select(Order).order_by(Order.created_at.desc()).limit(200)
        ).unique().all()
        return jsonify([o.to_dict() for o in orders]), 200
    return _inner()


@admin_bp.route("/api/admin/orders/<int:order_id>", methods=["PUT"])
def admin_update_order(order_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Finance", "Operations")
    def _inner():
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
            if order.status in award_statuses and old_status not in award_statuses:
                if order.customer_id and order.loyalty_points_earned > 0:
                    customer = db.session.scalars(select(User).where(User.id == order.customer_id).with_for_update()).first()
                    if customer:
                        customer.loyalty_points = (customer.loyalty_points or 0) + order.loyalty_points_earned
                        db.session.add(WalletTransaction(
                            user_id=customer.id, amount=order.loyalty_points_earned, transaction_type="credit",
                            description=f"Points awarded for completion of Order #{order.id}"
                        ))
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
                        if old_status in award_statuses and order.loyalty_points_earned and order.loyalty_points_earned > 0:
                            customer.loyalty_points = max(0, (customer.loyalty_points or 0) - order.loyalty_points_earned)
                            db.session.add(WalletTransaction(
                                user_id=customer.id, amount=-order.loyalty_points_earned, transaction_type="debit",
                                description=f"Points deducted due to {order.status} of Order #{order.id}"
                            ))
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
    return _inner()


@admin_bp.route("/api/admin/orders/<int:order_id>/ship", methods=["PUT"])
def admin_ship_order(order_id):
    """Mark order as shipped with a tracking code and optional label upload."""
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Finance", "Operations")
    def _inner():
        from flask import current_app
        _send_order_shipped_email = _get("_send_order_shipped_email")

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
        customer = db.session.get(User, order.customer_id)
        if customer and customer.email:
            _send_order_shipped_email(current_app._get_current_object(), order, customer, tracking_code)
        return jsonify({"message": "Order marked as shipped", "order": order.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/orders/<int:order_id>/refund", methods=["POST"])
def admin_refund_order(order_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Finance", "Operations")
    def _inner():
        try:
            from audit_utils import manual_log_audit
        except ImportError:
            manual_log_audit = None

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
        if manual_log_audit:
            manual_log_audit("refund_order", "Order", order_id,
                             old_value=f"status={order.status},amount={order.total_price}",
                             new_value=f"refund_amount={refund_amount},reason={reason}")
        return jsonify({"message": "Refund processed", "order": order.to_dict()}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Staff Management
# ============================================================

@admin_bp.route("/api/admin/staff", methods=["GET"])
def admin_get_staff():
    role_required = _get("role_required")

    @role_required("admin", "outlet_owner")
    def _inner():
        user_id = get_jwt_identity()
        current_user = db.session.get(User, user_id)
        query = select(User).where(
            User.role.in_(["staff", "outlet_owner", "kitchen", "customer"]),
            User.deleted_at.is_(None)
        ).order_by(User.created_at.desc())
        
        if current_user.role == "outlet_owner":
            owner_outlet_ids = [o.id for o in getattr(current_user, 'owned_outlets', [])]
            query = query.where(User.outlet_id.in_(owner_outlet_ids), User.role == "staff")
            
        staff = db.session.scalars(query).all()
        return jsonify([u.to_dict() for u in staff]), 200
    return _inner()


@admin_bp.route("/api/admin/staff", methods=["POST"])
def admin_create_staff():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    validate_phone = _get("validate_phone")

    @role_required("admin", "outlet_owner")
    def _inner():
        import secrets
        import string
        _send_staff_created_email = _get("_send_staff_created_email")
        _send_admin_created_email = _get("_send_admin_created_email")
        from flask import current_app

        data = (sanitize_input(request.get_json(silent=True)) or {})
        email = (data.get("email") or "").strip().lower()
        password = data.get("password")
        if not password:
            password = "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
        outlet_id = data.get("outlet_id")
        full_name = data.get("full_name")
        valid_phone, phone = validate_phone(data.get("phone"))
        if not valid_phone:
            return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number. Must be exactly 10 digits starting with 6, 7, 8, or 9."}), 400
        role = (data.get("role") or "staff").strip().lower()
        if role not in ("staff", "admin", "outlet_owner", "kitchen"):
            return jsonify({"error": "Bad Request", "message": "Invalid role"}), 400
        claims = get_jwt()
        current_user = db.session.get(User, get_jwt_identity())
        
        if claims.get("role") == "admin":
            if not claims.get("is_superadmin") and claims.get("admin_department") not in ("HR", "SuperAdmin"):
                return jsonify({"error": "Forbidden", "message": "HR department required"}), 403
            if role == "admin" and not claims.get("is_superadmin"):
                return jsonify({"error": "Forbidden", "message": "Only super-admins can create admin accounts"}), 403
        elif claims.get("role") == "outlet_owner":
            if role != "staff":
                return jsonify({"error": "Forbidden", "message": "Outlet owners can only create staff roles"}), 403
            if not outlet_id:
                return jsonify({"error": "Bad Request", "message": "outlet_id is required"}), 400
            owner_outlet_ids = [o.id for o in getattr(current_user, 'owned_outlets', [])]
            if outlet_id not in owner_outlet_ids:
                return jsonify({"error": "Forbidden", "message": "You can only assign staff to your own outlets."}), 403
        if not email:
            return jsonify({"error": "Bad Request", "message": "email required"}), 400
        if db.session.scalars(select(User).where(User.email == email)).first():
            return jsonify({"error": "Conflict", "message": "Email already exists"}), 409

        if role == "admin":
            admin_count = db.session.scalar(select(func.count(User.id)).where(User.role == "admin"))
            if admin_count >= 3:
                return jsonify({"error": "Conflict", "message": "Maximum of 3 admin accounts allowed."}), 409

        bcrypt = _get("bcrypt")

        if role == "admin":
            dept = data.get("admin_department")
            if not dept or dept not in ["Finance", "Operations", "HR"]:
                return jsonify({"error": "Bad Request", "message": "admin_department is required and must be Finance, Operations, or HR"}), 400
            user = Admin(email=email, full_name=full_name, phone=phone)
            user.admin_department = dept
        elif role == "staff":
            user = Staff(email=email, full_name=full_name, phone=phone, outlet_id=outlet_id)
        elif role == "outlet_owner":
            # pyrefly: ignore [unexpected-keyword]
            user = OutletOwner(email=email, full_name=full_name, phone=phone, outlet_id=outlet_id)
        elif role == "kitchen":
            user = KitchenStaff(email=email, full_name=full_name, phone=phone, outlet_id=outlet_id)
        else:
            return jsonify({"error": "Bad Request", "message": "Invalid role"}), 400

        user.set_password(password, bcrypt)
        if role in ("staff", "kitchen"):
            while True:
                code = str(random.randint(1000, 9999))
                if not db.session.scalars(select(User).where(User.staff_code == code)).first():
                    user.staff_code = code
                    break
            pin = (data.get("pin") or "").strip()
            if not pin or len(pin) != 4 or not pin.isdigit():
                return jsonify({"error": "Bad Request", "message": "A 4-digit PIN is required for staff and kitchen accounts"}), 400
            user.set_pin(pin, bcrypt)

        db.session.add(user)
        db.session.commit()

        if role in ("staff", "outlet_owner"):
            outlet = db.session.get(Outlet, outlet_id) if outlet_id else None
            _send_staff_created_email(current_app._get_current_object(), user, outlet)
        else:
            _send_admin_created_email(current_app._get_current_object(), user)

        return jsonify({"message": f"{role.capitalize()} created", "user": user.to_dict()}), 201
    return _inner()


@admin_bp.route("/api/admin/staff/<int:user_id>", methods=["PUT"])
def admin_edit_staff(user_id):
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    validate_phone = _get("validate_phone")
    log_admin_action = _get("log_admin_action")

    @role_required("admin", "outlet_owner")
    def _inner():
        import re
        _send_admin_password_changed_email = _get("_send_admin_password_changed_email")
        from flask import current_app

        claims = get_jwt()
        if claims.get("role") == "admin":
            if not claims.get("is_superadmin") and claims.get("admin_department") not in ("HR", "SuperAdmin"):
                return jsonify({"error": "Forbidden", "message": "HR department required"}), 403

        user = db.session.get(User, user_id)
        if not user or user.role not in ("staff", "admin", "outlet_owner", "kitchen", "customer"):
            return jsonify({"error": "Not Found"}), 404
            
        current_user = db.session.get(User, get_jwt_identity())
        if claims.get("role") == "outlet_owner":
            owner_outlet_ids = [o.id for o in getattr(current_user, 'owned_outlets', [])]
            if user.role != "staff" or user.outlet_id not in owner_outlet_ids:
                return jsonify({"error": "Forbidden", "message": "You can only edit staff in your assigned outlets."}), 403

        if getattr(user, 'is_superadmin', False):
            return jsonify({"error": "Forbidden", "message": "Cannot modify a super-admin."}), 403
        data = (sanitize_input(request.get_json(silent=True)) or {})
        for field in ("full_name",):
            if field in data:
                setattr(user, field, data[field])
        if "phone" in data:
            valid_phone, phone_clean = validate_phone(data["phone"])
            if not valid_phone:
                return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number."}), 400
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
            delta = new_points - old_points
            if delta != 0:
                db.session.add(WalletTransaction(
                    user_id=user.id, amount=delta,
                    transaction_type="credit" if delta > 0 else "debit",
                    description=f"Admin balance adjustment: {old_points} -> {new_points}"
                ))
            log_admin_action(db.session, get_jwt_identity(), "set_loyalty_points", "User", user.id, f"Loyalty points changed from {old_points} to {user.loyalty_points}")
        if "pin" in data:
            bcrypt = _get("bcrypt")
            pin = (data["pin"] or "").strip()
            if pin:
                if not pin.isdigit() or len(pin) != 4:
                    return jsonify({"error": "Bad Request", "message": "PIN must be exactly 4 digits"}), 400
                user.set_pin(pin, bcrypt)
            else:
                user.pin_hash = None
        password_changed = False
        if "password" in data:
            bcrypt = _get("bcrypt")
            if len(data["password"]) >= 8 and re.search(r'[A-Za-z]', data["password"]) and re.search(r'[0-9]', data["password"]):
                user.set_password(data["password"], bcrypt)
                password_changed = True
            else:
                return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain both letters and numbers."}), 400
        db.session.commit()
        if password_changed and user.role == "admin" and user.email:
            _send_admin_password_changed_email(current_app._get_current_object(), user)
        return jsonify({"message": "Updated", "user": user.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/staff/<int:user_id>", methods=["DELETE"])
def admin_delete_staff(user_id):
    department_required = _get("department_required")

    @department_required("HR")
    def _inner():
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
        user.bump_token_version()
        db.session.commit()
        return jsonify({"message": "Staff deleted successfully (soft delete)"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Coupons
# ============================================================

@admin_bp.route("/api/admin/coupons", methods=["GET"])
def admin_get_coupons():
    role_required = _get("role_required")

    @role_required("admin", "outlet_owner")
    def _inner():
        coupons = db.session.scalars(select(Coupon).where(Coupon.deleted_at.is_(None)).order_by(Coupon.created_at.desc())).all()
        return jsonify([c.to_dict() for c in coupons]), 200
    return _inner()


@admin_bp.route("/api/admin/coupons", methods=["POST"])
def admin_add_coupon():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Finance")
    def _inner():
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
            code=code, discount_pct=pct,
            discount_amount=Decimal(str(amt)) if amt else None,
            max_discount_amount=Decimal(str(data["max_discount_amount"])) if data.get("max_discount_amount") else None,
            applicable_menu_item_id=data.get("applicable_menu_item_id") or None,
            applicable_customer_id=data.get("applicable_customer_id") or None,
            expiry_date=expiry_date, usage_limit=data.get("usage_limit") or None,
            is_active=bool(data.get("is_active", True)),
            min_order_value=Decimal(str(data["min_order_value"])) if data.get("min_order_value") else Decimal("0"),
            is_first_order_only=bool(data.get("is_first_order_only", False)),
            scope=data.get("scope", "both")
        )
        db.session.add(coupon)
        db.session.commit()
        return jsonify({"message": "Coupon created", "coupon": coupon.to_dict()}), 201
    return _inner()


@admin_bp.route("/api/admin/coupons/<int:id>", methods=["PUT"])
def admin_edit_coupon(id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Finance")
    def _inner():
        coupon = db.session.get(Coupon, id)
        if not coupon:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        if "discount_pct" in data: coupon.discount_pct = data["discount_pct"]
        if "discount_amount" in data: coupon.discount_amount = Decimal(str(data["discount_amount"])) if data["discount_amount"] else None
        if "max_discount_amount" in data: coupon.max_discount_amount = Decimal(str(data["max_discount_amount"])) if data["max_discount_amount"] else None
        if "expiry_date" in data:
            coupon.expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date() if data["expiry_date"] else None
        if "usage_limit" in data: coupon.usage_limit = data["usage_limit"]
        if "is_active" in data: coupon.is_active = bool(data["is_active"])
        if "scope" in data: coupon.scope = data["scope"] if data["scope"] in ("both", "outlet", "customer") else "both"
        if "min_order_value" in data: coupon.min_order_value = Decimal(str(data["min_order_value"])) if data["min_order_value"] else Decimal("0")
        if "is_first_order_only" in data: coupon.is_first_order_only = bool(data["is_first_order_only"])
        db.session.commit()
        return jsonify({"message": "Coupon updated", "coupon": coupon.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/coupons/<int:id>", methods=["DELETE"])
def admin_delete_coupon(id):
    department_required = _get("department_required")

    @department_required("Finance")
    def _inner():
        coupon = db.session.get(Coupon, id)
        if not coupon:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(coupon)
        db.session.commit()
        return jsonify({"message": "Coupon deleted"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Suppliers
# ============================================================

@admin_bp.route("/api/admin/suppliers", methods=["GET"])
def admin_get_suppliers():
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        suppliers = db.session.scalars(select(Supplier).order_by(Supplier.name)).all()
        return jsonify([s.to_dict() for s in suppliers]), 200
    return _inner()


@admin_bp.route("/api/admin/suppliers", methods=["POST"])
def admin_add_supplier():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    validate_phone = _get("validate_phone")

    @department_required("Operations")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/suppliers/<int:sid>", methods=["PUT"])
def admin_edit_supplier(sid):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    validate_phone = _get("validate_phone")

    @department_required("Operations")
    def _inner():
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
                return jsonify({"error": "Bad Request", "message": "Invalid Indian phone number."}), 400
            s.phone = phone_clean
        db.session.commit()
        return jsonify({"message": "Updated", "supplier": s.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/suppliers/<int:sid>", methods=["DELETE"])
def admin_delete_supplier(sid):
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        s = db.session.get(Supplier, sid)
        if not s:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(s)
        db.session.commit()
        return jsonify({"message": "Supplier deleted"}), 200
    return _inner()


@admin_bp.route("/api/admin/suppliers/<int:sid>/items", methods=["POST"])
def admin_link_supplier_item(sid):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
        s = db.session.get(Supplier, sid)
        if not s:
            return jsonify({"error": "Not Found"}), 404
        data = (sanitize_input(request.get_json(silent=True)) or {})
        mid = data.get("menu_item_id")
        if not mid:
            return jsonify({"error": "Bad Request", "message": "menu_item_id required"}), 400
        exists = db.session.scalars(select(SupplierItem).filter_by(supplier_id=sid, menu_item_id=mid)).first()
        if exists:
            return jsonify({"error": "Conflict", "message": "Already linked"}), 409
        si = SupplierItem(supplier_id=sid, menu_item_id=mid,
                          cost_price=data.get("cost_price"),
                          lead_days=int(data.get("lead_days", 1)))
        db.session.add(si)
        db.session.commit()
        return jsonify({"message": "Linked", "item": si.to_dict()}), 201
    return _inner()


# ============================================================
# ADMIN ROUTES – Analytics, Forecasting & Audit
# ============================================================

@admin_bp.route("/api/admin/audit-logs", methods=["GET"])
@jwt_required()
def get_audit_logs():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        limit = request.args.get("limit", 100, type=int)
        logs = db.session.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).all()
        return jsonify([log.to_dict() for log in logs]), 200
    return _inner()


@admin_bp.route("/api/admin/revenue/reset", methods=["POST"])
@jwt_required()
def reset_revenue():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")

    @role_required("admin", "outlet_owner")
    def _inner():
        try:
            from audit_utils import manual_log_audit
        except ImportError:
            manual_log_audit = None

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
        if manual_log_audit:
            manual_log_audit("reset_revenue", "Outlet", outlet.id, new_value=str(outlet.revenue_cutoff_date))
        return jsonify({"message": "Revenue counter reset successfully", "recorded_revenue": float(rev)}), 200
    return _inner()


@admin_bp.route("/api/admin/revenue/history", methods=["GET"])
@jwt_required()
def get_revenue_history():
    role_required = _get("role_required")

    @role_required("admin", "outlet_owner")
    def _inner():
        claims = get_jwt()
        role = claims.get("role")
        user_outlet_id = claims.get("outlet_id")
        if role == "admin":
            history = db.session.scalars(select(MonthlyRevenueHistory).order_by(MonthlyRevenueHistory.created_at.desc())).all()
        else:
            history = db.session.scalars(select(MonthlyRevenueHistory).where(MonthlyRevenueHistory.outlet_id == user_outlet_id).order_by(MonthlyRevenueHistory.created_at.desc())).all()
        return jsonify([h.to_dict() for h in history]), 200
    return _inner()


@admin_bp.route("/api/admin/analytics", methods=["GET"])
def admin_analytics():
    role_required = _get("role_required")

    @role_required("admin", "outlet_owner")
    def _inner():
        from datetime import date as date_cls
        claims = get_jwt()
        role = claims.get("role")
        user_outlet_id = claims.get("outlet_id")
        share_pct = 0.0

        days = int(request.args.get("days", 30))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        b2c_conditions = [Order.created_at >= since, Order.order_type == "online", Order.status != "cancelled"]
        pos_conditions = [Order.created_at >= since, Order.order_type == "pos", Order.status != "cancelled"]

        if role == "outlet_owner" and user_outlet_id:
            b2c_conditions.append(Order.outlet_id == user_outlet_id)
            pos_conditions.append(Order.outlet_id == user_outlet_id)
            outlet_obj = db.session.get(Outlet, user_outlet_id)
            if outlet_obj and outlet_obj.revenue_share_percentage:
                share_pct = float(outlet_obj.revenue_share_percentage)

        b2c_rev = db.session.scalar(
            select(func.sum(Order.total_price))
            .outerjoin(Outlet, Order.outlet_id == Outlet.id)
            .where(*b2c_conditions)
            .where(or_(Outlet.id.is_(None), Outlet.revenue_cutoff_date.is_(None), Order.created_at >= Outlet.revenue_cutoff_date))
        ) or 0

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

        b2c_count = db.session.scalar(select(func.count(Order.id)).where(*b2c_conditions)) or 0
        pos_count = db.session.scalar(select(func.count(Order.id)).where(*pos_conditions)) or 0

        top_b2c = db.session.execute(
            select(MenuItem.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*b2c_conditions)
            .group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5)
        ).fetchall()

        top_pos = db.session.execute(
            select(MenuItem.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*pos_conditions)
            .group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc()).limit(5)
        ).fetchall()

        outlet_rev = db.session.execute(
            select(Outlet.name, func.sum(Order.total_price).label("rev"))
            .join(Order, Order.outlet_id == Outlet.id)
            .where(*pos_conditions)
            .where(or_(Outlet.revenue_cutoff_date.is_(None), Order.created_at >= Outlet.revenue_cutoff_date))
            .group_by(Outlet.name).order_by(func.sum(Order.total_price).desc())
        ).fetchall()

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

        low_stock_cond = [OutletStock.current_stock <= OutletStock.restock_limit]
        if role == "outlet_owner" and user_outlet_id:
            low_stock_cond.append(OutletStock.outlet_id == user_outlet_id)
        low_stock = db.session.scalars(select(OutletStock).where(*low_stock_cond)).all()

        today = date_cls.today()
        expiring_cond = [ProductBatch.expiry_date != None, ProductBatch.expiry_date <= today + timedelta(days=3)]
        if role == "outlet_owner" and user_outlet_id:
            expiring_cond.append(ProductBatch.outlet_id == user_outlet_id)
        expiring = db.session.scalars(select(ProductBatch).where(*expiring_cond)).all()

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
    return _inner()


@admin_bp.route("/api/admin/audit-log", methods=["GET"])
def admin_audit_log():
    department_required = _get("department_required")

    @department_required()
    def _inner():
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
        logs = db.session.scalars(
            select(StockAuditLog)
            .order_by(StockAuditLog.created_at.desc())
            .limit(per_page).offset((page - 1) * per_page)
        ).all()
        total = db.session.scalar(select(func.count(StockAuditLog.id))) or 0
        return jsonify({"logs": [l.to_dict() for l in logs], "total": total, "page": page}), 200
    return _inner()


@admin_bp.route("/api/admin/forecast", methods=["GET"])
def admin_forecast():
    department_required = _get("department_required")

    @department_required("Finance", "Operations")
    def _inner():
        since = datetime.now(timezone.utc) - timedelta(days=30)
        sales_query = db.session.execute(
            select(Order.outlet_id, OrderItem.menu_item_id, func.sum(OrderItem.quantity).label('total_sold'))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.created_at >= since, Order.order_type == "pos", Order.status != "cancelled")
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
    return _inner()


@admin_bp.route("/api/admin/batches", methods=["GET"])
def admin_get_batches():
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        batches = db.session.scalars(
            select(ProductBatch).order_by(ProductBatch.expiry_date.is_(None), ProductBatch.expiry_date.asc())
        ).all()
        return jsonify([b.to_dict() for b in batches]), 200
    return _inner()


@admin_bp.route("/api/admin/generate-qr", methods=["POST"])
def admin_generate_qr():
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
        import hmac as _hmac
        import hashlib
        from flask import current_app

        data = (sanitize_input(request.get_json(silent=True)) or {})
        if not data:
            return jsonify({"error": "Bad Request", "message": "Payload required"}), 400
        try:
            sig_payload = {
                "order_id": data.get("order_id"), "type": data.get("type"),
                "item": data.get("item"), "qty": data.get("qty"),
                "outlet_id": data.get("outlet_id"), "destination": data.get("destination"),
                "batch_number": data.get("batch_number"), "expiry_date": data.get("expiry_date")
            }
            serialized = json.dumps(sig_payload, sort_keys=True)
            signature = _hmac.new(current_app.config["SECRET_KEY"].encode(), serialized.encode(), hashlib.sha256).hexdigest()
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Users
# ============================================================

@admin_bp.route("/api/admin/users", methods=["GET"])
def admin_get_users():
    department_required = _get("department_required")

    @department_required("HR")
    def _inner():
        users = db.session.scalars(
            select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
        ).all()
        return jsonify([u.to_dict() for u in users]), 200
    return _inner()


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PUT"])
def admin_update_user(user_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @department_required("HR")
    def _inner():
        import re
        _send_admin_password_changed_email = _get("_send_admin_password_changed_email")
        from flask import current_app

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
            delta = new_points - old_points
            if delta != 0:
                db.session.add(WalletTransaction(
                    user_id=user.id, amount=delta,
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
                    admin_count = db.session.scalar(select(func.count(User.id)).where(User.role == "admin"))
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
        if "password" in data and data["password"]:
            new_pwd = data["password"]
            bcrypt = _get("bcrypt")
            if len(new_pwd) >= 8 and re.search(r'[A-Za-z]', new_pwd) and re.search(r'[0-9]', new_pwd):
                user.set_password(new_pwd, bcrypt)
                user.set_pin(new_pwd, bcrypt)
                user.bump_token_version()
                password_changed = True
            else:
                return jsonify({"error": "Bad Request", "message": "Password must be at least 8 characters and contain both letters and numbers."}), 400
        db.session.commit()
        if password_changed and user.role == "admin" and user.email:
            _send_admin_password_changed_email(current_app._get_current_object(), user)
        return jsonify({"message": "User updated successfully", "user": user.to_dict()}), 200
    return _inner()


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):
    department_required = _get("department_required")

    @department_required("HR")
    def _inner():
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
        user.bump_token_version()
        db.session.commit()
        return jsonify({"message": "User deleted successfully (soft delete)"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Staff Timesheets / Shifts
# ============================================================

@admin_bp.route("/api/admin/shifts", methods=["GET"])
def admin_get_shifts():
    department_required = _get("department_required")

    @department_required("HR")
    def _inner():
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
            query.order_by(StaffShift.clock_in_time.desc()).offset((page - 1) * limit).limit(limit)
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
                    Order.staff_id == s.staff_id, Order.outlet_id == s.outlet_id,
                    Order.created_at >= s.clock_in_time, Order.created_at <= end_time,
                    Order.status != "cancelled"
                )
                .group_by(MenuItem.name)
            ).all()
            s_dict["sales_summary"] = [
                {"item_name": row.menu_item_name, "total_qty": int(row.total_qty), "total_revenue": float(row.total_revenue)}
                for row in sales
            ]
            result.append(s_dict)
        return jsonify({
            "shifts": result, "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 1,
            "current_page": page
        }), 200
    return _inner()


@admin_bp.route("/api/admin/shifts/<int:shift_id>", methods=["DELETE"])
def admin_delete_shift(shift_id):
    department_required = _get("department_required")

    @department_required("HR")
    def _inner():
        shift = db.session.get(StaffShift, shift_id)
        if not shift:
            return jsonify({"error": "Not Found"}), 404
        db.session.delete(shift)
        db.session.commit()
        return jsonify({"message": "Shift record deleted"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Reviews
# ============================================================

@admin_bp.route("/api/admin/reviews", methods=["GET"])
def admin_get_reviews():
    role_required = _get("role_required")

    @role_required("admin", "outlet_owner")
    def _inner():
        reviews = db.session.scalars(select(Review).order_by(Review.created_at.desc())).all()
        return jsonify([r.to_dict() for r in reviews]), 200
    return _inner()


@admin_bp.route("/api/admin/reviews/<int:review_id>", methods=["PATCH", "PUT"])
def admin_update_review(review_id):
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")

    @department_required("Operations")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
def admin_delete_review(review_id):
    department_required = _get("department_required")

    @department_required("Operations")
    def _inner():
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"error": "Not Found", "message": "Review not found"}), 404
        db.session.delete(review)
        db.session.commit()
        return jsonify({"message": "Review deleted successfully"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – WhatsApp
# ============================================================

@admin_bp.route("/api/admin/whatsapp", methods=["GET"])
def admin_get_whatsapp_messages():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        from models import WhatsAppMessage
        messages = db.session.execute(db.select(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc())).scalars().all()
        return jsonify([m.to_dict() for m in messages]), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Wallet & CRM
# ============================================================

@admin_bp.route("/api/admin/wallet/credit", methods=["POST"])
def credit_wallet():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/wallet/debit", methods=["POST"])
def debit_wallet():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/wallet/transactions/<int:user_id>", methods=["GET"])
def get_wallet_transactions(user_id):
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        txs = db.session.scalars(
            select(WalletTransaction).where(WalletTransaction.user_id == user_id).order_by(WalletTransaction.created_at.desc())
        ).all()
        return jsonify([t.to_dict() for t in txs]), 200
    return _inner()


@admin_bp.route("/api/admin/customers/segments", methods=["GET"])
def get_customer_segments():
    department_required = _get("department_required")

    @department_required("Operations", "Finance")
    def _inner():
        customers = db.session.scalars(select(User).where(User.role == 'customer').options(joinedload(User.orders))).unique().all()
        segments = {"all": [], "frequent_buyers": [], "high_value": [], "inactive_30_days": []}
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        for c in customers:
            c_dict = c.to_dict()
            orders = c.orders
            c_dict['order_count'] = len(orders)
            c_dict['total_spent'] = sum(float(o.total_price) for o in orders)
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
                segments["inactive_30_days"].append(c_dict)
        return jsonify(segments), 200
    return _inner()


@admin_bp.route("/api/admin/bulk-coupons", methods=["POST"])
def bulk_coupons():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin")
    def _inner():
        data = sanitize_input(request.get_json(silent=True)) or {}
        min_loyalty_points = data.get("min_loyalty_points")
        coupon_data = data.get("coupon")
        if min_loyalty_points is None or not coupon_data:
            return jsonify({"error": "Bad Request", "message": "min_loyalty_points and coupon data are required"}), 400
        customers = db.session.scalars(
            select(User).where(User.role == 'customer', Customer.loyalty_points >= int(min_loyalty_points))
        ).all()
        coupon = Coupon(
            code=coupon_data.get("code"), discount_pct=coupon_data.get("discount_pct", 0),
            discount_amount=Decimal(str(coupon_data.get("discount_amount"))) if coupon_data.get("discount_amount") else None,
            usage_limit=len(customers),
            expiry_date=datetime.strptime(coupon_data["expires_at"], "%Y-%m-%d").date() if coupon_data.get("expires_at") else None,
            is_active=True
        )
        db.session.add(coupon)
        db.session.commit()
        log_admin_action(db.session, get_jwt_identity(), "bulk_coupons", "Coupon", coupon.id, f"Created coupon {coupon.code} for {len(customers)} users with >={min_loyalty_points} points")
        return jsonify({"message": f"Coupon {coupon.code} generated and assigned to {len(customers)} customers.", "matched_customers": len(customers)}), 201
    return _inner()


@admin_bp.route("/api/admin/broadcast", methods=["POST"])
def send_broadcast():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin")
    def _inner():
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Image Upload
# ============================================================

@admin_bp.route("/api/admin/upload_image", methods=["POST"])
def admin_upload_image():
    role_required = _get("role_required")
    limiter = _get("limiter")

    @limiter.limit("20 per minute")
    @role_required("admin")
    def _inner():
        from flask import current_app
        from werkzeug.utils import secure_filename
        import uuid

        if "file" not in request.files:
            return jsonify({"error": "Bad Request", "message": "No file part in the request"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Bad Request", "message": "No file selected for uploading"}), 400
        if file:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join(current_app.root_path, "static", "uploads", "images")
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            public_path = f"/static/uploads/images/{unique_filename}"
            return jsonify({"success": True, "path": public_path}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Audit Logs (alternate endpoint)
# ============================================================

@admin_bp.route("/api/admin/audit_logs", methods=["GET"])
def admin_get_audit_logs():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        logs = db.session.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)).all()
        return jsonify([log.to_dict() for log in logs]), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Banners
# ============================================================

@admin_bp.route("/api/admin/banners", methods=["GET"])
def admin_get_banners():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        banners = db.session.scalars(select(Banner).order_by(Banner.display_order.asc())).all()
        return jsonify([b.to_dict() for b in banners]), 200
    return _inner()


@admin_bp.route("/api/admin/banners", methods=["POST"])
def admin_create_banner():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")

    @role_required("admin")
    def _inner():
        limiter = _get("limiter")

        @limiter.limit("10 per minute")
        def _rate_limited():
            data = sanitize_input(request.get_json(silent=True)) or {}
            title = data.get("title")
            image_url = data.get("image_url")
            if not title or not image_url:
                return jsonify({"error": "Bad Request", "message": "title and image_url are required"}), 400
            if image_url and image_url.startswith("data:image/"):
                return jsonify({"error": "Bad Request", "message": "Base64 image uploads are not allowed. Please use the file upload component."}), 400
            start_date = datetime.fromisoformat(data["start_date"].replace('Z', '+00:00')) if data.get("start_date") else None
            end_date = datetime.fromisoformat(data["end_date"].replace('Z', '+00:00')) if data.get("end_date") else None
            countdown_end_time = datetime.fromisoformat(data["countdown_end_time"].replace('Z', '+00:00')) if data.get("countdown_end_time") else None
            banner = Banner(
                title=title, description=data.get("description"),
                eyebrow_text=data.get("eyebrow_text"), button_text=data.get("button_text"),
                image_url=image_url, target_url=data.get("target_url"),
                is_active=data.get("is_active", True), display_order=data.get("display_order", 0),
                display_location=data.get("display_location", "home"),
                start_date=start_date, end_date=end_date,
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
        return _rate_limited()
    return _inner()


@admin_bp.route("/api/admin/banners/<int:id>", methods=["PUT"])
def admin_update_banner(id):
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")

    @role_required("admin")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/banners/<int:id>", methods=["DELETE"])
def admin_delete_banner(id):
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        banner = db.session.get(Banner, id)
        if not banner:
            return jsonify({"error": "Not Found", "message": "Banner not found"}), 404
        db.session.delete(banner)
        db.session.commit()
        return jsonify({"message": "Banner deleted"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Store Settings
# ============================================================

@admin_bp.route("/api/admin/store-settings", methods=["GET"])
def admin_get_store_settings():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        settings = db.session.scalars(select(StoreSetting)).all()
        return jsonify({s.setting_key: s.setting_value for s in settings}), 200
    return _inner()


@admin_bp.route("/api/admin/store-settings", methods=["PUT"])
def admin_update_store_settings():
    role_required = _get("role_required")
    sanitize_input = _get("sanitize_input")
    log_admin_action = _get("log_admin_action")
    LOYALTY_SETTING_KEYS = _get("LOYALTY_SETTING_KEYS")

    @role_required("admin")
    def _inner():
        data = sanitize_input(request.get_json(silent=True)) or {}
        for key, (lo, hi) in LOYALTY_SETTING_KEYS.items():
            if key in data:
                try:
                    num = float(data[key])
                except (TypeError, ValueError):
                    return jsonify({"error": "Bad Request", "message": f"{key} must be a number"}), 400
                if not (lo <= num <= hi):
                    return jsonify({"error": "Bad Request", "message": f"{key} must be between {lo} and {hi}"}), 400
        for k, v in data.items():
            val_str = "true" if isinstance(v, bool) and v else ("false" if isinstance(v, bool) else str(v))
            setting = db.session.scalars(select(StoreSetting).where(StoreSetting.setting_key == k)).first()
            if not setting:
                setting = StoreSetting(setting_key=k, setting_value=val_str)
                db.session.add(setting)
            else:
                setting.setting_value = val_str
        log_admin_action(db.session, get_jwt_identity(), "update_store_settings", "StoreSetting", None, "Updated store settings")
        db.session.commit()
        return jsonify({"message": "Settings updated successfully"}), 200
    return _inner()


# ============================================================
# ADMIN ROUTES – Payment Settings (Razorpay)
# ============================================================

@admin_bp.route("/api/admin/settings/payment", methods=["GET"])
def admin_get_payment_settings():
    role_required = _get("role_required")
    department_required = _get("department_required")
    _setting_value = _get("_setting_value")

    @role_required("admin")
    @department_required("Finance", "Owner")
    def _inner():
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
    return _inner()


@admin_bp.route("/api/admin/settings/payment", methods=["POST"])
def admin_update_payment_settings():
    role_required = _get("role_required")
    department_required = _get("department_required")
    sanitize_input = _get("sanitize_input")
    _setting_value = _get("_setting_value")
    _set_setting = _get("_set_setting")
    _fernet = _get("_fernet")
    _encrypt_secret = _get("_encrypt_secret")
    log_admin_action = _get("log_admin_action")
    clear_razorpay_cache = _get("clear_razorpay_cache")

    @role_required("admin")
    @department_required("Finance", "Owner")
    def _inner():
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
    return _inner()


# ============================================================
# ADMIN ROUTES – Market Purchases
# ============================================================

@admin_bp.route('/api/admin/market-purchases', methods=['GET'])
def admin_get_market_purchases():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        try:
            purchases = MarketPurchase.query.order_by(MarketPurchase.purchased_at.desc()).all()
            return jsonify([p.to_dict() for p in purchases]), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return _inner()


@admin_bp.route('/api/admin/market-purchases', methods=['POST'])
def admin_add_market_purchase():
    role_required = _get("role_required")

    @role_required("admin")
    def _inner():
        data = request.json
        try:
            current_user = get_jwt_identity()
            admin_id_val = current_user.get('id') if isinstance(current_user, dict) else current_user
            purchase = MarketPurchase(
                ingredient_name=data.get('ingredient_name'),
                cost=data.get('cost'), quantity=data.get('quantity'),
                unit=data.get('unit'), category=data.get('category'),
                expiration_date=data.get('expiration_date'),
                receipt_url=data.get('receipt_url'), notes=data.get('notes'),
                admin_id=admin_id_val
            )
            db.session.add(purchase)
            db.session.commit()
            return jsonify(purchase.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    return _inner()


@admin_bp.route('/api/admin/market-purchases/<int:id>', methods=['PUT'])
@jwt_required()
def admin_edit_market_purchase(id):
    role_required = _get("role_required")

    @role_required('admin')
    def _inner():
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
    return _inner()


@admin_bp.route('/api/admin/market-purchases/<int:id>', methods=['DELETE'])
@jwt_required()
def admin_delete_market_purchase(id):
    role_required = _get("role_required")

    @role_required('admin')
    def _inner():
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
    return _inner()
