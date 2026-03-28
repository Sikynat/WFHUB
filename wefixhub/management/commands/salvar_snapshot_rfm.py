"""
Management command: salvar_snapshot_rfm

Calcula o RFM atual para cada empresa e salva um snapshot mensal.
Deve ser executado 1x por mês (ex: cron no dia 1 de cada mês).

Uso:
    python manage.py salvar_snapshot_rfm
    python manage.py salvar_snapshot_rfm --empresa minha-empresa
    python manage.py salvar_snapshot_rfm --data 2025-01-01   # forçar data de referência
"""
from datetime import date
from django.core.management.base import BaseCommand
from wefixhub.models import Empresa, SnapshotRFM
from wefixhub.utils import calcular_rfm


class Command(BaseCommand):
    help = 'Salva snapshot mensal do RFM para todas as empresas'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, default=None,
                            help='Slug da empresa (omitir = todas)')
        parser.add_argument('--data', type=str, default=None,
                            help='Data de referência YYYY-MM-DD (omitir = hoje)')
        parser.add_argument('--forcar', action='store_true',
                            help='Sobrescreve snapshot existente do mesmo mês')

    def handle(self, *args, **options):
        if options['data']:
            data_ref = date.fromisoformat(options['data']).replace(day=1)
        else:
            hoje = date.today()
            data_ref = hoje.replace(day=1)

        empresas_qs = Empresa.objects.filter(ativo=True)
        if options['empresa']:
            empresas_qs = empresas_qs.filter(slug=options['empresa'])

        if not empresas_qs.exists():
            self.stderr.write('Nenhuma empresa encontrada.')
            return

        total_criados = 0
        total_ignorados = 0

        for empresa in empresas_qs:
            rfm = calcular_rfm(empresa=empresa)

            if not rfm['clientes']:
                self.stdout.write(f'  {empresa.slug}: sem clientes no RFM, pulando.')
                continue

            criados = 0
            ignorados = 0
            for c in rfm['clientes']:
                defaults = {
                    'nome_cliente': c['nome'],
                    'segmento':     c['segmento'],
                    'r_score':      c['r_score'],
                    'f_score':      c['f_score'],
                    'm_score':      c['m_score'],
                    'rfm_score':    c['rfm_score'],
                    'recencia':     c['recencia'],
                    'frequencia':   c['frequencia'],
                    'monetario':    c['monetario'],
                }
                if options['forcar']:
                    obj, created = SnapshotRFM.objects.update_or_create(
                        empresa=empresa,
                        data_ref=data_ref,
                        cod_cliente=c['codigo'],
                        defaults=defaults,
                    )
                    criados += 1
                else:
                    _, created = SnapshotRFM.objects.get_or_create(
                        empresa=empresa,
                        data_ref=data_ref,
                        cod_cliente=c['codigo'],
                        defaults=defaults,
                    )
                    if created:
                        criados += 1
                    else:
                        ignorados += 1

            self.stdout.write(
                f'  {empresa.slug}: {criados} clientes salvos, {ignorados} já existiam'
            )
            total_criados += criados
            total_ignorados += ignorados

        self.stdout.write(self.style.SUCCESS(
            f'\nSnapshot {data_ref:%m/%Y} concluído: {total_criados} criados, {total_ignorados} ignorados.'
        ))
