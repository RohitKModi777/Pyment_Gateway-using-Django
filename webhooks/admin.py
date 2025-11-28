from django.contrib import admin

from .models import WebhookLog


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "received_at", "verified", "replay_count"]
    list_filter = ["provider", "verified", "received_at"]
    search_fields = ["payload", "signature_header"]
    readonly_fields = ["received_at", "payload_pretty", "headers_pretty"]
    actions = ["replay_webhooks"]

    def event_type(self, obj):
        return obj.payload.get("event", "unknown")
    event_type.short_description = "Event"

    def payload_pretty(self, obj):
        import json
        return json.dumps(obj.payload, indent=2)
    payload_pretty.short_description = "Payload"

    def headers_pretty(self, obj):
        import json
        return json.dumps(obj.headers, indent=2)
    headers_pretty.short_description = "Headers"

    @admin.action(description="Replay selected webhooks")
    def replay_webhooks(self, request, queryset):
        from .views import process_razorpay_event
        count = 0
        for log in queryset:
            if log.verified:
                process_razorpay_event(log.payload, log, replay=True)
                count += 1
        self.message_user(request, f"{count} webhooks replayed successfully.")
