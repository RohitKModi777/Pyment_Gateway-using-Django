"""
Payment notification system for sending emails on successful payments.
"""
import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Order, Transaction

logger = logging.getLogger(__name__)


def send_payment_success_email_to_customer(order: Order, transaction: Transaction) -> bool:
    """
    Send payment confirmation email to customer.
    
    Args:
        order: The Order instance
        transaction: The Transaction instance
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = f"Payment Confirmation - Order #{order.id}"
        
        # Prepare context for email template
        context = {
            'order': order,
            'transaction': transaction,
            'customer_name': order.user.get_full_name() or order.user.email,
            'customer_email': order.user.email,
            'order_items': order.items.all(),
            'total_amount': order.total_amount_cents / 100,
            'payment_id': transaction.reference,
            'order_url': f"{settings.SITE_URL}/orders/{order.id}/",
        }
        
        # Render HTML email
        html_message = render_to_string('emails/payment_success_email.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment confirmation email sent to {order.user.email} for order {order.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email for order {order.id}: {e}", exc_info=True)
        return False


def send_payment_notification_to_admin(order: Order, transaction: Transaction) -> bool:
    """
    Send payment notification to admin/support team.
    
    Args:
        order: The Order instance
        transaction: The Transaction instance
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = f"[PayDemo] New Payment Received - Order #{order.id}"
        
        # Prepare context for email template
        context = {
            'order': order,
            'transaction': transaction,
            'customer_name': order.user.get_full_name() or order.user.email,
            'customer_email': order.user.email,
            'order_items': order.items.all(),
            'total_amount': order.total_amount_cents / 100,
            'payment_id': transaction.reference,
            'admin_url': f"{settings.SITE_URL}/admin/store/order/{order.id}/change/",
        }
        
        # Render HTML email
        html_message = render_to_string('emails/payment_notification_admin.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email to support team
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.SUPPORT_EMAIL],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment notification sent to admin for order {order.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send admin notification for order {order.id}: {e}", exc_info=True)
        return False


def send_payment_notifications(order: Order, transaction: Transaction) -> None:
    """
    Send both customer and admin payment notifications.
    
    Args:
        order: The Order instance
        transaction: The Transaction instance
    """
    # Send customer confirmation
    customer_sent = send_payment_success_email_to_customer(order, transaction)
    
    # Send admin notification
    admin_sent = send_payment_notification_to_admin(order, transaction)
    
    if customer_sent and admin_sent:
        logger.info(f"All payment notifications sent successfully for order {order.id}")
    elif not customer_sent:
        logger.warning(f"Customer notification failed for order {order.id}")
    elif not admin_sent:
        logger.warning(f"Admin notification failed for order {order.id}")
