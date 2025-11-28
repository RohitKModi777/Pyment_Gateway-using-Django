import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    def __str__(self):
        return f"Profile for {self.user.get_full_name() or self.user.email}"


class Product(TimeStampedModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price_cents = models.PositiveIntegerField()
    inventory = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def price_display(self):
        return self.price_cents / 100


class Order(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    total_amount_cents = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    DELIVERY_STATUS_PENDING = "pending"
    DELIVERY_STATUS_PACKED = "packed"
    DELIVERY_STATUS_SHIPPED = "shipped"
    DELIVERY_STATUS_DELIVERED = "delivered"
    DELIVERY_STATUS_CANCELLED = "cancelled"
    DELIVERY_STATUS_CHOICES = [
        (DELIVERY_STATUS_PENDING, "Pending"),
        (DELIVERY_STATUS_PACKED, "Packed"),
        (DELIVERY_STATUS_SHIPPED, "Shipped"),
        (DELIVERY_STATUS_DELIVERED, "Delivered"),
        (DELIVERY_STATUS_CANCELLED, "Cancelled"),
    ]
    delivery_status = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES, default=DELIVERY_STATUS_PENDING
    )
    razorpay_order_id = models.CharField(max_length=191, blank=True)
    razorpay_payment_id = models.CharField(max_length=191, blank=True)
    razorpay_signature = models.CharField(max_length=191, blank=True)
    notes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.pk}"

    def recalculate_total(self):
        total = self.items.aggregate(
            total=Sum(F("qty") * F("unit_price_cents"), output_field=models.PositiveIntegerField())
        ).get("total") or 0
        self.total_amount_cents = total
        self.save(update_fields=["total_amount_cents"])

    @property
    def amount_display(self):
        return self.total_amount_cents / 100


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    unit_price_cents = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.qty} x {self.product.title}"

    @property
    def line_total_cents(self):
        return self.qty * self.unit_price_cents


class Transaction(TimeStampedModel):
    PROVIDER_RAZORPAY = "razorpay"
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    order = models.ForeignKey(Order, related_name="transactions", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    provider = models.CharField(max_length=32, default=PROVIDER_RAZORPAY)
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payload = models.JSONField(default=dict, blank=True)
    reference = models.CharField(max_length=191, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} tx for {self.order_id}"

    @property
    def amount_display(self):
        return self.amount_cents / 100


class DeveloperConfig(TimeStampedModel):
    webhook_secret = models.CharField(max_length=255, blank=True)
    razorpay_key_id = models.CharField(max_length=255, blank=True)
    razorpay_key_secret = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Developer Configuration"
        verbose_name_plural = "Developer Configuration"

    def __str__(self):
        return "Developer Config"

    @classmethod
    def get_solo(cls):
        return cls.objects.first() or cls.objects.create()


class Cart(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    session_key = models.CharField(max_length=40, null=True, blank=True)

    def __str__(self):
        return f"Cart {self.pk} ({self.user or self.session_key})"

    @property
    def total_cents(self):
        return sum(item.line_total_cents for item in self.items.all())


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("cart", "product")]

    def __str__(self):
        return f"{self.qty} x {self.product.title}"

    @property
    def line_total_cents(self):
        return self.product.price_cents * self.qty


class PreviousCartItem(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)  # Added missing field
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Previous Cart Item"
        verbose_name_plural = "Previous Cart Items"

    def __str__(self):
        return f"{self.user} - {self.product.title} ({self.qty})"

    @property
    def line_total_cents(self):
        return self.product.price_cents * self.qty