from django import template
from django.conf import settings
from django.utils import formats
from django.utils.html import format_html

register = template.Library()


def _get_foto(user):
    """Retorna a URL da foto de perfil do usuário (membro ou cliente)."""
    try:
        if hasattr(user, 'perfil') and user.perfil.foto_perfil:
            return user.perfil.foto_perfil.url
    except Exception:
        pass
    try:
        if hasattr(user, 'wfclient') and user.wfclient.foto_perfil:
            return user.wfclient.foto_perfil.url
    except Exception:
        pass
    return None


@register.simple_tag
def avatar(user, size=32, classes=''):
    """
    Renderiza um avatar circular para um usuário.
    Usa a foto de perfil se disponível, senão mostra as iniciais.
    Uso: {% avatar user %} ou {% avatar user size=40 %}
    """
    if user is None:
        return format_html(
            '<span style="width:{s}px;height:{s}px;border-radius:50%;background:#9ca3af;display:inline-flex;align-items:center;justify-content:center;font-size:{fs}rem;font-weight:700;color:white;flex-shrink:0;" class="{c}">?</span>',
            s=size, fs=round(size * 0.4 / 16, 2), c=classes
        )
    foto_url = _get_foto(user)
    initials = (user.get_full_name() or user.username or '?')[:2].upper()
    if foto_url:
        return format_html(
            '<img src="{}" alt="{}" style="width:{s}px;height:{s}px;border-radius:50%;object-fit:cover;flex-shrink:0;" class="{}">',
            foto_url, initials, classes, s=size
        )
    return format_html(
        '<span style="width:{s}px;height:{s}px;border-radius:50%;background:#6366f1;display:inline-flex;align-items:center;justify-content:center;font-size:{fs}rem;font-weight:700;color:white;flex-shrink:0;" class="{c}">{i}</span>',
        s=size, fs=round(size * 0.38 / 16, 2), c=classes, i=initials
    )

@register.filter
def get_item(dictionary, key):
    """Acessa dicionário por chave variável: dict|get_item:key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def intcomma_br(value):
    """Formata número com separadores brasileiros: 1.234.567"""
    try:
        value = float(value)
        formatted = f'{value:,.0f}'
        return formatted.replace(',', '.')
    except (ValueError, TypeError):
        return value


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