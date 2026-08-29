import unittest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from flask_jwt_extended import create_access_token
from app import create_app, db, bcrypt  # Update with your app import
from models import User, Order, Outlet, MenuItem, Coupon

class TestBusinessLogic(unittest.TestCase):
    def setUp(self):
        # 1. Initialize test app
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 2. Setup Database
        db.create_all()

        # 3. Create Baseline Data (Outlet & Menu Items)
        self.outlet = Outlet(name="Test Outlet", address="123 Main St")
        db.session.add(self.outlet)

        self.burger = MenuItem(
            name="Burger", 
            price=Decimal("150.00"), 
            business_type="both", 
            global_stock=100,
            is_active=True
        )
        db.session.add(self.burger)

        # 4. Create Coupons
        self.min_order_coupon = Coupon(
            code="SAVE50", 
            discount_amount=Decimal("50.00"), 
            min_order_value=Decimal("500.00"), # Requires 500 spend
            is_active=True,
            scope="both"
        )
        self.first_time_coupon = Coupon(
            code="WELCOME",
            discount_pct=10,
            is_first_order_only=True,
            is_active=True,
            scope="both"
        )
        db.session.add(self.min_order_coupon)
        db.session.add(self.first_time_coupon)

        # 5. Create Customer with a realistic wallet balance
        self.customer = User(email="buyer@test.com", role="customer")
        self.customer.set_password("pass123", bcrypt)
        self.customer.loyalty_points = 50 # They have 50 points
        
        # THE FIX: Set email verified directly on the object before committing
        self.customer.is_email_verified = True 
        
        db.session.add(self.customer)
        db.session.commit()

        # Generate Customer Token
        customer_token = create_access_token(
            identity=str(self.customer.id), 
            additional_claims={"role": "customer", "token_version": getattr(self.customer, "token_version", 0)}
        )
        self.headers = {
            "Authorization": f"Bearer {customer_token}",
            "Content-Type": "application/json"
        }
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # BUSINESS LOGIC TESTS
    # ==========================================

    def test_negative_quantity_order(self):
        """Test if a user can order a negative quantity to get a negative total (refund fraud)"""
        resp = self.client.post(
            "/api/foods/order",
            json={
                "items": [{"menu_item_id": self.burger.id, "quantity": -5}],
                "delivery_address": "123 Hacker Way",
                "delivery_charge": 0
            },
            headers=self.headers
        )
        
        # Look closely at your app.py: you have `if qty < 1: continue`. 
        # This strips the negative items out. If the cart is then empty, it might proceed with a 0 total, 
        # or it might throw an error. Let's assert it DOES NOT create a negative total order.
        
        # If it created an order, verify the total isn't negative
        if resp.status_code == 201:
            order_total = Decimal(resp.json["order"]["total_price"])
            self.assertGreaterEqual(
                order_total, Decimal("0.00"), 
                "BUSINESS LOGIC FLAW: App allowed an order with a negative total!"
            )
        else:
            # If it threw a 400 Bad Request, that is also a secure outcome
            self.assertEqual(resp.status_code, 400)

    def test_coupon_min_order_bypass(self):
        """Test if user can use a coupon without meeting the minimum order value"""
        # Burger is 150. Coupon requires 500.
        resp = self.client.post(
            "/api/foods/order",
            json={
                "items": [{"menu_item_id": self.burger.id, "quantity": 1}],
                "coupon_code": "SAVE50",
                "delivery_address": "123 Test St",
                "delivery_charge": 0
            },
            headers=self.headers
        )
        self.assertEqual(
            resp.status_code, 400, 
            "BUSINESS LOGIC FLAW: Coupon was applied without meeting minimum order value!"
        )
        self.assertIn("Minimum order value", resp.json.get("message", ""))

    def test_first_time_coupon_reuse(self):
        """Test if a user can abuse a 'First Order Only' coupon on their second order"""
        # Place the first legitimate order
        resp1 = self.client.post(
            "/api/foods/order",
            json={
                "items": [{"menu_item_id": self.burger.id, "quantity": 1}],
                "coupon_code": "WELCOME",
                "delivery_address": "123 Test St",
                "delivery_charge": 0
            },
            headers=self.headers
        )
        self.assertEqual(resp1.status_code, 201, "Setup failed: Could not place first order")

        # Attempt to use it again
        resp2 = self.client.post(
            "/api/foods/order",
            json={
                "items": [{"menu_item_id": self.burger.id, "quantity": 1}],
                "coupon_code": "WELCOME",
                "delivery_address": "123 Test St",
                "delivery_charge": 0
            },
            headers=self.headers
        )
        self.assertEqual(
            resp2.status_code, 400, 
            "BUSINESS LOGIC FLAW: User successfully reused a 'First Order Only' coupon!"
        )

    def test_over_redeem_loyalty_points(self):
        """Test if a user can redeem more loyalty points than they actually have in their wallet"""
        # User only has 50 points. Let's try to redeem 10,000.
        resp = self.client.post(
            "/api/foods/order",
            json={
                "items": [{"menu_item_id": self.burger.id, "quantity": 1}],
                "redeem_loyalty_points": 10000,
                "delivery_address": "123 Test St",
                "delivery_charge": 0
            },
            headers=self.headers
        )
        
        self.assertEqual(resp.status_code, 201)
        
        # Check how many points the backend *actually* allowed them to redeem
        redeemed = resp.json["order"]["loyalty_points_redeemed"]
        self.assertLessEqual(
            redeemed, 50, 
            f"BUSINESS LOGIC FLAW: User redeemed {redeemed} points but only had 50 in their wallet!"
        )