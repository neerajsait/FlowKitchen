import unittest
from app import create_app, db, bcrypt
from models import User, Outlet, MenuItem, Order, OrderItem, SupportTicket, WalletTransaction, Coupon, Banner, StoreSetting

class MarketingTestCase(unittest.TestCase):
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
        
        # Setup Users
        self.admin = User(email="admin@test.com", first_name="Admin", role="admin")
        self.admin.admin_department = "Finance"
        self.admin.set_password("adminpass", bcrypt)
        db.session.add(self.admin)
        
        db.session.commit()

        # Add a coupon
        self.coupon = Coupon(code="TEST10", discount_pct=10, is_active=True, usage_limit=100)
        db.session.add(self.coupon)
        db.session.commit()

        # Add a banner
        self.banner = Banner(title="Banner 1", image_url="http://test.com/img.jpg", display_location="home", is_active=True)
        db.session.add(self.banner)
        db.session.commit()

        # Add a store setting
        self.setting = StoreSetting(setting_key="store_name", setting_value="Test Store")
        db.session.add(self.setting)
        db.session.commit()

        # Get Token
        resp_admin = self.client.post("/api/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
        self.admin_headers = {"Authorization": f"Bearer {resp_admin.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_whatsapp_webhook(self):
        import os
        os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-token"
        resp = self.client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=test-token&hub.challenge=123")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "123")

    def test_get_coupons(self):
        resp = self.client.get("/api/admin/coupons", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        codes = [c["code"] for c in resp.json]
        self.assertIn("TEST10", codes)

    def test_get_active_coupons(self):
        resp = self.client.get("/api/coupons/active")
        self.assertEqual(resp.status_code, 200)

    def test_get_banners(self):
        resp = self.client.get("/api/admin/banners", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 1)

    def test_get_store_settings(self):
        resp = self.client.get("/api/admin/store-settings", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
