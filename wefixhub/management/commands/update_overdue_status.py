# seu_app/management/commands/update_overdue_status.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import Pedido # Ajuste '...models' para o nome do seu app, ex: 'pedidos.models'

class Command(BaseCommand):
    help = 'Atualiza o status de pedidos não finalizados para "Atrasado" se a data de expedição já passou.'

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        self.stdout.write(f"Verificando pedidos com data de expedição anterior a {hoje.strftime('%d/%m/%Y')}...")

        # Filtra os pedidos que:
        # 1. Tenham data de envio solicitada no passado (__lt = less than)
        # 2. NÃO estejam com status 'FINALIZADO' ou 'CANCELADO'
        pedidos_para_atualizar = Pedido.objects.filter(
            data_envio_solicitada__lt=hoje
        ).exclude(
            status__in=['FINALIZADO', 'CANCELADO']
        )
        
        # Opcional: Para evitar atualizações desnecessárias, exclua também os que já estão atrasados.
        pedidos_atrasados = pedidos_para_atualizar.exclude(status='ATRASADO')

        if not pedidos_atrasados.exists():
            self.stdout.write(self.style.SUCCESS("Nenhum pedido novo para marcar como atrasado."))
            return

        # Atualiza todos os pedidos encontrados de uma só vez para 'ATRASADO'
        # Isso é muito mais eficiente do que um loop
        num_pedidos_atualizados = pedidos_atrasados.update(status='ATRASADO')

        self.stdout.write(
            self.style.SUCCESS(
                f'Sucesso! {num_pedidos_atualizados} pedido(s) foram marcados como "Atrasado".'
            )
        )