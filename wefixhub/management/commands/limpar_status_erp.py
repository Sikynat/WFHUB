# seu_app/management/commands/limpar_status_erp.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from wefixhub.models import StatusPedidoERP  # Ajuste para o nome real do seu app

class Command(BaseCommand):
    help = 'Remove registros do StatusPedidoERP com mais de 15 dias'

    def handle(self, *args, **options):
        data_limite = timezone.now() - timedelta(days=15)
        
        # Filtra registros cuja data de emissão é anterior a 15 dias atrás
        registros_antigos = StatusPedidoERP.objects.filter(emissao__lt=data_limite.date())
        quantidade = registros_antigos.count()
        
        registros_antigos.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Sucesso: {quantidade} registros antigos foram removidos.')
        )