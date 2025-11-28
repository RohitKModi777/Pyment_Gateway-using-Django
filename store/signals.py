from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import UserProfile, CartItem, PreviousCartItem

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_delete, sender=CartItem)
def move_to_history_on_delete(sender, instance, **kwargs):
    # If the cart belongs to a user, save to history
    if instance.cart.user:
        # Check if already exists to avoid duplicates if desired, or just create
        # Requirement: "When quantity becomes 0, item should NOT disappear forever — it should move into a 'previously selected products' list."
        # This signal handles the deletion case (which happens when qty=0 in our logic, or explicit remove)
        PreviousCartItem.objects.create(
            user=instance.cart.user,
            product=instance.product
        )
