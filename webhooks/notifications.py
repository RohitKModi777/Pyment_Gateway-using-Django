import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import WebhookLog

logger = logging.getLogger(__name__)


def send_webhook_failure_alert(log: WebhookLog, error: Exception) -> None:
    """Send email alert when webhook processing fails."""
    if not settings.DEBUG:  # Only send in production
        try:
            subject = f"[PayDemo] Webhook Processing Failed - {log.provider}"
            message = f"""
Webhook processing failed:

Provider: {log.provider}
Event: {log.payload.get('event', 'unknown')}
Received: {log.received_at}
Verified: {log.verified}
Error: {str(error)}

Webhook ID: {log.pk}
View details: {getattr(settings, 'SITE_URL', 'http://localhost:8000')}/webhooks/inspector/{log.pk}/

Payload:
{log.payload}
"""
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SUPPORT_EMAIL],
                fail_silently=True,
            )
            logger.info(f"Sent webhook failure alert for log {log.pk}")
        except Exception as e:
            logger.error(f"Failed to send webhook failure alert: {e}")


def send_verification_failure_alert(log: WebhookLog) -> None:
    """Send email alert when webhook signature verification fails."""
    if not settings.DEBUG:  # Only send in production
        try:
            subject = f"[PayDemo] Webhook Verification Failed - {log.provider}"
            message = f"""
Webhook signature verification failed:

Provider: {log.provider}
Event: {log.payload.get('event', 'unknown')}
Received: {log.received_at}
Signature: {log.signature_header[:20]}...

This could indicate:
1. Incorrect webhook secret configured
2. Potential security threat (spoofed webhook)

Webhook ID: {log.pk}
View details: {getattr(settings, 'SITE_URL', 'http://localhost:8000')}/webhooks/inspector/{log.pk}/
"""
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SUPPORT_EMAIL],
                fail_silently=True,
            )
            logger.warning(f"Sent verification failure alert for log {log.pk}")
        except Exception as e:
            logger.error(f"Failed to send verification failure alert: {e}")
