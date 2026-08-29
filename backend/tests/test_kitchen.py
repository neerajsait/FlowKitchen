import unittest
from app import create_app, db, bcrypt
from models import Staff, KitchenStaff, Outlet, MenuItem, OutletStock, Order, OrderItem

class KitchenTestCase(unittest.TestCase):
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
        self.outlet = Outlet(name="Kitchen Outlet", address="123 Kitchen St")
        db.session.add(self.outlet)
        db.session.commit()

        # Setup Kitchen Staff
        self.staff = KitchenStaff(email="kitchen@test.com", first_name="Kitchen", outlet_id=self.outlet.id)
        self.staff.set_password("kitchenpass", bcrypt)
        db.session.add(self.staff)
        db.session.commit()

        # Setup Menu Item
        self.item = MenuItem(name="Burger", price=15.00, category="Main", code="K001", business_type="both")
        db.session.add(self.item)
        db.session.commit()

        self.stock = OutletStock(outlet_id=self.outlet.id, menu_item_id=self.item.id, current_stock=5, restock_limit=10)
        db.session.add(self.stock)
        db.session.commit()

        # Add pending order for kitchen
        self.order = Order(outlet_id=self.outlet.id, status="pending")
        self.order.type = "delivery"
        db.session.add(self.order)
        db.session.commit()
        
        self.order_item = OrderItem(order_id=self.order.id, menu_item_id=self.item.id, quantity=2, price=15.00)
        db.session.add(self.order_item)
        db.session.commit()

        # Get Token
        resp_staff = self.client.post("/api/auth/login", json={"email": "kitchen@test.com", "password": "kitchenpass"})
        self.kitchen_headers = {"Authorization": f"Bearer {resp_staff.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_kitchen_get_orders(self):
        resp = self.client.get("/api/kitchen/orders", headers=self.kitchen_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 1)

    def test_kitchen_update_order_status(self):
        resp = self.client.put(f"/api/kitchen/orders/{self.order.id}/status", json={"status": "processing"}, headers=self.kitchen_headers)
        self.assertEqual(resp.status_code, 200)
        
        db.session.refresh(self.order)
        self.assertEqual(self.order.status, "processing")

    def test_kitchen_get_restock_requests(self):
        resp = self.client.get("/api/kitchen/stock-requests", headers=self.kitchen_headers)
        self.assertEqual(resp.status_code, 200)
        
    def test_kitchen_produce_batch(self):
        resp = self.client.post("/api/kitchen/produce", json={
            "menu_item_id": self.item.id,
            "quantity": 20,
            "expiry_date": "2027-12-31"
        }, headers=self.kitchen_headers)
        self.assertEqual(resp.status_code, 201)

if __name__ == '__main__':
    unittest.main()
