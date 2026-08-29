import unittest
from flask_jwt_extended import create_access_token
from app import create_app, db, bcrypt  # Update with your app import
from models import User

class TestRBACAndPrivilegeEscalation(unittest.TestCase):
    def setUp(self):
        # 1. Initialize the app with an isolated in-memory test database
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 2. Create the tables
        db.create_all()

        # 3. Create a standard Customer (The "Attacker")
        self.customer = User(email="sneaky_customer@test.com", role="customer", first_name="Sneaky")
        self.customer.set_password("pass123", bcrypt)
        db.session.add(self.customer)
        db.session.commit()

        # Generate Customer Token
        customer_token = create_access_token(
            identity=str(self.customer.id), 
            additional_claims={"role": "customer", "token_version": getattr(self.customer, "token_version", 0)}
        )
        self.customer_headers = {
            "Authorization": f"Bearer {customer_token}",
            "Content-Type": "application/json"
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # PRIVILEGE ESCALATION TESTS
    # ==========================================

    def test_customer_access_admin_analytics(self):
        """Test if a customer can view the admin analytics dashboard"""
        resp = self.client.get(
            "/api/admin/analytics",
            headers=self.customer_headers
        )
        # Should be blocked by @role_required("admin", "outlet_owner")
        self.assertEqual(resp.status_code, 403, "Privilege Escalation: Customer accessed admin analytics!")

    def test_customer_create_menu_item(self):
        """Test if a customer can create a new menu item"""
        resp = self.client.post(
            "/api/admin/menu",
            json={"name": "Hacked Burger", "price": 10.00, "business_type": "both"},
            headers=self.customer_headers
        )
        # Should be blocked by @department_required("Operations") or admin check
        self.assertEqual(resp.status_code, 403, "Privilege Escalation: Customer created a menu item!")

    def test_customer_access_kitchen_orders(self):
        """Test if a customer can view kitchen operations"""
        resp = self.client.get(
            "/api/kitchen/orders",
            headers=self.customer_headers
        )
        # Should be blocked by @role_required("kitchen", "admin")
        self.assertEqual(resp.status_code, 403, "Privilege Escalation: Customer accessed kitchen queue!")

    def test_customer_credit_wallet(self):
        """Test if a customer can magically add money to their own wallet"""
        resp = self.client.post(
            "/api/admin/wallet/credit",
            json={"user_id": self.customer.id, "amount": 10000},
            headers=self.customer_headers
        )
        # Should be blocked by @role_required("admin")
        self.assertEqual(resp.status_code, 403, "Privilege Escalation: Customer credited their own wallet!")

    # ==========================================
    # BROKEN AUTHENTICATION TESTS (NO TOKEN)
    # ==========================================

    def test_unauthenticated_access_profile(self):
        """Test if an unauthenticated user can access a protected route"""
        resp = self.client.get("/api/auth/me")
        # Should be blocked by @jwt_required()
        self.assertEqual(resp.status_code, 401, "Broken Auth: Unauthenticated user accessed profile!")

    def test_unauthenticated_place_order(self):
        """Test if an unauthenticated user can place an order"""
        resp = self.client.post(
            "/api/foods/order",
            json={"items": [{"menu_item_id": 1, "quantity": 1}]}
        )
        # Should be blocked by @jwt_required() / token verification
        self.assertEqual(resp.status_code, 401, "Broken Auth: Unauthenticated user placed an order!")