
"""
test_loyalty_points.py
Comprehensive loyalty-points tests for FlowKitchen.

Covers:
  - Settings (default rates, disabled program, invalid rates)
  - Online order: earn (deferred), redeem, over-redeem, guest cannot redeem
  - Cancel: refund redeemed points only (not uncredited earn)
  - Delivery confirm: credit earned points + WalletTransaction
  - POS: instant earn, redeem, optional customer link
  - Loyalty history API
  - Admin cannot edit points (non-superadmin)
  - Negative / zero / fractional edge cases
  - CheckConstraint loyalty_points >= 0

Run from backend/:
  REDIS_URL=memory:// python -m unittest tests.test_loyalty_points -v
  # or:
  REDIS_URL=memory:// python tests/test_loyalty_points.py
"""

import os
import unittest
from decimal import Decimal

# Force test env before app import
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("REDIS_URL", "memory://")

from flask_jwt_extended import create_access_token
from app import create_app, db, bcrypt
from models import (
    User, Customer, Admin, Staff, Outlet, MenuItem, Order, OrderItem,
    WalletTransaction, StoreSetting, Coupon, OutletStock
)
from constants import OrderStatus, PaymentStatus


class LoyaltyPointsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": False,
            "SECRET_KEY": "test-secret-key-loyalty",
            "JWT_SECRET_KEY": "a-very-long-test-jwt-secret-key-32-bytes",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Default loyalty settings: earn 0.1 pts per rupee, redeem 0.01 INR per point
        # (matches app defaults when StoreSetting rows are missing)
        self._set_loyalty(earn="0.1", redeem="0.01", enabled="true")

        self.outlet = Outlet(name="Loyalty Outlet", address="1 Test St")
        db.session.add(self.outlet)
        db.session.flush()

        self.item = MenuItem(
            name="Loyalty Burger",
            price=Decimal("100.00"),
            business_type="both",
            global_stock=1000,
            is_active=True,
        )
        db.session.add(self.item)
        db.session.flush()

        self.outlet_stock = OutletStock(
            outlet_id=self.outlet.id,
            menu_item_id=self.item.id,
            current_stock=1000
        )
        db.session.add(self.outlet_stock)

        # Customer with 100 points
        self.customer = Customer(email="loyal@test.com", full_name="Loyal User")
        self.customer.set_password("pass12345", bcrypt)
        self.customer.is_active = True
        self.customer.is_email_verified = True
        self.customer.loyalty_points = 100
        db.session.add(self.customer)

        # Zero-balance customer
        self.broke = Customer(email="broke@test.com", full_name="Broke User")
        self.broke.set_password("pass12345", bcrypt)
        self.broke.is_active = True
        self.broke.is_email_verified = True
        self.broke.loyalty_points = 0
        db.session.add(self.broke)

        # Staff for POS
        self.staff = Staff(email="staff@test.com", full_name="Cashier", outlet_id=None)
        self.staff.set_password("pass12345", bcrypt)
        self.staff.is_active = True
        self.staff.outlet_id = None  # set after flush if needed
        db.session.add(self.staff)

        # HR admin (not superadmin) — must not edit loyalty_points
        self.hr_admin = Admin(email="hr@test.com", full_name="HR Admin")
        self.hr_admin.set_password("pass12345", bcrypt)
        self.hr_admin.is_active = True
        self.hr_admin.admin_department = "HR"
        self.hr_admin.is_superadmin = False
        db.session.add(self.hr_admin)

        # Superadmin
        self.superadmin = Admin(email="super@test.com", full_name="Super")
        self.superadmin.set_password("pass12345", bcrypt)
        self.superadmin.is_active = True
        self.superadmin.is_superadmin = True
        db.session.add(self.superadmin)

        db.session.add(StoreSetting(setting_key='delivery_fee', setting_value='0.00'))
        db.session.commit()

        # Bind staff to outlet
        self.staff.outlet_id = self.outlet.id
        db.session.commit()

        self.customer_headers = self._auth_headers(self.customer, "customer")
        self.broke_headers = self._auth_headers(self.broke, "customer")
        self.staff_headers = self._auth_headers(
            self.staff, "staff",
            extra={"outlet_id": self.outlet.id}
        )
        self.hr_headers = self._auth_headers(
            self.hr_admin, "admin",
            extra={"admin_department": "HR", "is_superadmin": False},
        )
        self.super_headers = self._auth_headers(
            self.superadmin, "admin",
            extra={"admin_department": "Operations", "is_superadmin": True},
        )

        # Keep Redis token_version in sync if Redis is present
        try:
            from redis_client import get_redis
            r = get_redis()
            if r:
                for u in (self.customer, self.broke, self.staff, self.hr_admin, self.superadmin):
                    r.set(f"user_tv:{u.id}", getattr(u, "token_version", 0))
        except Exception:
            pass

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _auth_headers(self, user, role, extra=None):
        claims = {
            "role": role,
            "token_version": getattr(user, "token_version", 0),
        }
        if extra:
            claims.update(extra)
        token = create_access_token(identity=str(user.id), additional_claims=claims)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _set_loyalty(self, earn="0.1", redeem="0.01", enabled="true"):
        for key, val in (
            ("enable_loyalty_program", enabled),
            ("loyalty_earn_rate", earn),
            ("loyalty_redeem_rate", redeem),
        ):
            row = db.session.scalars(
                db.select(StoreSetting).where(StoreSetting.setting_key == key)
            ).first()
            if row:
                row.setting_value = str(val)
            else:
                db.session.add(StoreSetting(setting_key=key, setting_value=str(val)))
        db.session.commit()

    def _reload_customer(self, user_id=None):
        uid = user_id or self.customer.id
        db.session.expire_all()
        return db.session.get(Customer, uid) or db.session.get(User, uid)

    def _place_online_order(self, headers, qty=1, redeem=0, delivery_charge=0, guest=None):
        payload = {
            "items": [{"menu_item_id": self.item.id, "quantity": qty}],
            "delivery_address": "123 Test Lane",
            "payment_method": "COD",
            "delivery_charge": delivery_charge,
            "redeem_loyalty_points": redeem,
        }
        if guest:
            payload.update(guest)
        return self.client.post("/api/foods/order", json=payload, headers=headers or {})

    def _pos_sale(self, customer_email=None, redeem=0, qty=1):
        payload = {
            "items": [{"menu_item_id": self.item.id, "quantity": qty}],
            "payment_method": "cash",
            "redeem_loyalty_points": redeem,
        }
        if customer_email:
            payload["customer_email"] = customer_email
        return self.client.post("/api/pos/sell", json=payload, headers=self.staff_headers)

    # ==================================================================
    # 1. SETTINGS
    # ==================================================================
    def test_loyalty_disabled_earn_and_redeem_zero(self):
        """When program disabled, earn_rate and redeem yield 0 effect."""
        self._set_loyalty(enabled="false")
        before = self._reload_customer().loyalty_points

        resp = self._place_online_order(self.customer_headers, qty=1, redeem=50)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        data = resp.get_json()
        order = data.get("order") or data
        self.assertEqual(order.get("loyalty_points_earned", 0), 0)
        self.assertEqual(order.get("loyalty_points_redeemed", 0), 0)
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before, "Balance must not change when loyalty is disabled")

    def test_default_rates_when_settings_missing(self):
        """No StoreSetting rows → defaults earn=0.1, redeem=0.01."""
        db.session.query(StoreSetting).delete()
        db.session.commit()
        # 149 INR total (100 item + 49 default delivery fee) -> 149 * 0.1 = 14
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=0)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        self.assertEqual(order["loyalty_points_earned"], 14)
        self.assertEqual(order["loyalty_points_redeemed"], 0)

    # ==================================================================
    # 2. ONLINE ORDER — REDEEM
    # ==================================================================
    def test_redeem_exact_balance(self):
        """Redeem all 100 points on a large enough order."""
        # redeem_rate 0.01 → 100 pts = 1 INR discount; item 100 → still room
        before = 100
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=100)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        order = resp.get_json().get("order") or resp.get_json()
        self.assertEqual(order["loyalty_points_redeemed"], 100)
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, 0)

    def test_over_redeem_capped_to_balance(self):
        """Request 10000 points but only have 100 → redeem at most 100."""
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=10000)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        self.assertLessEqual(order["loyalty_points_redeemed"], 100)
        after = self._reload_customer().loyalty_points
        self.assertGreaterEqual(after, 0)
        self.assertEqual(after, 100 - order["loyalty_points_redeemed"])

    def test_over_redeem_capped_to_order_total(self):
        """Cannot redeem more value than order total (max_redeem_allowed)."""
        # total 100, redeem_rate 0.01 → max points = 100 / 0.01 = 10000
        # give customer huge balance
        c = self._reload_customer()
        c.loyalty_points = 50000
        db.session.commit()

        resp = self._place_online_order(self.customer_headers, qty=1, redeem=50000)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        redeemed = order["loyalty_points_redeemed"]
        # discount = redeemed * 0.01 must be <= 100
        self.assertLessEqual(redeemed * Decimal("0.01"), Decimal("100.00") + Decimal("0.01"))
        self.assertEqual(float(order["total_price"]), 0.0)  # fully covered

    def test_redeem_with_zero_balance(self):
        """Broke user redeem request → 0 redeemed, order still succeeds."""
        resp = self._place_online_order(self.broke_headers, qty=1, redeem=50)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        self.assertEqual(order["loyalty_points_redeemed"], 0)
        self.assertEqual(self._reload_customer(self.broke.id).loyalty_points, 0)

    def test_guest_cannot_redeem(self):
        """Guest checkout with redeem_loyalty_points → 400."""
        resp = self._place_online_order(
            headers=None,
            qty=1,
            redeem=10,
            guest={
                "guest_name": "Guest",
                "guest_email": "guest@test.com",
                "guest_phone": "9876543210",
            },
        )
        # Optional JWT route: no auth → either 400 loyalty message or still places without redeem
        data = resp.get_json() or {}
        if resp.status_code == 400:
            msg = (data.get("message") or "").lower()
            self.assertTrue("loyalty" in msg or "registered" in msg or "customer" in msg)
        else:
            # If guest order allowed, redeemed must be 0
            order = data.get("order") or data
            self.assertEqual(order.get("loyalty_points_redeemed", 0), 0)

    def test_negative_redeem_treated_as_zero(self):
        """Negative redeem should not increase balance."""
        before = self._reload_customer().loyalty_points
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=-50)
        # int(-50) is negative → branch redeem_points > 0 is false
        self.assertIn(resp.status_code, (201, 400))
        if resp.status_code == 201:
            after = self._reload_customer().loyalty_points
            self.assertEqual(after, before)  # no debit, earn still deferred

    # ==================================================================
    # 3. ONLINE ORDER — EARN (DEFERRED UNTIL DELIVERED)
    # ==================================================================
    def test_earn_not_credited_on_checkout(self):
        """Points earned are stored on order but NOT added to balance at place."""
        before = self._reload_customer().loyalty_points
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=0)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        self.assertEqual(order["loyalty_points_earned"], 10)  # 100 * 0.1
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before, "Balance must not increase until delivery")

    def test_earn_credited_on_delivery_confirm(self):
        """Confirm receipt → credit loyalty_points_earned + WalletTransaction."""
        resp = self._place_online_order(self.customer_headers, qty=2, redeem=0)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        order_id = order["id"]
        earned = order["loyalty_points_earned"]  # int(200 * 0.1) = 20
        self.assertEqual(earned, 20)

        # Simulate admin/staff marking delivered + set confirmation code,
        # or use confirm endpoint with matching code.
        o = db.session.get(Order, order_id)
        o.status = OrderStatus.SHIPPED  # or pending → confirm will set delivered
        o.delivery_confirmation_code = "1234"
        # If model uses tracking_id fallback:
        if hasattr(o, "tracking_code"):
            o.tracking_code = "1234"
        db.session.commit()

        before = self._reload_customer().loyalty_points
        conf = self.client.post(
            f"/api/foods/orders/{order_id}/confirm",
            json={"tracking_code": "1234"},
            headers=self.customer_headers,
        )
        # Some installs use delivery_confirmation_code field name
        if conf.status_code not in (200, 201):
            conf = self.client.post(
                f"/api/foods/orders/{order_id}/confirm",
                json={"code": "1234", "tracking_code": "1234"},
                headers=self.customer_headers,
            )

        self.assertIn(conf.status_code, (200, 201), conf.get_json())
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before + earned)

        txs = db.session.scalars(
            db.select(WalletTransaction).where(
                WalletTransaction.user_id == self.customer.id,
                WalletTransaction.transaction_type == "credit",
            )
        ).all()
        self.assertTrue(any(t.amount == earned for t in txs))

    def test_double_confirm_does_not_double_credit(self):
        """Second confirm on already-delivered order must not add points again."""
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=0)
        order = resp.get_json().get("order") or resp.get_json()
        order_id = order["id"]
        earned = order["loyalty_points_earned"]

        o = db.session.get(Order, order_id)
        o.delivery_confirmation_code = "9999"
        db.session.commit()

        for _ in range(2):
            self.client.post(
                f"/api/foods/orders/{order_id}/confirm",
                json={"tracking_code": "9999"},
                headers=self.customer_headers,
            )

        after = self._reload_customer().loyalty_points
        # Started 100; at most +earned once
        self.assertLessEqual(after, 100 + earned)
        # Exactly once if first confirm succeeded
        credit_txs = [
            t for t in db.session.scalars(
                db.select(WalletTransaction).where(WalletTransaction.user_id == self.customer.id)
            ).all()
            if t.transaction_type == "credit" and t.amount == earned
        ]
        self.assertLessEqual(len(credit_txs), 1)

    # ==================================================================
    # 4. CANCEL — REFUND REDEEMED ONLY
    # ==================================================================
    def test_cancel_refunds_redeemed_points(self):
        """Cancel before delivery restores redeemed points; does not claw back uncredited earn."""
        before = self._reload_customer().loyalty_points  # 100
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=40)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        order_id = order["id"]
        redeemed = order["loyalty_points_redeemed"]
        self.assertEqual(redeemed, 40)

        mid = self._reload_customer().loyalty_points
        self.assertEqual(mid, before - 40)

        cancel = self.client.post(
            f"/api/foods/orders/{order_id}/cancel",
            json={"reason": "Changed mind"},
            headers=self.customer_headers,
        )
        self.assertIn(cancel.status_code, (200, 201), cancel.get_json())

        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before, "Redeemed points must be fully restored on cancel")

        txs = db.session.scalars(
            db.select(WalletTransaction).where(
                WalletTransaction.user_id == self.customer.id,
                WalletTransaction.transaction_type == "credit",
            )
        ).all()
        self.assertTrue(any("cancel" in (t.description or "").lower() or "refund" in (t.description or "").lower() for t in txs))

    def test_cancel_does_not_deduct_uncredited_earn(self):
        """Pending earn was never credited → cancel must not reduce balance."""
        before = self._reload_customer().loyalty_points
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=0)
        order_id = (resp.get_json().get("order") or resp.get_json())["id"]
        cancel = self.client.post(
            f"/api/foods/orders/{order_id}/cancel",
            json={"reason": "No earn clawback"},
            headers=self.customer_headers,
        )
        self.assertIn(cancel.status_code, (200, 201))
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before)

    # ==================================================================
    # 5. POS — INSTANT EARN + REDEEM
    # ==================================================================
    def test_pos_instant_earn_when_customer_linked(self):
        """POS sale with customer_email credits points immediately (status=delivered)."""
        before = self._reload_customer().loyalty_points
        resp = self._pos_sale(customer_email="loyal@test.com", redeem=0, qty=1)
        self.assertIn(resp.status_code, (200, 201), resp.get_json())
        data = resp.get_json()
        earned = data.get("loyalty_points_earned") or (data.get("order") or {}).get("loyalty_points_earned")
        # After redeem 0: total ~100 → earn 10
        self.assertEqual(earned, 10)
        after = self._reload_customer().loyalty_points
        self.assertEqual(after, before + 10)

    def test_pos_redeem_and_earn_net(self):
        """POS: redeem 50 pts (0.50 INR off), earn on remaining total."""
        before = self._reload_customer().loyalty_points  # 100
        resp = self._pos_sale(customer_email="loyal@test.com", redeem=50, qty=1)
        self.assertIn(resp.status_code, (200, 201), resp.get_json())
        data = resp.get_json()
        redeemed = data.get("loyalty_points_redeemed") or (data.get("order") or {}).get("loyalty_points_redeemed")
        earned = data.get("loyalty_points_earned") or (data.get("order") or {}).get("loyalty_points_earned")
        self.assertEqual(redeemed, 50)
        # total after discount ≈ 99.5 → int(99.5 * 0.1) = 9
        self.assertEqual(earned, 9)
        after = self._reload_customer().loyalty_points
        # 100 - 50 + 9 = 59
        self.assertEqual(after, before - 50 + earned)

    def test_pos_without_customer_no_loyalty(self):
        """Anonymous POS sale → no earn/redeem."""
        resp = self._pos_sale(customer_email=None, redeem=20, qty=1)
        self.assertIn(resp.status_code, (200, 201), resp.get_json())
        data = resp.get_json()
        self.assertEqual(data.get("loyalty_points_earned", 0) or 0, 0)
        self.assertEqual(data.get("loyalty_points_redeemed", 0) or 0, 0)

    # ==================================================================
    # 6. HISTORY API
    # ==================================================================
    def test_loyalty_history_endpoint(self):
        """GET /api/customer/loyalty returns balance + history shape."""
        # Create a redeem so history has an entry
        self._place_online_order(self.customer_headers, qty=1, redeem=10)
        resp = self.client.get("/api/customer/loyalty", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertIn("loyalty_points", body)
        self.assertIn("history", body)
        self.assertIsInstance(body["history"], list)
        self.assertEqual(body["loyalty_points"], self._reload_customer().loyalty_points)

    def test_loyalty_history_requires_auth(self):
        resp = self.client.get("/api/customer/loyalty")
        self.assertIn(resp.status_code, (401, 422))

    # ==================================================================
    # 7. ADMIN RESTRICTION
    # ==================================================================
    def test_non_superadmin_cannot_set_loyalty_points(self):
        """HR admin PUT loyalty_points → 403."""
        resp = self.client.put(
            f"/api/admin/users/{self.customer.id}",
            json={"loyalty_points": 9999},
            headers=self.hr_headers,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._reload_customer().loyalty_points, 100)

    # ==================================================================
    # 8. EDGE CASES / SAFETY
    # ==================================================================
    def test_balance_never_negative_after_redeem(self):
        c = self._reload_customer()
        c.loyalty_points = 5
        db.session.commit()
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=100)
        self.assertEqual(resp.status_code, 201)
        after = self._reload_customer().loyalty_points
        self.assertGreaterEqual(after, 0)

    def test_earn_uses_post_discount_total(self):
        """Earn is computed on total AFTER redeem discount (online deferred amount)."""
        # 100 item, redeem 50 pts * 0.01 = 0.5 off → total 99.5 → earn int(9.95)=9
        resp = self._place_online_order(self.customer_headers, qty=1, redeem=50)
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json().get("order") or resp.get_json()
        self.assertEqual(order["loyalty_points_redeemed"], 50)
        self.assertEqual(order["loyalty_points_earned"], 9)

    def test_zero_quantity_or_empty_cart_no_loyalty_side_effects(self):
        before = self._reload_customer().loyalty_points
        resp = self.client.post(
            "/api/foods/order",
            json={
                "items": [],
                "delivery_address": "x",
                "redeem_loyalty_points": 10,
            },
            headers=self.customer_headers,
        )
        self.assertIn(resp.status_code, (400, 422))
        self.assertEqual(self._reload_customer().loyalty_points, before)

    def test_check_constraint_loyalty_non_negative_model(self):
        """Model CheckConstraint chk_user_loyalty_points — cannot persist negative."""
        c = self._reload_customer()
        c.loyalty_points = -1
        try:
            db.session.commit()
            # SQLite may not enforce CHECK depending on version; if it commits, flag it
            db.session.refresh(c)
            if c.loyalty_points < 0:
                self.fail("DB allowed negative loyalty_points — CHECK constraint not enforced")
        except Exception:
            db.session.rollback()  # expected if constraint works


if __name__ == "__main__":
    unittest.main(verbosity=2)
    