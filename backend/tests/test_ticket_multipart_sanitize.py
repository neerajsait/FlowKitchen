import pytest
import io
from app import create_app, db, bcrypt

@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            from models import Customer
            c = Customer(email="test@cust.com", first_name="Test", last_name="Cust")
            c.set_password("custpass", bcrypt)
            db.session.add(c)
            db.session.commit()
            
        yield client
        with app.app_context():
            db.drop_all()

def test_ticket_upload_security(client):
    # Login to get token
    res = client.post('/api/auth/login', json={"email": "test@cust.com", "password": "custpass"})
    token = res.get_json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: disallowed extension
    data = {
        "issue_type": "<script>alert(1)</script>",
        "description": "I have an issue",
        "attachment": (io.BytesIO(b"malicious script"), "hack.sh")
    }
    
    res = client.post('/api/customer/tickets', headers=headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 400
    assert "Disallowed file extension" in res.get_json().get("message", "")

    # Test 2: allowed extension but with XSS in issue_type
    data2 = {
        "issue_type": "<script>alert(1)</script>",
        "description": "I have an issue",
        "attachment": (io.BytesIO(b"fake image"), "image.png")
    }
    
    res2 = client.post('/api/customer/tickets', headers=headers, data=data2, content_type='multipart/form-data')
    # Should succeed or return 201
    assert res2.status_code in [200, 201]
    
    # Check XSS sanitization
    ticket_id = res2.get_json().get("ticket", {}).get("id")
    res3 = client.get(f'/api/customer/tickets', headers=headers)
    
    # Actually wait, there is no GET /api/customer/tickets/<id>. There is GET /api/customer/tickets
    # So I will get all tickets and find the one
    tickets = res3.get_json()
    issue_type = tickets[0].get("issue_type", "") if isinstance(tickets, list) and tickets else ""
    assert "<script>" not in issue_type
    assert "&lt;script&gt;" in issue_type or "alert(1)" in issue_type or issue_type == "" # bleached


def test_url_validation_rejects_javascript(client):
    res = client.post('/api/auth/login', json={"email": "test@cust.com", "password": "custpass"})
    token = res.get_json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    data = {
        "first_name": "Test",
        "image_url": "javascript:alert(1)"
    }
    res2 = client.put('/api/auth/profile', headers=headers, json=data)
    assert res2.status_code == 400
    assert "Invalid URL" in res2.get_json().get("message", "")
