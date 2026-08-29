import unittest
import os
from app import create_app, db, bcrypt
from models import User, Admin, Customer
from flask_jwt_extended import create_access_token

class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "development"
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_cors_lockdown(self):
        response = self.client.options("/api/auth/login", headers={"Origin": "http://evil.com"})
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Origin"), "http://evil.com")
        
    def test_rate_limit(self):
        pass

    def test_staff_create_role_permissions(self):
        hr_user = Admin(email="hr@test.com")
        hr_user.is_active = True
        hr_user.admin_department = "HR"
        hr_user.is_superadmin = False
        hr_user.set_password("password123", bcrypt)
        db.session.add(hr_user)
        db.session.commit()
        token = create_access_token(identity=str(hr_user.id), additional_claims={"role": "admin", "admin_department": "HR", "is_superadmin": False, "token_version": getattr(hr_user, 'token_version', 0)})
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.set(f"user_tv:{hr_user.id}", getattr(hr_user, 'token_version', 0))

        # Standard HR admin cannot create another admin
        response = self.client.post("/api/admin/staff", json={
            "email": "newadmin@test.com",
            "role": "admin"
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)

    def test_loyalty_points_superadmin_restriction(self):
        hr_user = Admin(email="hr2@test.com")
        hr_user.is_active = True
        hr_user.admin_department = "HR"
        hr_user.is_superadmin = False
        hr_user.set_password("pwd", bcrypt)
        customer = Customer(email="cust@test.com")
        customer.is_active = True
        customer.set_password("pwd", bcrypt)
        db.session.add(hr_user)
        db.session.add(customer)
        db.session.commit()
        hr_id = hr_user.id
        cust_id = customer.id
        token = create_access_token(identity=str(hr_id), additional_claims={"role": "admin", "admin_department": "HR", "is_superadmin": False, "token_version": getattr(hr_user, 'token_version', 0)})
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.set(f"user_tv:{hr_id}", getattr(hr_user, 'token_version', 0))

        # Standard HR admin cannot directly edit loyalty points
        response = self.client.put(f"/api/admin/users/{cust_id}", json={
            "loyalty_points": 500
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)
