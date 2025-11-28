from django.core.management.base import BaseCommand, CommandError

from store.models import Order
from store.services import create_razorpay_order


class Command(BaseCommand):
    help = "Regenerate a Razorpay order for an existing local Order UUID."

    def add_arguments(self, parser):
        parser.add_argument("--order", required=True, help="Order UUID")

    def handle(self, *args, **options):
        order_id = options["order"]
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise CommandError(f"Order {order_id} not found.")

        data = create_razorpay_order(order)
        self.stdout.write(self.style.SUCCESS(f"Razorpay order ready: {data['id']}"))

