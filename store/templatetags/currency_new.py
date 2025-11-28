import json

from django import template

register = template.Library()


@register.filter
def rupees(value):
    """Format value as INR currency with 2 decimal places."""
    try:
        # Convert to float first to handle both string and numeric inputs
        amount = float(value) / 100  # Convert cents to rupees
        # Format with 2 decimal places and add rupee symbol
        return f"₹{amount:,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


@register.filter
def pretty_json(value):
    try:
        return json.dumps(value, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        return value
