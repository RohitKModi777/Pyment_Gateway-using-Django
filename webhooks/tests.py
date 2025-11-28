import hmac
import json
import hashlib
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from store.models import Order, Product, Transaction
from webhooks.models import WebhookLog

@override_settings(RAZORPAY_KEY_SECRET="testsecret", WEBHOOK_SECRET="testsecret")
class WebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="buyer", email="buyer@example.com", password="pass1234")
        self.product = Product.objects.create(
            title="Demo Product",
            slug="demo-product",
            description="desc",
            price_cents=1500,
            inventory=5,
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount_cents=1500,
            razorpay_order_id="order_123",
        )

    def _get_signature(self, payload):
        body = json.dumps(payload).encode()
        return hmac.new(b"testsecret", body, digestmod=hashlib.sha256).hexdigest()

    def test_payment_captured(self):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "order_id": "order_123",
                        "id": "pay_123",
                        "status": "captured",
                        "amount": 1500,
                    }
                }
            },
        }
        signature = self._get_signature(payload)
        response = self.client.post(
            reverse("webhooks:razorpay-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAID)
        self.assertTrue(Transaction.objects.filter(reference="pay_123", status=Transaction.STATUS_SUCCESS).exists())

    def test_payment_failed(self):
        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "order_id": "order_123",
                        "id": "pay_fail_123",
                        "status": "failed",
                        "amount": 1500,
                    }
                }
            },
        }
        signature = self._get_signature(payload)
        response = self.client.post(
            reverse("webhooks:razorpay-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_FAILED)
        self.assertTrue(Transaction.objects.filter(reference="pay_fail_123", status=Transaction.STATUS_FAILED).exists())

    def test_refund_processed(self):
        # First mark order as paid
        self.order.status = Order.STATUS_PAID
        self.order.razorpay_payment_id = "pay_123"
        self.order.save()

        payload = {
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_123",
                        "payment_id": "pay_123",
                        "status": "processed",
                        "amount": 500,
                    }
                }
            },
        }
        signature = self._get_signature(payload)
        response = self.client.post(
            reverse("webhooks:razorpay-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.filter(reference="rfnd_123", amount_cents=500).exists())

    def test_invalid_signature(self):
        payload = {"event": "payment.captured"}
        response = self.client.post(
            reverse("webhooks:razorpay-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="invalid_signature",
        )
        self.assertEqual(response.status_code, 200)  # Should still return 200 to acknowledge receipt
        content = json.loads(response.content)
        self.assertFalse(content["verified"])
        
        # Verify log created but not verified
        log = WebhookLog.objects.last()
        self.assertFalse(log.verified)

    def test_replay_functionality(self):
        # Create a log entry manually
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "order_id": "order_123",
                        "id": "pay_replay_123",
                        "status": "captured",
                        "amount": 1500,
                    }
                }
            },
        }
        log = WebhookLog.objects.create(
            provider="razorpay",
            payload=payload,
            verified=True
        )
        
        # Login as staff
        admin_user = get_user_model().objects.create_superuser("admin", "admin@example.com", "password")
        self.client.force_login(admin_user)
        
        # Replay
        response = self.client.post(reverse("webhooks:inspector-replay", args=[log.pk]))
        self.assertEqual(response.status_code, 302)
        
        log.refresh_from_db()
        self.assertEqual(log.replay_count, 1)
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAID)
