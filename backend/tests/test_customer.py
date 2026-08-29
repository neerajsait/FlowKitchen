import unittest
from app import create_app, db, bcrypt
from models import User, Outlet, MenuItem, Order, OrderItem, SupportTicket

class CustomerTestCase(unittest.TestCase):
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
        self.outlet = Outlet(name="Customer Outlet", address="123 Customer St")
        db.session.add(self.outlet)
        db.session.commit()

        # Setup Customer
        self.customer = User(email="customer@test.com", first_name="Customer", role="customer")
        self.customer.set_password("customerpass", bcrypt)
        self.customer.loyalty_points = 150
        db.session.add(self.customer)
        db.session.commit()

        # Setup Menu Item
        self.item = MenuItem(name="Pizza", price=20.00, category="Main", code="C001", business_type="both")
        db.session.add(self.item)
        db.session.commit()

        # Add an order for the customer
        self.order = Order(outlet_id=self.outlet.id, customer_id=self.customer.id, status="delivered")
        self.order.order_type = "b2c"
        db.session.add(self.order)
        db.session.commit()
        
        self.order_item = OrderItem(order_id=self.order.id, menu_item_id=self.item.id, quantity=1, price=20.00)
        db.session.add(self.order_item)
        db.session.commit()

        # Add a support ticket for the customer
        self.ticket = SupportTicket(customer_id=self.customer.id, issue_type="Payment", description="Help me")
        db.session.add(self.ticket)
        db.session.commit()

        # Get Token
        resp_cust = self.client.post("/api/auth/login", json={"email": "customer@test.com", "password": "customerpass"})
        self.customer_headers = {"Authorization": f"Bearer {resp_cust.json['access_token']}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_customer_get_orders(self):
        resp = self.client.get("/api/foods/orders", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 1)

    def test_customer_get_me(self):
        resp = self.client.get("/api/auth/me", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["loyalty_points"], 150)

    def test_customer_create_ticket(self):
        resp = self.client.post("/api/customer/tickets", json={
            "issue_type": "Bug",
            "description": "I need help with my order"
        }, headers=self.customer_headers)
        self.assertEqual(resp.status_code, 201)
        
    def test_customer_get_tickets(self):
        resp = self.client.get("/api/customer/tickets", headers=self.customer_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 1)

    def test_customer_update_ticket(self):
        resp = self.client.put(f"/api/customer/tickets/{self.ticket.id}", json={
            "description": "Thank you"
        }, headers=self.customer_headers)
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
