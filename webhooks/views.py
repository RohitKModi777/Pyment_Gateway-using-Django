import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from store.models import DeveloperConfig, Order, Transaction
from store.services import get_razorpay_keys, verify_webhook_signature

from .forms import DeveloperConfigForm
from .models import WebhookLog
from .notifications import send_verification_failure_alert, send_webhook_failure_alert

logger = logging.getLogger(__name__)

RAZORPAY_SIGNATURE_HEADER = "X-Razorpay-Signature"


@csrf_exempt
@require_POST
def razorpay_webhook(request: HttpRequest) -> HttpResponse:
    """
    Receive and process Razorpay webhook events.
    
    This endpoint:
    1. Validates the webhook signature
    2. Logs all webhook events
    3. Processes verified events
    4. Sends alerts on failures
    """
    try:
        payload = request.body
        signature = request.headers.get(RAZORPAY_SIGNATURE_HEADER, "")
        
        # Parse payload
        try:
            data = json.loads(payload.decode("utf-8") or "{}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook payload: {e}")
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        # Get webhook secret
        _, secret = get_razorpay_keys()
        config = DeveloperConfig.get_solo()
        webhook_secret = config.webhook_secret or settings.WEBHOOK_SECRET or secret
        
        if not webhook_secret:
            logger.error("No webhook secret configured")
            return JsonResponse({"error": "Webhook secret not configured"}, status=500)
        
        # Verify signature
        verified = verify_webhook_signature(payload, signature, webhook_secret)
        
        # Create log entry
        log = WebhookLog.objects.create(
            provider="razorpay",
            payload=data,
            headers=dict(request.headers),
            signature_header=signature,
            verified=verified,
        )
        
        logger.info(f"Webhook received: {data.get('event')} (verified={verified}, log_id={log.pk})")
        
        # Process verified webhooks
        if verified:
            try:
                process_razorpay_event(data, log)
            except Exception as e:
                logger.error(f"Error processing webhook {log.pk}: {e}", exc_info=True)
                send_webhook_failure_alert(log, e)
                return JsonResponse({
                    "received": True,
                    "verified": True,
                    "processed": False,
                    "error": str(e)
                }, status=200)  # Still return 200 to prevent retries
        else:
            logger.warning(f"Webhook signature verification failed for log {log.pk}")
            send_verification_failure_alert(log)
        
        return JsonResponse({"received": True, "verified": verified, "processed": verified})
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook endpoint: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


def process_razorpay_event(data: dict, log: WebhookLog, replay: bool = False) -> None:
    """
    Process Razorpay webhook events and update order/transaction status.
    
    Supported events:
    - payment.captured: Payment successfully captured
    - payment.authorized: Payment authorized (not yet captured)
    - payment.failed: Payment failed
    - payment.pending: Payment is pending
    - order.paid: Order marked as paid
    - refund.created: Refund initiated
    - refund.processed: Refund completed
    """
    import logging
    logger = logging.getLogger(__name__)
    
    event = data.get("event")
    logger.info(f"Processing webhook event: {event} (replay={replay})")
    
    # Handle different event types
    if event and event.startswith("payment."):
        _process_payment_event(data, log, event, logger)
    elif event and event.startswith("refund."):
        _process_refund_event(data, log, event, logger)
    elif event == "order.paid":
        _process_order_paid_event(data, log, logger)
    else:
        logger.warning(f"Unhandled event type: {event}")
    
    # Update replay count
    if replay:
        log.replay_count += 1
        log.save(update_fields=["replay_count"])
        logger.info(f"Webhook replayed. Total replays: {log.replay_count}")


