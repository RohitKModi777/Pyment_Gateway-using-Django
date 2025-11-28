from django.db import models

class WebhookLog(models.Model):
    PROVIDER_CHOICES = [
        ("razorpay", "Razorpay"),
    ]

    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    payload = models.JSONField()
    headers = models.JSONField(default=dict, blank=True)
    signature_header = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    replay_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-received_at",)

    def __str__(self):
        return f"{self.provider} webhook @ {self.received_at:%Y-%m-%d %H:%M:%S}"
