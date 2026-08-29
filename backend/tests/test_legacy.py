import unittest
from decimal import Decimal
from app import create_app, db, bcrypt
from models import User, Admin, Customer, Staff, Outlet, MenuItem, Order, OrderItem, Review, OutletStock

class BackendTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app to use an in-memory database and disable rate limiting for tests
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": False,
            "SECRET_KEY": "a-very-long-and-highly-secure-test-secret-key-32-bytes",
            "JWT_SECRET_KEY": "a-very-long-and-highly-secure-test-jwt-secret-key-32-bytes"
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create all tables
        db.create_all()
        
        # Setup initial test data
        self.setup_initial_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def setup_initial_data(self):
        # Clear any auto-seeded records to ensure test isolation
        db.session.query(Review).delete()
        db.session.query(OrderItem).delete()
        db.session.query(Order).delete()
        db.session.query(OutletStock).delete()
        db.session.query(MenuItem).delete()
        db.session.query(Outlet).delete()
        db.session.query(User).delete()
        db.session.commit()

        # Create a test outlet
        self.outlet = Outlet(name="Downtown Snacks", address="123 Main St")
        db.session.add(self.outlet)
        db.session.commit()  # commit to get the outlet ID

        # Create admin, customer, and staff users
        self.admin = Admin(email="admin@brand.com")
        self.admin.is_superadmin = True
        self.admin.set_password("adminpass", bcrypt)

        self.customer = Customer(email="customer@gmail.com")
        self.customer.is_email_verified = True
        self.customer.set_password("custpass1", bcrypt)

        self.staff = Staff(email="staff@brand.com", outlet_id=self.outlet.id)
        self.staff.set_password("staffpass", bcrypt)

        # Create menu items
        self.item_foods = MenuItem(name="Biryani", price=Decimal("12.50"), business_type="home_foods")
        self.item_snacks = MenuItem(name="Samosa", price=Decimal("1.50"), business_type="snack_supply")
        self.item_both = MenuItem(name="Soft Drink", price=Decimal("2.00"), business_type="both")

        db.session.add_all([self.admin, self.customer, self.staff, self.item_foods, self.item_snacks, self.item_both])
        db.session.commit()

        # Seed the outlet inventory stock (assign self.item_snacks with stock 15, limit 10)
        self.stock_record = OutletStock(
            outlet_id=self.outlet.id,
            menu_item_id=self.item_snacks.id,
            current_stock=15,
            restock_limit=10
        )
        db.session.add(self.stock_record)
        db.session.commit()

    def get_jwt_headers(self, email, password):
        """Helper to login and get JWT Authorization header"""
        resp = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(resp.status_code, 200)
        token = resp.json["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_rbac_access_control(self):
        # Obtain tokens
        customer_headers = self.get_jwt_headers("customer@gmail.com", "custpass1")
        staff_headers = self.get_jwt_headers("staff@brand.com", "staffpass")
        admin_headers = self.get_jwt_headers("admin@brand.com", "adminpass")

        # 1. Customer attempts to access Admin orders queue -> Should be Forbidden (403)
        resp = self.client.get("/api/admin/orders", headers=customer_headers)
        self.assertEqual(resp.status_code, 403)

        # 2. Staff attempts to access Admin outlets queue -> Should be Forbidden (403)
        resp = self.client.get("/api/admin/outlets", headers=staff_headers)
        self.assertEqual(resp.status_code, 403)

        # 3. Customer attempts to access POS sell -> Should be Forbidden (403)
        resp = self.client.post("/api/pos/sell", json={"items": [], "payment_method": "cash"}, headers=customer_headers)
        self.assertEqual(resp.status_code, 403)

        # 4. Admin accesses Admin outlets queue -> Should be OK (200)
        resp = self.client.get("/api/admin/outlets", headers=admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 1)

    def test_b2c_home_foods_order_and_feedback_flow(self):
        customer_headers = self.get_jwt_headers("customer@gmail.com", "custpass1")
        admin_headers = self.get_jwt_headers("admin@brand.com", "adminpass")

        # 1. Customer places order
        order_payload = {
            "items": [
                {"menu_item_id": self.item_foods.id, "quantity": 2},
                {"menu_item_id": self.item_both.id, "quantity": 3}
            ]
        }
        resp = self.client.post("/api/foods/order", json=order_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 201)
        order_id = resp.json["order"]["id"]
        self.assertEqual(resp.json["order"]["status"], "pending")
        self.assertEqual(resp.json["order"]["total_price"], 31.00) # (12.5*2) + (2*3) = 31

        # 2. Customer attempts to submit feedback for pending order -> Should be Forbidden (403)
        feedback_payload = {"rating": 5, "comment": "Excellent Biryani!"}
        resp = self.client.post(f"/api/foods/orders/{order_id}/feedback", json=feedback_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Feedback form is locked", resp.json["message"])

        # 3. Admin ships the order and inputs tracking code
        ship_payload = {"tracking_code": "TRACK_XYZ_789"}
        resp = self.client.put(f"/api/admin/orders/{order_id}/ship", json=ship_payload, headers=admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["order"]["status"], "shipped")
        self.assertEqual(resp.json["order"]["tracking_code"], "TRACK_XYZ_789")

        delivery_code = resp.json["order"]["delivery_confirmation_code"]

        # 4. Customer attempts to submit feedback before confirming delivery -> Should still be Forbidden (403)
        resp = self.client.post(f"/api/foods/orders/{order_id}/feedback", json=feedback_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 403)

        # 5. Customer confirms receipt with WRONG tracking code -> Should be Unauthorized (401)
        resp = self.client.post(f"/api/foods/orders/{order_id}/confirm", json={"tracking_code": "WRONG_CODE"}, headers=customer_headers)
        self.assertEqual(resp.status_code, 401)

        # 6. Customer confirms receipt with MATCHING delivery confirmation code -> Should be OK (200)
        resp = self.client.post(f"/api/foods/orders/{order_id}/confirm", json={"tracking_code": delivery_code}, headers=customer_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json["order"]["is_received"])
        self.assertEqual(resp.json["order"]["status"], "delivered")

        # 7. Customer submits feedback -> Should be Created (201)
        resp = self.client.post(f"/api/foods/orders/{order_id}/feedback", json=feedback_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json["feedback"]["rating"], 5)
        self.assertEqual(resp.json["feedback"]["comment"], "Excellent Biryani!")

        # 8. Customer attempts duplicate feedback submission -> Should be Conflict (409)
        resp = self.client.post(f"/api/foods/orders/{order_id}/feedback", json=feedback_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 409)

    def test_b2b2c_snack_supply_inventory_and_alert_flow(self):
        staff_headers = self.get_jwt_headers("staff@brand.com", "staffpass")
        admin_headers = self.get_jwt_headers("admin@brand.com", "adminpass")

        # Initial outlet stock is 15. Restock limit is 10.
        # 1. Staff does POS sale of 4 Samosas (total sold = 4, remaining stock = 11)
        sale_payload = {
            "items": [{"menu_item_id": self.item_snacks.id, "quantity": 4}],
            "payment_method": "scanner"
        }
        resp = self.client.post("/api/pos/sell", json=sale_payload, headers=staff_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json["remaining_stock"], 11)
        self.assertFalse(resp.json["restock_alert"])

        # 2. Admin checks outlets -> Needs restock should be False
        resp = self.client.get("/api/admin/outlets", headers=admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json[0]["needs_restock"])

        # 3. Staff does POS sale of 2 Samosas (total sold = 6, remaining stock = 9 <= restock limit of 10)
        sale_payload2 = {
            "items": [{"menu_item_id": self.item_snacks.id, "quantity": 2}],
            "payment_method": "cash"
        }
        resp = self.client.post("/api/pos/sell", json=sale_payload2, headers=staff_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json["remaining_stock"], 9)
        self.assertTrue(resp.json["restock_alert"]) # Flagged on completion

        # 4. Admin checks outlets dashboard -> Outlet should be flagged for restocking
        resp = self.client.get("/api/admin/outlets", headers=admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json[0]["needs_restock"]) # Needs restock is True!

        # 5. Staff attempts to make a POS sale exceeding stock (quantity = 10, available = 9) -> Should fail (409)
        sale_payload3 = {
            "items": [{"menu_item_id": self.item_snacks.id, "quantity": 10}],
            "payment_method": "cash"
        }
        resp = self.client.post("/api/pos/sell", json=sale_payload3, headers=staff_headers)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Insufficient stock", resp.json["message"])
    def test_staff_registration_restrictions(self):
        admin_headers = self.get_jwt_headers("admin@brand.com", "adminpass")
        customer_headers = self.get_jwt_headers("customer@gmail.com", "custpass1")

        # 1. Self-registration must lock the role to "customer" and ignore other role specs
        register_payload = {
            "email": "new_staff_try@brand.com",
            "password": "somepassword1",
            "role": "staff",
            "outlet_id": self.outlet.id
        }
        resp = self.client.post("/api/auth/register", json=register_payload)
        self.assertEqual(resp.status_code, 201)
        user = db.session.query(User).filter_by(email="new_staff_try@brand.com").first()
        self.assertEqual(user.role, "customer") 
        self.assertIsNone(user.outlet_id)

        # 2. Customer attempts to access Admin staff creation route -> Should be Forbidden (403)
        admin_staff_payload = {
            "email": "real_staff@brand.com",
            "password": "staffpassword",
            "first_name": "Real",
            "last_name": "Staff",
            "outlet_id": self.outlet.id,
            "phone": "1234567890",
            "pin": "1234"
        }
        resp = self.client.post("/api/admin/staff", json=admin_staff_payload, headers=customer_headers)
        self.assertEqual(resp.status_code, 403)

        # 3. Admin creates a staff member successfully -> Should be Created (201)
        resp = self.client.post("/api/admin/staff", json=admin_staff_payload, headers=admin_headers)
        if resp.status_code != 201:
            print("ERROR response:", resp.get_json(), flush=True)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json["user"]["role"], "staff")
        self.assertEqual(resp.json["user"]["outlet_id"], self.outlet.id)


if __name__ == "__main__":
    unittest.main()
