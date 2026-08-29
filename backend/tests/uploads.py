import unittest
import io
from unittest.mock import patch
from flask_jwt_extended import create_access_token
from app import create_app, db, bcrypt  # Update with your app import if needed
from models import User, SupportTicket

class TestFileUploadSecurity(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "MAX_CONTENT_LENGTH": 2 * 1024 * 1024  # 2MB Limit
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

        self.customer = User(email="uploader@test.com", role="customer")
        self.customer.set_password("pass123", bcrypt)
        self.customer.is_email_verified = True
        db.session.add(self.customer)
        db.session.commit()

        login_resp = self.client.post("/api/auth/login", json={
            "email": "uploader@test.com",
            "password": "pass123"
        })
        token = login_resp.get_json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('werkzeug.datastructures.FileStorage.save')
    def test_path_traversal_filename(self, mock_save):
        """Test if the app strips dangerous path traversal characters"""
        data = {
            "issue_type": "Bug",
            "description": "Testing path traversal",
            "attachment": (io.BytesIO(b"fake data"), "../../../etc/passwd.jpg")
        }
        resp = self.client.post("/api/customer/tickets", data=data, headers=self.headers)
        self.assertEqual(resp.status_code, 201)
        ticket = db.session.scalar(db.select(SupportTicket).where(SupportTicket.description == "Testing path traversal"))
        self.assertNotIn("../", ticket.attachment_url)

    @patch('werkzeug.datastructures.FileStorage.save')
    def test_oversized_file_upload(self, mock_save):
        """Test if the app blocks files larger than the server limit"""
        huge_file_content = b"0" * (2 * 1024 * 1024 + 100000)
        data = {
            "issue_type": "Bug",
            "description": "Testing huge file",
            "attachment": (io.BytesIO(huge_file_content), "large_image.jpg")
        }
        resp = self.client.post("/api/customer/tickets", data=data, headers=self.headers)
        self.assertEqual(resp.status_code, 413)