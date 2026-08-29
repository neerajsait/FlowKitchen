import unittest
from app import create_app, db, bcrypt
from models import Customer, Staff, Outlet, MenuItem, OutletStock, Order, OrderItem

class PosOrdersTestCase(unittest.TestCase):
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
        
        # 1. Setup Outlet
        self.outlet = Outlet(name="Test Outlet", address="123 Test St")
        db.session.add(self.outlet)
        db.session.commit()

        # 2. Setup Staff for POS
        self.staff = Staff(email="staff@test.com", first_name="Staff", outlet_id=self.outlet.id)
        self.staff.set_password("staffpass", bcrypt)
        db.session.add(self.staff)
        db.session.commit()

        # 3. Setup Customer for Orders
        self.customer = Customer(email="customer@test.com", first_name="Cust")
        self.customer.is_email_verified = True
        self.customer.set_password("custpass", bcrypt)
        db.session.add(self.customer)
        db.session.commit()

        # 4. Setup Menu Item and Stock
        self.item = MenuItem(name="Burger", price=10.00, category="Main", code="B001", business_type="both")
        db.session.add(self.item)
        db.session.commit()

        self.stock = OutletStock(outlet_id=self.outlet.id, menu_item_id=self.item.id, current_stock=50, restock_limit=10)
        db.session.add(self.stock)
        db.session.commit()

        # 5. Get Tokens
        resp_staff = self.client.post("/api/auth/login", json={"email": "staff@test.com", "password": "staffpass"})
        self.staff_headers = {"Authorization": f"Bearer {resp_staff.json['access_token']}"}

        resp_cust = self.client.post("/api/auth/login", json={"email": "customer@test.com", "password": "custpass"})
        self.cust_headers = {"Authorization": f"Bearer {resp_cust.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- POS Tests ---
    def test_pos_sell_success(self):
        resp = self.client.post("/api/pos/sell", json={
            "items": [
                {"menu_item_id": self.item.id, "quantity": 2}
            ],
            "payment_method": "card"
        }, headers=self.staff_headers)
        self.assertIn(resp.status_code, [200, 201])
        
        # Verify stock decreased
        db.session.refresh(self.stock)
        self.assertEqual(self.stock.current_stock, 48)

    def test_pos_sell_insufficient_stock(self):
        resp = self.client.post("/api/pos/sell", json={
            "items": [
                {"menu_item_id": self.item.id, "quantity": 100}
            ]
        }, headers=self.staff_headers)
        self.assertEqual(resp.status_code, 409) # Conflict

    # --- Customer Orders Tests ---
    def test_customer_create_order(self):
        resp = self.client.post("/api/foods/order", json={
            "outlet_id": self.outlet.id,
            "items": [
                {"menu_item_id": self.item.id, "quantity": 1}
            ],
            "delivery_address": "456 Cust Home",
            "type": "delivery"
        }, headers=self.cust_headers)
        self.assertIn(resp.status_code, [200, 201])
        self.order_id = resp.json.get("order", {}).get("id") or resp.json.get("id")

    def test_customer_get_orders(self):
        # Create an order first
        order = Order(
            customer_id=self.customer.id,
            outlet_id=self.outlet.id,
            status="pending"
        )
        order.type = "delivery"
        order.delivery_address = "123 Home"
        db.session.add(order)
        db.session.commit()

        resp = self.client.get("/api/foods/orders", headers=self.cust_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.json), 0)

    # --- Order Lifecycle & Feedback ---
    def test_customer_confirm_and_feedback(self):
        # Create order in 'delivered' or 'completed' state so feedback is allowed
        order = Order(
            customer_id=self.customer.id,
            outlet_id=self.outlet.id,
            status="delivered"
        )
        order.is_received = True
        order.type = "delivery"
        order.delivery_address = "123 Home"
        db.session.add(order)
        db.session.commit()

        # Confirm (if confirm means they received it, some systems use this)
        # Assuming status=delivered is enough for feedback
        resp_fb = self.client.post(f"/api/foods/orders/{order.id}/feedback", json={
            "rating": 5,
            "comment": "Great food!"
        }, headers=self.cust_headers)
        self.assertIn(resp_fb.status_code, [200, 201])
        
        # Test conflict if feedback already exists
        resp_fb2 = self.client.post(f"/api/foods/orders/{order.id}/feedback", json={
            "rating": 4
        }, headers=self.cust_headers)
        self.assertEqual(resp_fb2.status_code, 409)


    def test_coupon_usage_atomic(self):
        # Create a coupon
        from models import Coupon
        coupon = Coupon(code="ATOMIC10", discount_pct=10, usage_limit=1)
        db.session.add(coupon)
        db.session.commit()
        
        # Test applying it twice - only one should succeed if we were running concurrently, 
        # but since we test serially, we just verify it fails on second try
        res = self.client.post('/api/pos/sell', json={
            "items": [{"menu_item_id": self.item.id, "quantity": 1}],
            "payment_method": "Cash",
            "coupon_code": "ATOMIC10"
        }, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        
        res2 = self.client.post('/api/pos/sell', json={
            "items": [{"menu_item_id": self.item.id, "quantity": 1}],
            "payment_method": "Cash",
            "coupon_code": "ATOMIC10"
        }, headers=self.staff_headers)
        self.assertEqual(res2.status_code, 400)

    def test_dispose_stock_atomic(self):
        # Current stock is 50. Let's dispose 50, then try to dispose 1 more.
        res = self.client.post('/api/pos/disposal', json={
            "menu_item_id": self.item.id,
            "quantity": 50,
            "reason": "Test"
        }, headers=self.staff_headers)
        self.assertEqual(res.status_code, 200)

        res2 = self.client.post('/api/pos/disposal', json={
            "menu_item_id": self.item.id,
            "quantity": 1,
            "reason": "Test"
        }, headers=self.staff_headers)
        self.assertIn(res2.status_code, [400, 409])


