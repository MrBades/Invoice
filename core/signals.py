from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Notification

@receiver(post_save, sender=Product)
def check_stock_level(sender, instance, **kwargs):
    threshold = instance.target_stock * 0.3
    if instance.stock_quantity <= threshold:
        msg = f"Low Stock Alert: {instance.name} is at {instance.stock_quantity} (Below 30% of target {instance.target_stock})"
        # Avoid duplicate unread notifications for the same product
        if not Notification.objects.filter(message=msg, is_read=False).exists():
            Notification.objects.create(message=msg)
