import unittest
from app import create_app, db, bcrypt
from models import Admin, Customer, MenuItem, Outlet, Staff, Coupon

class AdminTestCase(unittest.TestCase):
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
        
        # Setup initial admin user
        self.admin = Admin(email="admin@test.com", first_name="Admin")
        self.admin.is_superadmin = True
        self.admin.set_password("adminpass", bcrypt)
        db.session.add(self.admin)
        db.session.commit()
        
        # Setup initial outlet
        self.outlet = Outlet(name="Test Outlet", address="123 Test St")
        db.session.add(self.outlet)
        db.session.commit()

        # Login to get admin token
        resp = self.client.post("/api/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
        self.admin_headers = {"Authorization": f"Bearer {resp.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- Menu Management Tests ---
    def test_admin_add_menu(self):
        resp = self.client.post("/api/admin/menu", json={
            "name": "Test Burger",
            "price": 10.99,
            "category": "Main",
            "description": "A delicious burger",
            "code": "B001",
            "loyalty_points_cost": 50,
            "dietary_flags": ["vegan"]
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])
        
        # Verify it was added
        resp2 = self.client.get("/api/admin/menu", headers=self.admin_headers)
        self.assertEqual(resp2.status_code, 200)
        item = next((m for m in resp2.json if m["name"] == "Test Burger"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["code"], "B001")

    def test_admin_edit_menu(self):
        # First add one directly
        item = MenuItem(name="Pizza", price=12.00, category="Main", description="Cheese", code="P001", business_type="B2C")
        db.session.add(item)
        db.session.commit()
        
        resp = self.client.put(f"/api/admin/menu/{item.id}", json={
            "price": 15.00
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        
        # Verify
        db.session.refresh(item)
        self.assertEqual(item.price, 15.00)

    def test_admin_delete_menu(self):
        item = MenuItem(name="To Delete", price=5.00, category="Side", code="D001", business_type="B2C")
        db.session.add(item)
        db.session.commit()
        
        resp = self.client.delete(f"/api/admin/menu/{item.id}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        
        # Should be soft deleted or removed
        resp2 = self.client.get("/api/admin/menu", headers=self.admin_headers)
        deleted_item = next((m for m in resp2.json if m["name"] == "To Delete"), None)
        self.assertIsNone(deleted_item)

    # --- Outlet Management Tests ---
    def test_admin_add_outlet(self):
        resp = self.client.post("/api/admin/outlets", json={
            "name": "New Outlet",
            "address": "456 New St"
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_edit_outlet(self):
        resp = self.client.put(f"/api/admin/outlets/{self.outlet.id}", json={
            "name": "Updated Outlet"
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(self.outlet)
        self.assertEqual(self.outlet.name, "Updated Outlet")

    # --- Staff Management Tests ---
    def test_admin_create_staff(self):
        resp = self.client.post("/api/admin/staff", json={
            "email": "staff@test.com",
            "password": "staffpass123",
            "first_name": "Staff",
            "last_name": "Member",
            "phone": "5555555555",
            "pin": "1234",
            "outlet_id": self.outlet.id
        }, headers=self.admin_headers)
        print("TEST RESP:", resp.json)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_delete_staff(self):
        staff = Staff(email="temp@test.com", first_name="Temp")
        staff.set_password("pass", bcrypt)
        db.session.add(staff)
        db.session.commit()
        
        resp = self.client.delete(f"/api/admin/staff/{staff.id}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    # --- Coupon Management Tests ---
    def test_admin_add_coupon(self):
        resp = self.client.post("/api/admin/coupons", json={
            "code": "DISCOUNT10",
            "discount_pct": 10.00,
            "description": "Ten pct off"
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_delete_coupon(self):
        coupon = Coupon(code="TO_DEL", discount_pct=5.00)
import unittest
from app import create_app, db, bcrypt
from models import Admin, Customer, MenuItem, Outlet, Staff, Coupon

class AdminTestCase(unittest.TestCase):
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
        
        # Setup initial admin user
        self.admin = Admin(email="admin@test.com", first_name="Admin")
        self.admin.is_superadmin = True
        self.admin.set_password("adminpass", bcrypt)
        db.session.add(self.admin)
        db.session.commit()
        
        # Setup initial outlet
        self.outlet = Outlet(name="Test Outlet", address="123 Test St")
        db.session.add(self.outlet)
        db.session.commit()

        # Login to get admin token
        resp = self.client.post("/api/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
        self.admin_headers = {"Authorization": f"Bearer {resp.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- Menu Management Tests ---
    def test_admin_add_menu(self):
        resp = self.client.post("/api/admin/menu", json={
            "name": "Test Burger",
            "price": 10.99,
            "category": "Main",
            "description": "A delicious burger",
            "code": "B001",
            "loyalty_points_cost": 50,
            "dietary_flags": ["vegan"]
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])
        
        # Verify it was added
        resp2 = self.client.get("/api/admin/menu", headers=self.admin_headers)
        self.assertEqual(resp2.status_code, 200)
        item = next((m for m in resp2.json if m["name"] == "Test Burger"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["code"], "B001")

    def test_admin_edit_menu(self):
        # First add one directly
        item = MenuItem(name="Pizza", price=12.00, category="Main", description="Cheese", code="P001", business_type="B2C")
        db.session.add(item)
        db.session.commit()
        
        resp = self.client.put(f"/api/admin/menu/{item.id}", json={
            "price": 15.00
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        
        # Verify
        db.session.refresh(item)
        self.assertEqual(item.price, 15.00)

    def test_admin_delete_menu(self):
        item = MenuItem(name="To Delete", price=5.00, category="Side", code="D001", business_type="B2C")
        db.session.add(item)
        db.session.commit()
        
        resp = self.client.delete(f"/api/admin/menu/{item.id}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        
        # Should be soft deleted or removed
        resp2 = self.client.get("/api/admin/menu", headers=self.admin_headers)
        deleted_item = next((m for m in resp2.json if m["name"] == "To Delete"), None)
        self.assertIsNone(deleted_item)

    # --- Outlet Management Tests ---
    def test_admin_add_outlet(self):
        resp = self.client.post("/api/admin/outlets", json={
            "name": "New Outlet",
            "address": "456 New St"
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_edit_outlet(self):
        resp = self.client.put(f"/api/admin/outlets/{self.outlet.id}", json={
            "name": "Updated Outlet"
        }, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(self.outlet)
        self.assertEqual(self.outlet.name, "Updated Outlet")

    # --- Staff Management Tests ---
    def test_admin_create_staff(self):
        resp = self.client.post("/api/admin/staff", json={
            "email": "staff@test.com",
            "password": "staffpass123",
            "first_name": "Staff",
            "last_name": "Member",
            "phone": "5555555555",
            "pin": "1234",
            "outlet_id": self.outlet.id
        }, headers=self.admin_headers)
        print("TEST RESP:", resp.json)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_delete_staff(self):
        staff = Staff(email="temp@test.com", first_name="Temp")
        staff.set_password("pass", bcrypt)
        db.session.add(staff)
        db.session.commit()
        
        resp = self.client.delete(f"/api/admin/staff/{staff.id}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    # --- Coupon Management Tests ---
    def test_admin_add_coupon(self):
        resp = self.client.post("/api/admin/coupons", json={
            "code": "DISCOUNT10",
            "discount_pct": 10.00,
            "description": "Ten pct off"
        }, headers=self.admin_headers)
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_delete_coupon(self):
        coupon = Coupon(code="TO_DEL", discount_pct=5.00)
        db.session.add(coupon)
        db.session.commit()
        
        resp = self.client.delete(f"/api/admin/coupons/{coupon.id}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)

    def test_invalid_image_url_scheme_rejected(self):
        res2 = self.client.post('/api/admin/menu', json={
            'name': 'Test Item Scheme',
            'price': '10.00',
            'category': 'Test',
            'business_type': 'home_foods',
            'image_url': 'javascript:alert(1)'
        }, headers=self.admin_headers)
        self.assertEqual(res2.status_code, 400)
        self.assertIn('Invalid URL scheme', res2.get_json().get('message', ''))

        res3 = self.client.post('/api/admin/menu', json={
            'name': 'Test Item Scheme 2',
            'price': '10.00',
            'category': 'Test',
            'business_type': 'home_foods',
            'image_url': 'http://example.com/image.png'
        }, headers=self.admin_headers)
        self.assertEqual(res3.status_code, 201)

if __name__ == '__main__':
    unittest.main()
