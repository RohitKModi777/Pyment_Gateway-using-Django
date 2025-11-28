from django.contrib import admin

from .models import DeveloperConfig, Order, OrderItem, Product, Transaction, UserProfile


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "price_cents", "inventory", "is_featured")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount_cents", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "razorpay_order_id", "razorpay_payment_id")
    inlines = [OrderItemInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "status", "amount_cents", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("order__id", "reference")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__email", "phone")


@admin.register(DeveloperConfig)
class DeveloperConfigAdmin(admin.ModelAdmin):
    list_display = ("webhook_secret", "razorpay_key_id", "updated_at")
