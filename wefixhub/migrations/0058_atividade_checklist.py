from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wefixhub', '0057_alter_comentariotarefa_id_alter_notificacaotarefa_id_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AtividadeTarefa',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descricao', models.CharField(max_length=300)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('tarefa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='atividades', to='wefixhub.tarefa')),
                ('usuario', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Atividade de Tarefa',
                'verbose_name_plural': 'Atividades de Tarefas',
                'db_table': 'wf_atividade_tarefa',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='ChecklistItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.CharField(max_length=200)),
                ('concluido', models.BooleanField(default=False)),
                ('ordem', models.PositiveSmallIntegerField(default=0)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('tarefa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checklist', to='wefixhub.tarefa')),
            ],
            options={
                'verbose_name': 'Item de Checklist',
                'verbose_name_plural': 'Itens de Checklist',
                'db_table': 'wf_checklist_item',
                'ordering': ['ordem', 'criado_em'],
            },
        ),
    ]
