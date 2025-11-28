import json
from decimal import Decimal
from io import BytesIO

import razorpay
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView, UpdateView
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import CartItem, Order, OrderItem, PreviousCartItem, Product, UserProfile, Cart
# Add this import at the top
import os
from django.contrib.auth import get_user_model

def create_first_admin(request):
    """Secure admin creation using environment variables"""
    
    # Check secret key for security
    expected_secret = os.getenv('ADMIN_CREATION_SECRET')
    if not expected_secret:
        return HttpResponse('❌ ADMIN_CREATION_SECRET not configured', status=500)
    
    provided_secret = request.GET.get('secret', '')
    if provided_secret != expected_secret:
        return HttpResponse('❌ Unauthorized: Invalid secret key', status=401)
    
    User = get_user_model()
    
    # Check if admin already exists
    if User.objects.filter(is_superuser=True).exists():
        return HttpResponse(
            '❌ Admin user already exists. <br><br>'
            '<a href="/admin/">Go to Admin Panel</a>'
        )
    
    # Get credentials from environment variables
    admin_username = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    admin_email = os.getenv('DEFAULT_ADMIN_EMAIL')
    admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD')
    
    # Validate required environment variables
    if not admin_email or not admin_password:
        return HttpResponse(
            '❌ DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD must be set in environment variables',
            status=500
        )
    
    try:
        # Create the superuser
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        
        return HttpResponse(
            f'✅ Admin user created successfully!<br><br>'
            f'Username: <strong>{admin_username}</strong><br>'
            f'Email: <strong>{admin_email}</strong><br><br>'
            f'<a href="/admin/">Go to Admin Panel</a><br><br>'
            f'<small>Password was set from environment variables</small>'
        )
        
    except Exception as e:
        return HttpResponse(f'❌ Error creating admin: {str(e)}', status=500)
        

def home(request):
    """Home page view."""
    featured_products = Product.objects.all()[:6]
    recent_products = Product.objects.all().order_by('-created_at')[:6]
    return render(request, "store/home.html", {
        "featured_products": featured_products,
        "recent_products": recent_products,
    })


class ProductListView(ListView):
    """List all products with search functionality."""
    model = Product
    template_name = "store/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.all()
        search_query = self.request.GET.get('q', '')
        
        if search_query:
            queryset = queryset.filter(
                title__icontains=search_query
            ) | queryset.filter(
                description__icontains=search_query
            )
        
        return queryset.distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class ProductDetailView(DetailView):
    """Product detail view."""
    model = Product
    template_name = "store/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.all()


@login_required
def cart(request):
    """View shopping cart."""
    cart_items = CartItem.objects.filter(cart__user=request.user).select_related("product")
    previous_items = PreviousCartItem.objects.filter(user=request.user).select_related("product")[:10]
    
    total = sum(item.line_total_cents for item in cart_items) / 100
    total_items = sum(item.qty for item in cart_items)  # Total quantity of all items
    
    return render(
        request,
        "store/cart.html",
        {
            "cart_items": cart_items,
            "previous_items": previous_items,
            "total": total,
            "total_items": total_items
        },
    )


@login_required
@require_POST
def add_to_cart(request, product_id):
    """Add product to cart."""
    product = get_object_or_404(Product, pk=product_id)
    quantity = int(request.POST.get("qty", 1))

    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"qty": quantity},
    )

    if not created:
        cart_item.qty += quantity
        cart_item.save()

    messages.success(request, f"Added {product.title} to cart")
    return redirect("store:cart")


@login_required
@require_POST
def update_cart_item(request, item_id):
    """Update cart item quantity."""
    cart_item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    action = request.POST.get("action")

    if action == "increase":
        # Check if we can increase (don't exceed inventory)
        if cart_item.qty < cart_item.product.inventory:
            cart_item.qty += 1
            cart_item.save()
        else:
            messages.warning(request, f"Cannot add more {cart_item.product.title}. Only {cart_item.product.inventory} available in stock.")
    elif action == "decrease":
        if cart_item.qty > 1:
            cart_item.qty -= 1
            cart_item.save()
        else:
            PreviousCartItem.objects.create(
                user=request.user,
                product=cart_item.product,
                qty=cart_item.qty,
            )
            cart_item.delete()
            messages.info(request, f"{cart_item.product.title} moved to history")

    return redirect("store:cart")


