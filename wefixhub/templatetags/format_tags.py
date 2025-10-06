from django import template
from django.conf import settings
from django.utils import formats

register = template.Library()

@register.filter
def format_br(value):
    try:
        # Converte o valor para float, se ainda não for
        value = float(value)
        # Usa o localize para formatar o número no padrão brasileiro
        return formats.localize(value, use_l10n=True)
    except (ValueError, TypeError):
        # Retorna o valor original se não puder ser convertido
        return value