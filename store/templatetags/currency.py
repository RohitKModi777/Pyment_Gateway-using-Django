import json

from django import template

register = template.Library()


@register.filter
def rupees(value):
    try:
        return f"{int(value) / 100:.2f}"
    except (TypeError, ValueError):
        return value


@register.filter
def pretty_json(value):
    try:
        return json.dumps(value, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        return value

