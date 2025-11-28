import json
import uuid
import hmac
import hashlib
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.conf import settings
from webhooks.views import razorpay_webhook
from store.models import Order

class Command(BaseCommand):
    help = 'Simulate a Razorpay webhook event locally'

    def add_arguments(self, parser):
        parser.add_argument('--event', type=str, default='payment.captured', help='Event type (e.g., payment.captured, payment.failed)')
        parser.add_argument('--order-id', type=str, required=True, help='Razorpay Order ID (e.g., order_123)')
        parser.add_argument('--payment-id', type=str, default=f'pay_{uuid.uuid4().hex[:10]}', help='Razorpay Payment ID')
        parser.add_argument('--amount', type=int, help='Amount in cents (defaults to order total)')

    def handle(self, *args, **options):
        event_type = options['event']
        order_id = options['order_id']
        payment_id = options['payment_id']
        
        try:
            order = Order.objects.get(razorpay_order_id=order_id)
            amount = options['amount'] or order.total_amount_cents
        except Order.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"Order with ID {order_id} not found locally. Using mock data."))
            amount = options['amount'] or 1000

        # Construct payload based on event type
        payload = {
            "entity": "event",
            "account_id": "acc_test",
            "event": event_type,
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "entity": "payment",
                        "amount": amount,
                        "currency": "INR",
                        "status": event_type.split('.')[-1],
                        "order_id": order_id,
                        "method": "card",
                        "captured": True,
                        "description": "Test Transaction",
                        "card_id": "card_test",
                        "email": "test@example.com",
                        "contact": "+919999999999",
                    }
                }
            },
            "created_at": 1234567890
        }

        # Handle refund events specially
        if event_type.startswith('refund.'):
            payload['payload']['refund'] = {
                "entity": {
                    "id": f"rfnd_{uuid.uuid4().hex[:10]}",
                    "entity": "refund",
                    "amount": amount,
                    "currency": "INR",
                    "payment_id": payment_id,
                    "status": "processed",
                    "receipt": "Receipt No. 1",
                    "speed": "normal",
                    "created_at": 1234567890,
                    "batch_id": None
                }
            }
            # Remove payment payload if it's a refund event? Razorpay usually sends both or just refund?
            # Keeping payment payload as context is often useful, but let's stick to the structure expected by the view.
            # The view looks for payload.refund.entity for refund events.

        body = json.dumps(payload)
        
        # Generate signature
        secret = settings.WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET
        if not secret:
            self.stdout.write(self.style.ERROR("No WEBHOOK_SECRET or RAZORPAY_KEY_SECRET found in settings."))
            return

        signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

        # Create request
        factory = RequestFactory()
        request = factory.post(
            '/webhooks/razorpay/',
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature
        )

        # Execute view
        self.stdout.write(f"Sending {event_type} webhook for order {order_id}...")
        response = razorpay_webhook(request)
        
        if response.status_code == 200:
            content = json.loads(response.content)
            if content.get('verified'):
                self.stdout.write(self.style.SUCCESS(f"Webhook processed successfully! Verified: {content['verified']}"))
            else:
                self.stdout.write(self.style.ERROR(f"Webhook verification failed! Verified: {content['verified']}"))
        else:
            self.stdout.write(self.style.ERROR(f"Webhook failed with status {response.status_code}"))
