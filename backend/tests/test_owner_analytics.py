import unittest
from app import create_app, db, bcrypt
from models import User, Outlet, MenuItem, Order, OrderItem, SupportTicket, WalletTransaction

class OwnerAnalyticsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "JWT_SECRET_KEY": "a-very-long-test-jwt-secret-key-32-bytes"
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        db.create_all()
        
        # Setup Outlet
        self.outlet = Outlet(name="Test Outlet", address="123 Test St")
        db.session.add(self.outlet)
        db.session.commit()

        # Setup Users
        self.admin = User(email="admin@test.com", first_name="Admin", role="admin")
        self.admin.admin_department = "Operations"
        self.admin.set_password("adminpass", bcrypt)
        db.session.add(self.admin)

        self.owner = User(email="owner@test.com", first_name="Owner", role="outlet_owner")
        self.owner.outlet_id = self.outlet.id
        self.owner.set_password("ownerpass", bcrypt)
        db.session.add(self.owner)
        
        db.session.commit()

        # Setup Menu Item
        self.item = MenuItem(name="Burger", price=10.00, category="Main", code="B001", business_type="both")
        db.session.add(self.item)
        db.session.commit()

        # Add some orders for analytics
        self.order1 = Order(outlet_id=self.outlet.id, customer_id=self.admin.id, status="delivered", order_type="pos")
        db.session.add(self.order1)
        db.session.commit()
        
        self.order_item1 = OrderItem(order_id=self.order1.id, menu_item_id=self.item.id, quantity=2, price=10.00)
        db.session.add(self.order_item1)
        db.session.commit()

        # Get Tokens
        resp_admin = self.client.post("/api/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
        self.admin_headers = {"Authorization": f"Bearer {resp_admin.json['access_token']}"}

        resp_owner = self.client.post("/api/auth/login", json={"email": "owner@test.com", "password": "ownerpass"})
        self.owner_headers = {"Authorization": f"Bearer {resp_owner.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_owner_dashboard(self):
        resp = self.client.get("/api/owner/dashboard", headers=self.owner_headers)
        self.assertEqual(resp.status_code, 200)

    def test_admin_analytics(self):
        resp = self.client.get("/api/admin/analytics", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    def test_admin_forecast(self):
        resp = self.client.get("/api/admin/forecast", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    def test_admin_audit_log(self):
        resp = self.client.get("/api/admin/audit-log", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
