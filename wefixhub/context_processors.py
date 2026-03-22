from .models import Carrinho


def carrinho_count(request):
    """Injeta a quantidade de itens do carrinho em todos os templates."""
    if request.user.is_authenticated and not request.user.is_staff:
        try:
            carrinho = Carrinho.objects.filter(cliente=request.user.wfclient).first()
            if carrinho:
                return {'carrinho_count': carrinho.itens.count()}
        except Exception:
            pass
    return {'carrinho_count': 0}
