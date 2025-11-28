from django.urls import path

from . import views

app_name = "webhooks"

urlpatterns = [
    path("razorpay/", views.razorpay_webhook, name="razorpay-webhook"),
    path("inspector/", views.inspector_list, name="inspector"),
    path("inspector/<int:pk>/", views.inspector_detail, name="inspector-detail"),
    path("inspector/<int:pk>/replay/", views.inspector_replay, name="inspector-replay"),
    path("developer/config/", views.developer_config_view, name="developer-config"),
]

