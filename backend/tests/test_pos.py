import unittest
from app import create_app, db, bcrypt
from models import Staff, Outlet, MenuItem, OutletStock

class PosTestCase(unittest.TestCase):
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
        
        # Setup Outlet
        self.outlet = Outlet(name="Test POS Outlet", address="123 Test St")
        db.session.add(self.outlet)
        db.session.commit()

        # Setup Staff for POS
        self.staff = Staff(email="staff@pos.com", first_name="Staff", outlet_id=self.outlet.id)
        self.staff.set_password("pospass", bcrypt)
        self.staff.set_pin("1234", bcrypt)
        db.session.add(self.staff)
        db.session.commit()

        # Setup Menu Item and Stock
        self.item = MenuItem(name="Pizza", price=20.00, category="Main", code="P001", business_type="both")
        db.session.add(self.item)
        db.session.commit()

        self.stock = OutletStock(outlet_id=self.outlet.id, menu_item_id=self.item.id, current_stock=20, restock_limit=5)
        db.session.add(self.stock)
        db.session.commit()

        # Get Tokens
        resp_staff = self.client.post("/api/auth/login", json={"email": "staff@pos.com", "password": "pospass"})
        self.staff_headers = {"Authorization": f"Bearer {resp_staff.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_pos_get_outlet(self):
        resp = self.client.get("/api/pos/outlet", headers=self.staff_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["id"], self.outlet.id)

    def test_pos_get_menu(self):
        resp = self.client.get("/api/pos/menu", headers=self.staff_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json) >= 1)

    def test_pos_shift_lifecycle(self):
        # Clock in
        resp = self.client.post("/api/pos/shift/clock-in", json={"email": "staff@pos.com", "pin": "1234"}, headers=self.staff_headers)
        if resp.status_code != 201:
            print("ERROR response:", resp.json)
        self.assertEqual(resp.status_code, 201)
        
        # Get active shift
        resp_active = self.client.get("/api/pos/shift/active", headers=self.staff_headers)
        self.assertEqual(resp_active.status_code, 200)
        self.assertIsNotNone(resp_active.json)
        
        # Clock out
        resp_out = self.client.post("/api/pos/shift/clock-out", json={"notes": "End of day", "actual_cash": 0}, headers=self.staff_headers)
        self.assertEqual(resp_out.status_code, 200)
        
        # No active shift
        resp_active2 = self.client.get("/api/pos/shift/active", headers=self.staff_headers)
        self.assertEqual(resp_active2.status_code, 200)
        self.assertIsNone(resp_active2.json["shift"])

    def test_pos_customer_lookup(self):
        resp = self.client.get("/api/pos/customer/lookup?email=missing@test.com", headers=self.staff_headers)
        self.assertEqual(resp.status_code, 404)
        
    def test_pos_sales_history(self):
        resp = self.client.get("/api/pos/sales/history", headers=self.staff_headers)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
