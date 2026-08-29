import unittest
from decimal import Decimal
from flask_jwt_extended import create_access_token

# Adjust these imports to match your actual project structure
from app import create_app, db, bcrypt
from models import User, Order, Outlet, Address, SupportTicket, Review, MenuItem

class TestIDORVulnerabilities(unittest.TestCase):
    def setUp(self):
        # 1. Initialize the app with an isolated in-memory test database
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # 2. Create the tables
        db.create_all()

        # 3. Set up prerequisites (Outlet and Menu Item)
        self.outlet = Outlet(name="Test Outlet", address="123 Main St")
        db.session.add(self.outlet)
        
        self.menu_item = MenuItem(name="Test Burger", price=Decimal("150.00"), business_type="both")
        db.session.add(self.menu_item)
        db.session.commit()

        # ==========================================
        # 4. CREATE USER A (The "Attacker" / Tester)
        # ==========================================
        self.attacker = User(email="attacker@test.com", role="customer", first_name="Attacker")
        self.attacker.set_password("pass123", bcrypt)
        db.session.add(self.attacker)
        db.session.commit()

        # Generate token for Attacker
        attacker_token = create_access_token(
            identity=str(self.attacker.id), 
            additional_claims={"role": "customer", "token_version": getattr(self.attacker, "token_version", 0)}
        )
        self.attacker_headers = {
            "Authorization": f"Bearer {attacker_token}",
            "Content-Type": "application/json"
        }

        # ==========================================
        # 5. CREATE USER B (The "Victim") & THEIR DATA
        # ==========================================
        self.victim = User(email="victim@test.com", role="customer", first_name="Victim")
        self.victim.set_password("pass123", bcrypt)
        db.session.add(self.victim)
        db.session.commit()

        # Victim's Address
        self.victim_address = Address(user_id=self.victim.id, title="Home", address_line="456 Victim Lane")
        db.session.add(self.victim_address)

        # Victim's Order
        self.victim_order = Order(
            customer_id=self.victim.id, 
            outlet_id=self.outlet.id, 
            status="pending",
            total_price=Decimal("150.00")
        )
        db.session.add(self.victim_order)

        # Victim's Support Ticket
        # Victim's Support Ticket
        self.victim_ticket = SupportTicket(
            customer_id=self.victim.id, 
            issue_type="Missing Item", 
            description="Where is my food?"
        )
        db.session.add(self.victim_ticket)

        # Victim's Review
        self.victim_review = Review(
            customer_id=self.victim.id,
            menu_item_id=self.menu_item.id,
            rating=5,
            comment="Great food!"
        )
        db.session.add(self.victim_review)
        
        db.session.commit()

    def tearDown(self):
        # Clean up database after each test
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # ==========================================
    # ACTUAL IDOR TESTS
    # ==========================================

    def test_idor_delete_other_user_address(self):
        """Test if Attacker can delete Victim's saved address"""
        resp = self.client.delete(
            f"/api/auth/addresses/{self.victim_address.id}",
            headers=self.attacker_headers
        )
        # Should return 404 (Not Found) because the endpoint should only look up addresses belonging to current_user
        self.assertIn(resp.status_code, (403, 404), "IDOR Vulnerability: Attacker deleted victim's address!")

    def test_idor_cancel_other_user_order(self):
        """Test if Attacker can cancel Victim's pending order"""
        resp = self.client.post(
            f"/api/foods/orders/{self.victim_order.id}/cancel",
            json={"reason": "IDOR test cancellation"},
            headers=self.attacker_headers
        )
        # Should return 403 (Forbidden) or 404
        self.assertIn(resp.status_code, (403, 404), "IDOR Vulnerability: Attacker cancelled victim's order!")

    def test_idor_update_other_user_ticket(self):
        """Test if Attacker can modify Victim's support ticket"""
        resp = self.client.put(
            f"/api/customer/tickets/{self.victim_ticket.id}",
            json={"description": "Attacker modified this ticket"},
            headers=self.attacker_headers
        )
        self.assertIn(resp.status_code, (403, 404), "IDOR Vulnerability: Attacker updated victim's support ticket!")

    def test_idor_delete_other_user_ticket(self):
        """Test if Attacker can delete Victim's support ticket"""
        resp = self.client.delete(
            f"/api/customer/tickets/{self.victim_ticket.id}",
            headers=self.attacker_headers
        )
        self.assertIn(resp.status_code, (403, 404), "IDOR Vulnerability: Attacker deleted victim's support ticket!")

    def test_idor_delete_other_user_review(self):
        """Test if Attacker can delete Victim's review"""
        resp = self.client.delete(
            f"/api/customer/reviews/{self.victim_review.id}",
            headers=self.attacker_headers
        )
        self.assertIn(resp.status_code, (403, 404), "IDOR Vulnerability: Attacker deleted victim's review!")