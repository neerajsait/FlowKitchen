import unittest
from app import create_app, db, bcrypt  # Update with your app import
from models import User

class TestInputValidationAndSQLi(unittest.TestCase):
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

        # 3. Create a valid Admin user to test login bypass attempts
        # FIXED: Removed is_email_verified from the parentheses
        self.admin = User(email="admin@test.com", role="admin")
        self.admin.set_password("SecurePass123", bcrypt)
        self.admin.is_email_verified = True  # <-- Set it here instead!
        
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # SQL INJECTION TESTS
    # ==========================================

    def test_sqli_login_bypass(self):
        """Test if a classic SQL Injection payload can bypass authentication"""
        # The classic payload tries to make the WHERE clause evaluate to True
        payload = {
            "email": "admin@test.com' OR '1'='1", 
            "password": "password"
        }
        resp = self.client.post("/api/auth/login", json=payload)
        
        # Should return 401 Unauthorized or 400, NOT 200 OK
        self.assertNotEqual(
            resp.status_code, 200, 
            "SQL INJECTION VULNERABILITY: Authentication was bypassed!"
        )
        self.assertIn(resp.status_code, (400, 401))

    # ==========================================
    # INPUT VALIDATION (XSS / MALFORMED DATA)
    # ==========================================

    def test_xss_in_name_field(self):
        """Test if the app rejects script tags and special characters in names"""
        payload = {
            "email": "hacker@test.com",
            "password": "ValidPass123",
            "first_name": "<script>alert('XSS')</script>",
            "last_name": "Hacker",
            "phone": "1234567890"
        }
        resp = self.client.post("/api/auth/register", json=payload)
        
        # Should be blocked by your regex: ^[a-zA-Z\s\-']+$
        self.assertEqual(
            resp.status_code, 400, 
            "INPUT VALIDATION FLAW: App accepted HTML/JS tags in the name field!"
        )
        self.assertIn("invalid characters", resp.json.get("message", "").lower())

    def test_invalid_phone_number_length(self):
        """Test if the app rejects phone numbers that are too short/long or contain letters"""
        invalid_phones = ["12345", "123456789012", "abcdefghij"]
        
        for phone in invalid_phones:
            payload = {
                "email": f"test_{phone}@test.com",
                "password": "ValidPass123",
                "first_name": "John",
                "last_name": "Doe",
                "phone": phone
            }
            resp = self.client.post("/api/auth/register", json=payload)
            
            self.assertEqual(
                resp.status_code, 400, 
                f"INPUT VALIDATION FLAW: App accepted invalid phone number: {phone}"
            )
            self.assertIn("10 digits", resp.json.get("message", "").lower())

    def test_temp_email_blocker(self):
        """Test if the app correctly blocks disposable email providers"""
        payload = {
            "email": "throwaway@10minutemail.com",
            "password": "ValidPass123",
            "first_name": "Spammer",
            "last_name": "Bot",
            "phone": "9998887776"
        }
        resp = self.client.post("/api/auth/register", json=payload)
        
        # Should be blocked by your TEMP_DOMAINS list
        self.assertEqual(
            resp.status_code, 400, 
            "INPUT VALIDATION FLAW: App allowed registration with a temporary email!"
        )
        self.assertIn("temp mail", resp.json.get("message", "").lower())