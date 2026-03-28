import logging
import sys
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class WefixhubConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wefixhub'

    def ready(self):
        # Só inicia o scheduler no processo web (gunicorn ou runserver)
        # Evita rodar em migrate, test, shell, management commands, etc.
        is_web = (
            'gunicorn' in sys.argv[0]
            or ('runserver' in sys.argv and '--noreload' not in sys.argv)
            or 'RUN_MAIN' in __import__('os').environ  # django runserver worker
        )
        if not is_web:
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            from django_apscheduler.jobstores import DjangoJobStore
            from wefixhub.jobs import salvar_snapshot_rfm_job

            scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
            scheduler.add_jobstore(DjangoJobStore(), 'default')

            # Todo dia 30 às 23:00 (horário de Brasília)
            scheduler.add_job(
                salvar_snapshot_rfm_job,
                trigger=CronTrigger(day=30, hour=23, minute=0),
                id='salvar_snapshot_rfm',
                name='Snapshot RFM mensal (dia 30)',
                jobstore='default',
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=3600,  # executa em até 1h depois se o servidor estiver fora
            )

            scheduler.start()
            logger.info('APScheduler iniciado — snapshot RFM agendado para dia 30 às 23h.')
        except Exception as e:
            logger.warning(f'APScheduler nao iniciou: {e}')