@login_required
@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart and move to history."""
    cart_item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    
    PreviousCartItem.objects.create(
        user=request.user,
        product=cart_item.product,
        qty=cart_item.qty,
    )
    
    product_title = cart_item.product.title
    cart_item.delete()
    messages.success(request, f"Removed {product_title} from cart")
    return redirect("store:cart")


class PreviousCartView(LoginRequiredMixin, ListView):
    """View previous cart items."""
    model = PreviousCartItem
    template_name = "store/previous_items.html"
    context_object_name = "previous_items"

    def get_queryset(self):
        return PreviousCartItem.objects.filter(user=self.request.user).select_related("product")


@login_required
@require_POST
def restore_cart_item(request, item_id):
    """Restore item from previous cart to active cart."""
    prev_item = get_object_or_404(PreviousCartItem, pk=item_id, user=request.user)
    
    cart, _ = Cart.objects.get_or_create(user=request.user)
    
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=prev_item.product,
        defaults={"qty": prev_item.qty},
    )
    
    if not created:
        cart_item.qty += prev_item.qty
        cart_item.save()
    
    prev_item.delete()
    messages.success(request, f"Restored {prev_item.product.title} to cart")
    return redirect("store:cart")


@login_required
def checkout(request):
    """Checkout page."""
    try:
        cart_items = CartItem.objects.filter(cart__user=request.user).select_related("product")
        
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('store:cart')
        
        total_cents = sum(item.line_total_cents for item in cart_items)
        
        context = {
            'items': cart_items,
            'total_cents': total_cents,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        }
        
        return render(request, "store/checkout.html", context)
        
    except Exception as e:
        print(f"Checkout error: {e}")
        messages.error(request, "An error occurred while loading the checkout page.")
        return redirect('store:cart')


@login_required
@require_POST
def create_order(request):
    """Create Razorpay order for payment."""
    try:
        cart_items = CartItem.objects.filter(cart__user=request.user).select_related("product")
        
        if not cart_items:
            return JsonResponse({"error": "Cart is empty"}, status=400)
        
        total_cents = sum(item.line_total_cents for item in cart_items)
        
        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        order_data = {
            'amount': total_cents,
            'currency': 'INR',
            'payment_capture': 1
        }
        
        razorpay_order = razorpay_client.order.create(order_data)
        
        order = Order.objects.create(
            user=request.user,
            total_amount_cents=total_cents,
            status="pending",
            razorpay_order_id=razorpay_order['id']
        )
        
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                qty=cart_item.qty,
                unit_price_cents=cart_item.product.price_cents,
            )
        
        return JsonResponse({
            "order_id": razorpay_order['id'],
            "amount": total_cents,
            "currency": "INR",
            "order_uuid": str(order.id),
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
def verify_payment(request):
    """Verify Razorpay payment."""
    import logging
    from .models import Transaction
    from .payment_notifications import send_payment_notifications
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        
        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        params_dict = {
            'razorpay_order_id': data["razorpay_order_id"],
            'razorpay_payment_id': data["razorpay_payment_id"],
            'razorpay_signature': data["razorpay_signature"]
        }
        
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
            
            order = Order.objects.get(razorpay_order_id=data["razorpay_order_id"])
            order.status = "paid"
            order.razorpay_payment_id = data["razorpay_payment_id"]
            order.razorpay_signature = data["razorpay_signature"]
            order.save()
            
            # Create transaction record
            transaction, created = Transaction.objects.get_or_create(
                order=order,
                reference=data["razorpay_payment_id"],
                defaults={
                    "user": order.user,
                    "amount_cents": order.total_amount_cents,
                    "status": Transaction.STATUS_SUCCESS,
                    "provider": Transaction.PROVIDER_RAZORPAY,
                    "payload": data,
                }
            )
            
            if not created:
                # Update existing transaction
                transaction.status = Transaction.STATUS_SUCCESS
                transaction.payload = data
                transaction.save(update_fields=["status", "payload", "updated_at"])
                logger.info(f"Updated existing transaction {transaction.pk} for order {order.pk}")
            else:
                logger.info(f"Created new transaction {transaction.pk} for order {order.pk}")
            
            # Send email notifications
            try:
                send_payment_notifications(order, transaction)
                logger.info(f"Payment notifications sent for order {order.pk}")
            except Exception as email_error:
                logger.error(f"Failed to send payment notifications for order {order.pk}: {email_error}")
                # Don't fail the payment verification if email fails
            
            # Clear cart
            CartItem.objects.filter(cart__user=order.user).delete()
            
            return JsonResponse({
                "status": "success", 
                "redirect_url": reverse_lazy("store:order-detail", kwargs={"pk": order.id})
            })
            
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"status": "error", "message": "Invalid signature"}, status=400)
        
    except Order.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Payment verification error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
def order_detail(request, pk):
    """Order detail view."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, "store/order_detail.html", {"order": order})


