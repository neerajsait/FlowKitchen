import unittest
from app import create_app, db, bcrypt
from models import User, Admin, Customer, Staff

class AuthTestCase(unittest.TestCase):
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
        db.session.query(User).delete()
        db.session.commit()
        
        # Setup initial users
        self.admin = Admin(email="admin@test.com", first_name="Admin")
        self.admin.is_superadmin = True
        self.admin.set_password("adminpass", bcrypt)
        
        self.customer = Customer(email="customer@test.com", first_name="Cust")
        self.customer.set_password("custpass", bcrypt)
        
        db.session.add_all([self.admin, self.customer])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        
    def get_jwt_headers(self, email, password):
        resp = self.client.post("/api/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            token = resp.json.get("access_token")
            return {"Authorization": f"Bearer {token}"}
        return {}

    # --- Registration Tests ---
    def test_register_success(self):
        resp = self.client.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "newpass123",
            "first_name": "New",
            "last_name": "User",
            "role": "customer",
            "phone": "1234567890"
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn("registration confirmation will be sent", resp.json["message"])
        user = db.session.query(User).filter_by(email="new@test.com").first()
        self.assertIsNotNone(user)

    def test_register_duplicate_email(self):
        resp = self.client.post("/api/auth/register", json={
            "email": "customer@test.com", # already exists
            "password": "newpass123",
            "phone": "1234567890"
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn("registration confirmation will be sent", resp.json["message"])

    def test_register_invalid_email(self):
        resp = self.client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "newpass123",
            "phone": "1234567890"
        })
        # Could be 400 or 422 depending on how they validate
        self.assertIn(resp.status_code, [400, 422])

    def test_register_force_customer_role(self):
        # Even if a malicious user tries to register as admin, it should force customer or staff if handled properly
        resp = self.client.post("/api/auth/register", json={
            "email": "hacker@test.com",
            "password": "hack1234",
            "role": "admin",
            "phone": "1234567890"
        })
        self.assertEqual(resp.status_code, 201)
        user = db.session.query(User).filter_by(email="hacker@test.com").first()
        self.assertEqual(user.role, "customer") # Expected to be downgraded

    # --- Login Tests ---
    def test_login_success(self):
        resp = self.client.post("/api/auth/login", json={
            "email": "customer@test.com",
            "password": "custpass"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.json)

    def test_login_invalid_password(self):
        resp = self.client.post("/api/auth/login", json={
            "email": "customer@test.com",
            "password": "wrongpassword"
        })
        self.assertEqual(resp.status_code, 401)

    # --- Profile Tests ---
    def test_get_me(self):
        headers = self.get_jwt_headers("customer@test.com", "custpass")
        resp = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["email"], "customer@test.com")

    def test_update_profile(self):
        headers = self.get_jwt_headers("customer@test.com", "custpass")
        resp = self.client.put("/api/auth/profile", json={
            "first_name": "UpdatedName"
        }, headers=headers)
        self.assertEqual(resp.status_code, 200)
        
        # Verify it stuck
        resp2 = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(resp2.json["first_name"], "UpdatedName")

    # --- Password Tests ---
    def test_change_password(self):
        headers = self.get_jwt_headers("customer@test.com", "custpass")
        
        # 1. Request OTP
        resp_otp = self.client.post("/api/auth/request-password-change-otp", json={
            "old_password": "custpass"
        }, headers=headers)
        self.assertEqual(resp_otp.status_code, 200)
        
        # Extract token from DB
        user = db.session.query(User).filter_by(email="customer@test.com").first()
        token = user.password_reset_token
        self.assertIsNotNone(token)
        
        # 2. Change Password
        resp = self.client.post("/api/auth/change-password", json={
            "old_password": "custpass",
            "otp": "1234567890abcdef1234567890abcdef",
            "new_password": "newcustpass123"
        }, headers=headers)
        self.assertEqual(resp.status_code, 200)
        
        # Verify old password fails
        resp2 = self.client.post("/api/auth/login", json={"email": "customer@test.com", "password": "custpass"})
        self.assertEqual(resp2.status_code, 401)
        
        # Verify new password works
        resp3 = self.client.post("/api/auth/login", json={"email": "customer@test.com", "password": "newcustpass123"})
        self.assertEqual(resp3.status_code, 200)

    def test_forgot_and_reset_password(self):
        # Forgot password
        resp = self.client.post("/api/auth/forgot-password", json={"email": "customer@test.com"})
        self.assertEqual(resp.status_code, 200)
        
        # Extract token directly from DB since emails aren't really sent in testing
        user = db.session.query(User).filter_by(email="customer@test.com").first()
        token = user.password_reset_token
        self.assertIsNotNone(token)
        
        # Reset password
        resp2 = self.client.post("/api/auth/reset-password", json={
            "email": "customer@test.com",
            "token": "1234567890abcdef1234567890abcdef",
            "new_password": "newcustpass123"
        })
        self.assertEqual(resp2.status_code, 200)
        
        # Login with new password
        resp3 = self.client.post("/api/auth/login", json={"email": "customer@test.com", "password": "newcustpass123"})
        self.assertEqual(resp3.status_code, 200)

    # --- Admin User Management ---
    def test_admin_get_users(self):
        admin_headers = self.get_jwt_headers("admin@test.com", "adminpass")
        resp = self.client.get("/api/admin/users", headers=admin_headers)
        # Should be 200 or 404 (if not implemented). The route is /api/admin/users
        # Looking at list_routes, it exists
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json) >= 2) # At least admin and customer

    def test_admin_delete_user(self):
        admin_headers = self.get_jwt_headers("admin@test.com", "adminpass")
        user = db.session.query(User).filter_by(email="customer@test.com").first()
        user_id = user.id
        
        # Attempt to delete
        resp = self.client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
        self.assertEqual(resp.status_code, 200)
        
        # Verify user is gone or soft-deleted
        # Let's see if we can get them in list
        resp2 = self.client.get("/api/admin/users", headers=admin_headers)
        emails = [u.get("email") for u in resp2.json if u.get("email")]
        self.assertNotIn("customer@test.com", emails)

if __name__ == '__main__':
    unittest.main()
