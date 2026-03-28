"""
Jobs agendados via APScheduler.
Cada função aqui é chamada automaticamente pelo scheduler em apps.py.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


def salvar_snapshot_rfm_job():
    """
    Salva o snapshot RFM de todas as empresas ativas.
    Executado automaticamente todo dia 30 às 23h via APScheduler.
    Equivalente a: python manage.py salvar_snapshot_rfm
    """
    from wefixhub.models import Empresa, SnapshotRFM
    from wefixhub.utils import calcular_rfm

    hoje = date.today()
    data_ref = hoje.replace(day=1)

    empresas = Empresa.objects.filter(ativo=True)
    total_criados = 0

    for empresa in empresas:
        rfm = calcular_rfm(empresa=empresa)
        if not rfm['clientes']:
            continue

        criados = 0
        for c in rfm['clientes']:
            _, created = SnapshotRFM.objects.get_or_create(
                empresa=empresa,
                data_ref=data_ref,
                cod_cliente=c['codigo'],
                defaults={
                    'nome_cliente': c['nome'],
                    'segmento':     c['segmento'],
                    'r_score':      c['r_score'],
                    'f_score':      c['f_score'],
                    'm_score':      c['m_score'],
                    'rfm_score':    c['rfm_score'],
                    'recencia':     c['recencia'],
                    'frequencia':   c['frequencia'],
                    'monetario':    c['monetario'],
                },
            )
            if created:
                criados += 1

        logger.info(f'Snapshot RFM {data_ref:%m/%Y} — {empresa.slug}: {criados} clientes salvos.')
        total_criados += criados

    logger.info(f'Job salvar_snapshot_rfm concluido: {total_criados} registros criados.')
