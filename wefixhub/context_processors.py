from .models import Carrinho, NotificacaoTarefa


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


def notif_tarefas_count(request):
    """Injeta contagem de notificações de tarefas não lidas para staff."""
    if request.user.is_authenticated and request.user.is_staff:
        try:
            count = NotificacaoTarefa.objects.filter(
                usuario=request.user, lida=False
            ).count()
            return {'notif_tarefas_count': count}
        except Exception:
            pass
    return {'notif_tarefas_count': 0}
