from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from store.models import Product


class Command(BaseCommand):
    help = "Load demo products and a staff user for quick testing."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={"is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("adminpass")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created staff user admin@example.com / adminpass"))
        else:
            self.stdout.write("Staff user already exists.")

        product, created = Product.objects.get_or_create(
            slug="demo-product-499",
            defaults={
                "title": "Demo Product – ₹499",
                "description": "Sample product used to walk through the Razorpay checkout.",
                "price_cents": 49900,
                "inventory": 25,
                "is_featured": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            self.stdout.write("Demo product already exists.")

        self.stdout.write(self.style.SUCCESS("Demo data ready."))