@staff_member_required
@require_POST
def update_order_status(request, order_id):
    """Update order status (admin only)."""
    order = get_object_or_404(Order, pk=order_id)
    new_status = request.POST.get("status")
    
    if new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
        order.save()
        messages.success(request, f"Order status updated to {order.get_status_display()}")
    else:
        messages.error(request, "Invalid status")
    
    return redirect("admin:store_order_change", order_id)


@login_required
def dashboard(request):
    """User dashboard."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    cart_items = CartItem.objects.filter(cart__user=request.user)
    
    cart_total = sum(item.line_total_cents for item in cart_items) / 100
    
    from .models import Transaction
    transactions = Transaction.objects.filter(order__user=request.user).order_by("-created_at")[:5]
    
    context = {
        "profile": profile,
        "orders": orders,
        "transactions": transactions,
        "cart_summary": {
            "count": cart_items.count(),
            "total": cart_total,
        },
    }
    
    return render(request, "store/dashboard.html", context)


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Edit user profile."""
    model = UserProfile
    template_name = "store/profile_edit.html"
    fields = ["phone", "address", "avatar"]
    success_url = reverse_lazy("store:dashboard")

    def get_object(self, queryset=None):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully")
        return super().form_valid(form)


class InvoiceView(LoginRequiredMixin, View):
    """Generate and download PDF invoice for an order."""
    
    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        title = Paragraph(f"<b>Invoice - Order #{order.id}</b>", styles["Title"])
        elements.append(title)
        elements.append(Spacer(1, 0.3 * inch))
        
        order_info = Paragraph(
            f"<b>Date:</b> {order.created_at.strftime('%B %d, %Y')}<br/>"
            f"<b>Status:</b> {order.get_status_display()}<br/>"
            f"<b>Customer:</b> {request.user.get_full_name() or request.user.email}<br/>"
            f"<b>Email:</b> {request.user.email}",
            styles["Normal"]
        )
        elements.append(order_info)
        elements.append(Spacer(1, 0.3 * inch))
        
        data = [["Item", "Quantity", "Unit Price", "Total"]]
        for item in order.items.all():
            data.append([
                item.product.title,
                str(item.qty),
                f"{item.unit_price_cents / 100:.2f}",
                f"{item.line_total_cents / 100:.2f}",
            ])
        
        data.append(["", "", "Total", f"{order.total_amount_cents / 100:.2f}"])
        
        table = Table(data, colWidths=[3 * inch, 1 * inch, 1.5 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -2), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice_{order.id}.pdf"'
        return response


class SupportView(TemplateView):
    """Support page view."""
    template_name = "store/support.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["support_email"] = settings.SUPPORT_EMAIL
        context["support_phone"] = settings.SUPPORT_PHONE
        return context
