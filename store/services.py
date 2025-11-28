import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

import razorpay
from django.conf import settings
from django.utils import timezone

from .models import DeveloperConfig, Order, Transaction

logger = logging.getLogger(__name__)


def get_developer_config() -> DeveloperConfig:
    return DeveloperConfig.get_solo()


def get_razorpay_keys() -> tuple[str, str]:
    config = get_developer_config()
    key_id = config.razorpay_key_id or settings.RAZORPAY_KEY_ID
    key_secret = config.razorpay_key_secret or settings.RAZORPAY_KEY_SECRET
    return key_id, key_secret


def get_public_razorpay_key() -> str:
    key_id, _ = get_razorpay_keys()
    return key_id


def get_razorpay_client() -> Optional[razorpay.Client]:
    key_id, key_secret = get_razorpay_keys()
    if not (key_id and key_secret):
        return None
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(order: Order) -> Dict[str, Any]:
    client = get_razorpay_client()
    amount = order.total_amount_cents
    if not client:
        # Fallback mock order for local demos when keys are missing
        mock_id = f"order_local_{timezone.now().timestamp()}"
        logger.warning("Razorpay keys missing, returning mock order id %s", mock_id)
        order.razorpay_order_id = mock_id
        order.save(update_fields=["razorpay_order_id"])
        return {
            "id": mock_id,
            "amount": amount,
            "currency": "INR",
        }

    razorpay_order = client.order.create(
        {
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"order_id": str(order.id)},
        }
    )
    order.razorpay_order_id = razorpay_order["id"]
    order.save(update_fields=["razorpay_order_id"])
    return razorpay_order


def verify_payment_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    if not (order_id and payment_id and signature and secret):
        return False
    generated = hmac.new(
        secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(generated, signature)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not (payload and signature and secret):
        return False
    generated = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(generated, signature)


def record_transaction(order: Order, amount_cents: int, status: str, payload: Dict[str, Any], reference: str = "") -> Transaction:
    transaction = Transaction.objects.create(
        order=order,
        user=order.user,
        amount_cents=amount_cents,
        status=status,
        payload=payload,
        reference=reference,
    )
    return transaction

