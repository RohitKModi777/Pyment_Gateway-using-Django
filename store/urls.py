from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    # Home and Product URLs
    path("", views.home, name="home"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/<int:pk>/", views.ProductDetailView.as_view(), name="product-detail"),
    
    # Cart URLs
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add-to-cart"),
    path("cart/update/<int:item_id>/", views.update_cart_item, name="update-cart-item"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove-from-cart"),
    path("cart/previous/", views.PreviousCartView.as_view(), name="previous-cart"),
    path("cart/restore/<int:item_id>/", views.restore_cart_item, name="restore-cart-item"),
    
    # Checkout URLs
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/create-order/", views.create_order, name="create-order"),
    path("checkout/verify/", views.verify_payment, name="verify-payment"),
    
    # Order URLs
    path("orders/<uuid:pk>/", views.order_detail, name="order-detail"),
    path("orders/<int:order_id>/update-status/", views.update_order_status, name="update-order-status"),
    
    # Invoice and Support URLs
    path("invoice/<uuid:pk>/", views.InvoiceView.as_view(), name="invoice"),
    path("support/", views.SupportView.as_view(), name="support"),
    
    # User URLs
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/edit/", views.ProfileEditView.as_view(), name="profile-edit"),
]
