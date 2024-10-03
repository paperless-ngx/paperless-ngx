from django import template

register = template.Library()


@register.filter("get_cf_value")
def get_cf_value(custom_field_data: dict[str, dict[str, str]], name: str):
    """
    See https://stackoverflow.com/questions/2970244/django-templates-value-of-dictionary-key-with-a-space-in-it/2970337#2970337
    """
    data = custom_field_data[name]["value"]
    return data
