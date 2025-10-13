# wefixhub/templatetags/custom_filters.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Substitui todas as ocorrências de um substring por outro.
    Uso: {{ value|replace:"antigo,novo" }}
    """
    if not isinstance(value, str):
        # Converte valores como Decimal para string antes de substituir
        value = str(value)
        
    try:
        # Divide o argumento em "antigo" e "novo"
        find_string, replace_string = arg.split(',', 1)
        return value.replace(find_string, replace_string)
    except ValueError:
        # Se o formato não for "antigo,novo", retorna o valor original
        return value
    
@register.filter
def replace(value, arg):
    """
    Substitui todas as ocorrências de um substring por outro.
    Uso: {{ valor|replace:"antigo,novo" }}
    """
    # Garante que o valor seja uma string (importante para DecimalFields)
    if not isinstance(value, str):
        value = str(value)
        
    try:
        # Divide o argumento em "antigo" e "novo"
        find_string, replace_string = arg.split(',', 1)
        return value.replace(find_string, replace_string)
    except ValueError:
        # Se o formato for inválido (sem vírgula), retorna o valor original
        return value