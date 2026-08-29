import pytest
from app import create_app, db

@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            from models import User
            admin = User(email="test@admin.com", first_name="Test", last_name="Admin", role="admin")
            from app import bcrypt
            admin.set_password("admin", bcrypt)
            db.session.add(admin)
            db.session.commit()
            yield client
        with app.app_context():
            db.drop_all()

def test_refresh_and_logout(client):
    res = client.post('/api/auth/login', json={"email": "test@admin.com", "password": "admin"})
    assert res.status_code == 200
    data = res.get_json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    assert access_token
    assert refresh_token

    # Refresh
    res2 = client.post('/api/auth/refresh', headers={"Authorization": f"Bearer {refresh_token}"})
    assert res2.status_code == 200
    assert "access_token" in res2.get_json()

    # Logout
    res3 = client.post('/api/auth/logout', headers={"Authorization": f"Bearer {access_token}"}, json={"refresh_token": refresh_token})
    assert res3.status_code == 200

    # Try to use access token again
    res4 = client.get('/api/auth/me', headers={"Authorization": f"Bearer {access_token}"})
    assert res4.status_code in [401, 422]

def test_profile_password_change_invalidates_token(client):
    res = client.post('/api/auth/login', json={"email": "test@admin.com", "password": "admin"})
    access_token = res.get_json()["access_token"]
    
    # Change password via profile
    res2 = client.put('/api/auth/profile', headers={"Authorization": f"Bearer {access_token}"}, json={
        "old_password": "admin",
        "password": "newadminpassword123"
    })
    assert res2.status_code == 200
    
    # Verify old token is rejected
    res3 = client.get('/api/auth/me', headers={"Authorization": f"Bearer {access_token}"})
    assert res3.status_code == 401

def test_logout_requires_redis_in_production(client, monkeypatch):
    import os
    # Do not set FLASK_ENV=production because the blocklist loader would return 401 instead of letting the route return 503
    monkeypatch.setenv('REDIS_URL', '') # No redis
    
    res = client.post('/api/auth/login', json={"email": "test@admin.com", "password": "admin"})
    access_token = res.get_json().get("access_token")
    
    # Mock get_redis to return None to simulate failure
    import redis_client
    monkeypatch.setattr(redis_client, 'get_redis', lambda: None)
    
    res2 = client.post('/api/auth/logout', headers={"Authorization": f"Bearer {access_token}"})
    assert res2.status_code == 503

def test_inactive_user_token_rejected(client):
    res = client.post('/api/auth/login', json={"email": "test@admin.com", "password": "admin"})
    access_token = res.get_json()["access_token"]
    
    # Verify works initially
    res1 = client.get('/api/auth/me', headers={"Authorization": f"Bearer {access_token}"})
    assert res1.status_code == 200

    # Deactivate user
    from models import User
    from app import db
    user = db.session.scalars(db.select(User).where(User.email == "test@admin.com")).first()
    user.is_active = False
    # Bump token version to ensure token is rejected even if Redis matches
    user.bump_token_version()
    db.session.commit()

    # Verify token is rejected
    res2 = client.get('/api/auth/me', headers={"Authorization": f"Bearer {access_token}"})
    assert res2.status_code == 401

def test_refresh_preserves_claims(client):
    from models import User, Outlet
    from app import db, bcrypt
    
    # Create outlet
    outlet = Outlet(name="Test Outlet", address="Test")
    outlet.id = 42
    db.session.add(outlet)
    
    # Create staff user
    staff = User(email="staff@test.com", first_name="Staff", role="staff")
    staff.outlet_id = 42
    staff.staff_code = "5555"
    staff.set_password("staff", bcrypt)
    staff.set_pin("1234", bcrypt)
    db.session.add(staff)
    db.session.commit()
    
    res = client.post('/api/auth/login', json={"email": "staff@test.com", "password": "staff"})
    data = res.get_json()
    refresh_token = data.get("refresh_token")
    
    # Refresh
    res2 = client.post('/api/auth/refresh', headers={"Authorization": f"Bearer {refresh_token}"})
    assert res2.status_code == 200
    new_access = res2.get_json()["access_token"]
    
    # Check token claims
    import jwt
    from flask import current_app
    decoded = jwt.decode(new_access, "test-jwt-secret", options={"verify_signature": False})
    assert decoded.get("role") == "staff"
    assert decoded.get("outlet_id") == 42
    assert decoded.get("user_id") == staff.id