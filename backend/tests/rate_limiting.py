import unittest
from app import create_app, db, bcrypt  # Update with your actual app import
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

        # 2. Setup Database
        db.create_all()

        # 3. Create a Target User (FIXED: is_email_verified handled outside User())
        self.user = User(
            email="target@test.com", 
            role="customer"
        )
        self.user.set_password("SecurePass123", bcrypt)
        self.user.is_email_verified = True  # <-- The fix is right here
        db.session.add(self.user)
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
        payload = {"email": "target@test.com", "password": "WrongPassword"}
        
        # Send 5 requests (which should be allowed, but fail auth returning 401)
        for i in range(5):
            resp = self.client.post(endpoint, json=payload)
            self.assertEqual(
                resp.status_code, 401, 
                f"Attempt {i+1} should be 401 Unauthorized"
            )
            
        # The 6th request should hit the rate limit (429 Too Many Requests)
        resp_blocked = self.client.post(endpoint, json=payload)
        
        self.assertEqual(
            resp_blocked.status_code, 429, 
            "RATE LIMIT FLAW: 6th login attempt was not blocked! Brute-force is possible."
        )
        self.assertIn("Too Many Requests", resp_blocked.json.get("error", ""))

    def test_forgot_password_spam_prevention(self):
        """Test that the 4th forgot-password attempt is blocked (3 per minute limit)"""
        endpoint = "/api/auth/forgot-password"
        payload = {"email": "target@test.com"}
        
        # Send 3 requests (These should be allowed, returning 200 OK)
        for i in range(3):
            resp = self.client.post(endpoint, json=payload)
            self.assertEqual(
                resp.status_code, 200, 
                f"Attempt {i+1} should succeed"
            )
            
        # The 4th request should be blocked
        resp_blocked = self.client.post(endpoint, json=payload)
        
        self.assertEqual(
            resp_blocked.status_code, 429, 
            "RATE LIMIT FLAW: 4th forgot-password attempt was not blocked! Email spam is possible."
        )