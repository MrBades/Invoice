from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    try:
        return value - arg
    except:
        return 0
