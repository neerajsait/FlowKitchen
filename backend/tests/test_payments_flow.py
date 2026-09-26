import json
import hmac
import hashlib
import unittest
from unittest import mock

from app import create_app, db, bcrypt, clear_razorpay_cache
from models import User, Order, PaymentTransaction


KEY_ID = "rzp_test_unit111111"
KEY_SECRET = "unit_test_key_secret"
WEBHOOK_SECRET = "unit_test_webhook_secret"


class PaymentsFlowTestCase(unittest.TestCase):
    def setUp(self):
        # Razorpay creds resolved via the documented env-var fallback
        import os
        self._env_backup = {k: os.environ.get(k) for k in
                            ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_ENABLED", "RAZORPAY_WEBHOOK_SECRET")}
        os.environ["RAZORPAY_KEY_ID"] = KEY_ID
        os.environ["RAZORPAY_KEY_SECRET"] = KEY_SECRET
        os.environ["RAZORPAY_ENABLED"] = "true"
        os.environ["RAZORPAY_WEBHOOK_SECRET"] = WEBHOOK_SECRET

        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "RATELIMIT_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "JWT_SECRET_KEY": "a-very-long-test-jwt-secret-key-32-bytes",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        clear_razorpay_cache()

        db.create_all()

        self.customer = User(email="cust@test.com", full_name="Cust", role="customer")
        self.customer.set_password("custpass", bcrypt)
        self.other = User(email="other@test.com", full_name="Other", role="customer")
        self.other.set_password("otherpass", bcrypt)
        db.session.add_all([self.customer, self.other])
        db.session.commit()

        r = self.client.post("/api/auth/login", json={"email": "cust@test.com", "password": "custpass"})
        self.headers = {"Authorization": f"Bearer {r.json['access_token']}"}
        r2 = self.client.post("/api/auth/login", json={"email": "other@test.com", "password": "otherpass"})
        self.other_headers = {"Authorization": f"Bearer {r2.json['access_token']}"}

        self.order = Order(order_type="online", customer_id=self.customer.id,
                           status="pending", total_price=250.00, payment_method="ONLINE")
        db.session.add(self.order)
        db.session.commit()

    def tearDown(self):
        import os
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        clear_razorpay_cache()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _checkout_signature(self, rp_order_id, rp_payment_id):
        return hmac.new(KEY_SECRET.encode(), f"{rp_order_id}|{rp_payment_id}".encode(),
                        hashlib.sha256).hexdigest()

    def _webhook_signature(self, raw_bytes):
        return hmac.new(WEBHOOK_SECRET.encode(), raw_bytes, hashlib.sha256).hexdigest()

    def _select(self, stmt):
        from sqlalchemy import select as _s
        # .unique() is required because Order uses lazy='joined' collections
        return db.session.scalars(_s(stmt)).unique().all()

    # ------------------------------------------------------------------
    # POST /api/payments/razorpay/order
    # ------------------------------------------------------------------
    def test_create_razorpay_order_persists_rp_order_id(self):
        fake_resp = mock.Mock(status_code=201)
        fake_resp.json.return_value = {"id": "order_RP123", "amount": 25000, "currency": "INR"}
        with mock.patch("requests.post", return_value=fake_resp) as mp:
            r = self.client.post("/api/payments/razorpay/order",
                                 headers=self.headers, json={"order_id": self.order.id})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(r.json["razorpay_order_id"], "order_RP123")
        self.assertEqual(r.json["key_id"], KEY_ID)  # public key exposed, secret never
        _, kwargs = mp.call_args
        self.assertEqual(kwargs["auth"], (KEY_ID, KEY_SECRET))
        self.assertEqual(kwargs["json"]["amount"], 25000)  # paise
        fresh = self._select(Order)[0]
        self.assertEqual(fresh.razorpay_order_id, "order_RP123")
        txns = self._select(PaymentTransaction)
        self.assertTrue(any(t.event == "order_created" and t.status == "created" for t in txns))

    def test_create_order_requires_auth(self):
        r = self.client.post("/api/payments/razorpay/order", json={"order_id": self.order.id})
        self.assertEqual(r.status_code, 401)

    def test_create_order_rejects_foreign_order(self):
        r = self.client.post("/api/payments/razorpay/order",
                             headers=self.other_headers, json={"order_id": self.order.id})
        self.assertEqual(r.status_code, 404)
    # ------------------------------------------------------------------
    # POST /api/payments/razorpay/verify
    # ------------------------------------------------------------------
    def test_verify_missing_fields(self):
        r = self.client.post("/api/payments/razorpay/verify", headers=self.headers, json={})
        self.assertEqual(r.status_code, 400)

    def test_verify_wrong_owner_404(self):
        sig = self._checkout_signature("order_X1", "pay_X1")
        r = self.client.post("/api/payments/razorpay/verify", headers=self.other_headers,
                             json={"order_id": self.order.id, "razorpay_order_id": "order_X1",
                                   "razorpay_payment_id": "pay_X1", "razorpay_signature": sig})
        self.assertEqual(r.status_code, 404)

    def test_verify_valid_signature_marks_paid(self):
        sig = self._checkout_signature("order_OK1", "pay_OK1")
        r = self.client.post("/api/payments/razorpay/verify", headers=self.headers,
                             json={"order_id": self.order.id, "razorpay_order_id": "order_OK1",
                                   "razorpay_payment_id": "pay_OK1", "razorpay_signature": sig})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertFalse(r.json["already_paid"])
        self.assertEqual(r.json["order"]["payment_status"], "paid")
        fresh = self._select(Order)[0]
        self.assertEqual(fresh.payment_status, "paid")
        self.assertIsNotNone(fresh.paid_at)
        self.assertEqual(fresh.razorpay_payment_id, "pay_OK1")
        checkouts = [t for t in self._select(PaymentTransaction) if t.event == "checkout_verify"]
        self.assertTrue(checkouts and checkouts[0].signature_valid)

    def test_verify_invalid_signature_rejected(self):
        r = self.client.post("/api/payments/razorpay/verify", headers=self.headers,
                             json={"order_id": self.order.id, "razorpay_order_id": "order_BAD",
                                   "razorpay_payment_id": "pay_BAD", "razorpay_signature": "deadbeef"})
        self.assertEqual(r.status_code, 400)
        fresh = self._select(Order)[0]
        self.assertNotEqual(fresh.payment_status, "paid")
        txns = self._select(PaymentTransaction)
        self.assertTrue(txns and not txns[0].signature_valid)
    def test_verify_is_idempotent_after_paid(self):
        sig = self._checkout_signature("order_OK1", "pay_OK1")
        body = {"order_id": self.order.id, "razorpay_order_id": "order_OK1",
                "razorpay_payment_id": "pay_OK1", "razorpay_signature": sig}
        r1 = self.client.post("/api/payments/razorpay/verify", headers=self.headers, json=body)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post("/api/payments/razorpay/verify", headers=self.headers, json=body)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json["already_paid"])

    def test_verify_order_id_mismatch_rejected(self):
        self.order.razorpay_order_id = "order_REAL"
        db.session.commit()
        sig = self._checkout_signature("order_FAKE", "pay_FAKE")
        r = self.client.post("/api/payments/razorpay/verify", headers=self.headers,
                             json={"order_id": self.order.id, "razorpay_order_id": "order_FAKE",
                                   "razorpay_payment_id": "pay_FAKE", "razorpay_signature": sig})
        self.assertEqual(r.status_code, 400)

    # ------------------------------------------------------------------
    # POST /api/payments/razorpay/webhook
    # ------------------------------------------------------------------
    def _webhook_payload(self, event="payment.captured"):
        return {
            "event": event,
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_WH1",
                        "order_id": "order_RP9",
                        "amount": 25000,
                        "currency": "INR",
                        "notes": {"order_id": str(self.order.id)},
                    }
                }
            },
        }

    def _post_webhook(self, payload):
        body = json.dumps(payload).encode()
        return self.client.post("/api/payments/razorpay/webhook", data=body,
                                content_type="application/json",
                                headers={"X-Razorpay-Signature": self._webhook_signature(body)})
    def test_webhook_invalid_signature_rejected(self):
        body = json.dumps(self._webhook_payload()).encode()
        r = self.client.post("/api/payments/razorpay/webhook", data=body,
                             content_type="application/json",
                             headers={"X-Razorpay-Signature": "tampered"})
        self.assertEqual(r.status_code, 400)

    def test_webhook_captured_marks_paid(self):
        r = self._post_webhook(self._webhook_payload())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.json["status"], "ok")
        fresh = self._select(Order)[0]
        self.assertEqual(fresh.payment_status, "paid")
        webhooks = [t for t in self._select(PaymentTransaction) if t.source == "webhook"]
        self.assertTrue(webhooks and webhooks[0].status == "captured")

    def test_webhook_failed_event_records_failure(self):
        r = self._post_webhook(self._webhook_payload(event="payment.failed"))
        self.assertEqual(r.status_code, 200)
        fresh = self._select(Order)[0]
        self.assertEqual(fresh.payment_status, "failed")

    def test_webhook_unknown_order_still_audited(self):
        payload = self._webhook_payload()
        payload["payload"]["payment"]["entity"]["notes"] = {}
        payload["payload"]["payment"]["entity"]["order_id"] = "order_UNKNOWN"
        r = self._post_webhook(payload)
        self.assertEqual(r.status_code, 200)
        orphans = [t for t in self._select(PaymentTransaction) if t.source == "webhook"]
        self.assertTrue(any(t.order_id is None for t in orphans))


if __name__ == "__main__":
    unittest.main()
