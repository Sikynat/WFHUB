# wefixhub/templatetags/carrinho_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    # Tenta obter a chave original (que é um inteiro no loop)
    # Se não encontrar, tenta converter para string e buscar novamente
    return dictionary.get(str(key)) or dictionary.get(key)