def _process_payment_event(data: dict, log: WebhookLog, event: str, logger) -> None:
    """Process payment-related events."""
    from store.payment_notifications import send_payment_notifications
    
    payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment_entity.get("order_id")
    payment_id = payment_entity.get("id")
    status = payment_entity.get("status")
    amount = payment_entity.get("amount") or 0
    
    if not order_id:
        logger.warning(f"No order_id found in payment event: {event}")
        return
    
    try:
        order = Order.objects.get(razorpay_order_id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order not found for razorpay_order_id: {order_id}")
        return
    
    # Map payment status to order status
    old_status = order.status
    if status == "captured":
        order.status = Order.STATUS_PAID
        txn_status = Transaction.STATUS_SUCCESS
        logger.info(f"Payment captured for order {order.pk}")
    elif status == "authorized":
        order.status = Order.STATUS_PAID
        txn_status = Transaction.STATUS_SUCCESS
        logger.info(f"Payment authorized for order {order.pk}")
    elif status == "failed":
        order.status = Order.STATUS_FAILED
        txn_status = Transaction.STATUS_FAILED
        logger.warning(f"Payment failed for order {order.pk}")
    elif status == "pending":
        order.status = Order.STATUS_PENDING
        txn_status = Transaction.STATUS_PENDING
        logger.info(f"Payment pending for order {order.pk}")
    else:
        logger.warning(f"Unknown payment status: {status} for order {order.pk}")
        txn_status = Transaction.STATUS_PENDING
    
    # Update order details
    order.razorpay_payment_id = payment_id or order.razorpay_payment_id
    order.razorpay_signature = log.signature_header or order.razorpay_signature
    order.save()
    
    if old_status != order.status:
        logger.info(f"Order {order.pk} status changed: {old_status} -> {order.status}")
    
    # Create or update transaction
    txn, created = Transaction.objects.get_or_create(
        order=order,
        reference=payment_id or f"log-{log.pk}",
        defaults={
            "user": order.user,
            "amount_cents": amount,
            "status": txn_status,
            "payload": data,
        },
    )
    
    if not created:
        # Update existing transaction
        txn.status = txn_status
        txn.payload = data
        txn.amount_cents = amount
        txn.save(update_fields=["status", "payload", "amount_cents", "updated_at"])
        logger.info(f"Updated existing transaction {txn.pk} for order {order.pk}")
    else:
        logger.info(f"Created new transaction {txn.pk} for order {order.pk}")
    
    # Send email notifications for successful payments
    if status in ["captured", "authorized"] and order.status == Order.STATUS_PAID:
        try:
            send_payment_notifications(order, txn)
            logger.info(f"Payment notification emails sent for order {order.pk}")
        except Exception as email_error:
            logger.error(f"Failed to send payment notifications for order {order.pk}: {email_error}")
            # Don't fail webhook processing if email fails


def _process_refund_event(data: dict, log: WebhookLog, event: str, logger) -> None:
    """Process refund-related events."""
    refund_entity = data.get("payload", {}).get("refund", {}).get("entity", {})
    payment_id = refund_entity.get("payment_id")
    refund_id = refund_entity.get("id")
    amount = refund_entity.get("amount") or 0
    status = refund_entity.get("status")
    
    if not payment_id:
        logger.warning(f"No payment_id found in refund event: {event}")
        return
    
    # Find order by payment_id
    try:
        order = Order.objects.get(razorpay_payment_id=payment_id)
    except Order.DoesNotExist:
        logger.error(f"Order not found for payment_id: {payment_id}")
        return
    
    logger.info(f"Processing refund {refund_id} for order {order.pk}, status: {status}")
    
    # Create refund transaction
    txn_status = Transaction.STATUS_SUCCESS if status == "processed" else Transaction.STATUS_PENDING
    
    txn, created = Transaction.objects.get_or_create(
        order=order,
        reference=refund_id or f"refund-log-{log.pk}",
        defaults={
            "user": order.user,
            "amount_cents": amount,  # Store as positive, context implies refund
            "status": txn_status,
            "payload": data,
        },
    )
    
    if not created:
        txn.status = txn_status
        txn.payload = data
        txn.save(update_fields=["status", "payload", "updated_at"])
        logger.info(f"Updated refund transaction {txn.pk}")
    else:
        logger.info(f"Created refund transaction {txn.pk} for order {order.pk}")


def _process_order_paid_event(data: dict, log: WebhookLog, logger) -> None:
    """Process order.paid events."""
    order_entity = data.get("payload", {}).get("order", {}).get("entity", {})
    order_id = order_entity.get("id")
    amount = order_entity.get("amount") or 0
    
    if not order_id:
        logger.warning("No order_id found in order.paid event")
        return
    
    try:
        order = Order.objects.get(razorpay_order_id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order not found for razorpay_order_id: {order_id}")
        return
    
    old_status = order.status
    order.status = Order.STATUS_PAID
    order.save()
    
    logger.info(f"Order {order.pk} marked as paid via order.paid event (was: {old_status})")
    
    # Create transaction if not exists
    txn, created = Transaction.objects.get_or_create(
        order=order,
        reference=f"order-{order_id}",
        defaults={
            "user": order.user,
            "amount_cents": amount,
            "status": Transaction.STATUS_SUCCESS,
            "payload": data,
        },
    )
    
    if created:
        logger.info(f"Created transaction {txn.pk} from order.paid event")


@staff_member_required
def inspector_list(request: HttpRequest) -> HttpResponse:
    logs = WebhookLog.objects.all()[:50]
    return render(request, "webhooks/inspector_list.html", {"logs": logs})


@staff_member_required
def inspector_detail(request: HttpRequest, pk: int) -> HttpResponse:
    log = get_object_or_404(WebhookLog, pk=pk)
    return render(request, "webhooks/inspector_detail.html", {"log": log})


@staff_member_required
@require_POST
def inspector_replay(request: HttpRequest, pk: int) -> HttpResponse:
    log = get_object_or_404(WebhookLog, pk=pk)
    process_razorpay_event(log.payload, log, replay=True)
    messages.success(request, "Webhook replayed against the latest state.")
    return redirect(reverse("webhooks:inspector-detail", args=[pk]))


@staff_member_required
def developer_config_view(request: HttpRequest) -> HttpResponse:
    config = DeveloperConfig.get_solo()
    if request.method == "POST":
        form = DeveloperConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Developer configuration updated.")
            return redirect("webhooks:developer-config")
    else:
        form = DeveloperConfigForm(instance=config)
    return render(request, "webhooks/developer_config.html", {"form": form})
