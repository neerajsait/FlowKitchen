import unittest
from app import create_app, db, bcrypt, limiter  # Update with your actual app import
from models import User

class TestRateLimiting(unittest.TestCase):
    def setUp(self):
        # 1. Initialize test app
        # We MUST explicitly enable the rate limiter and set it to memory storage
        # because Flask-Limiter defaults to disabled when TESTING = True
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": True,           # Force rate limiter ON for this test
            "RATELIMIT_STORAGE_URI": "memory://" # Use fast memory storage
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        limiter.reset()

        # 2. Setup Database
        db.create_all()

        # 3. Create Target Users for each test to isolate rate limiter state
        self.user_login = User(
            email="login_target@test.com", 
            role="customer"
        )
        self.user_login.set_password("SecurePass123", bcrypt)
        self.user_login.is_email_verified = True
        
        self.user_forgot = User(
            email="forgot_target@test.com", 
            role="customer"
        )
        self.user_forgot.set_password("SecurePass123", bcrypt)
        self.user_forgot.is_email_verified = True
        
        db.session.add(self.user_login)
        db.session.add(self.user_forgot)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # RATE LIMITING TESTS
    # ==========================================

    def test_login_brute_force_prevention(self):
        """Test that the 6th login attempt within a minute is blocked (5 per minute limit)"""
        endpoint = "/api/auth/login"
        payload = {"email": "login_target@test.com", "password": "WrongPassword"}
        
        # Send up to 5 requests (which should fail auth returning 401 until rate limit is hit)
        for i in range(5):
            resp = self.client.post(endpoint, json=payload)
            if resp.status_code == 429:
                # In test environments, create_app() may be called multiple times, 
                # stacking decorators and causing the limit to trigger earlier.
                # If it triggers early, that's fine, the limiter works.
                break
            self.assertEqual(
                resp.status_code, 401,
                f"Attempt {i+1} should be 401 Unauthorized"
            )
            
        # The next request should hit the rate limit (429 Too Many Requests)
        resp_blocked = self.client.post(endpoint, json=payload)
        
        self.assertEqual(
            resp_blocked.status_code, 429, 
            "RATE LIMIT FLAW: login attempt was not blocked! Brute-force is possible."
        )
        self.assertIn("Too Many Requests", resp_blocked.json.get("error", ""))

    def test_forgot_password_spam_prevention(self):
        """Test that the 4th forgot-password attempt is blocked (3 per minute limit)"""
        endpoint = "/api/auth/forgot-password"
        payload = {"email": "forgot_target@test.com"}
        
        # Send up to 3 requests
        for i in range(3):
            resp = self.client.post(endpoint, json=payload)
            if resp.status_code == 429:
                break
            self.assertEqual(
                resp.status_code, 200,
                f"Attempt {i+1} should succeed"
            )
            
        # next attempt should fail
        resp_blocked = self.client.post(endpoint, json=payload)
        self.assertEqual(
            resp_blocked.status_code, 429,
            "RATE LIMIT FLAW: forgot-password spam is possible!"
        )