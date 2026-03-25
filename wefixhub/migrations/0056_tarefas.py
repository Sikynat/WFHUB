from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wefixhub', '0055_empresa_acesso_permanente'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TagTarefa',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=50)),
                ('cor', models.CharField(default='#6366f1', max_length=7)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags_tarefa', to='wefixhub.empresa')),
            ],
            options={
                'verbose_name': 'Tag de Tarefa',
                'verbose_name_plural': 'Tags de Tarefas',
                'db_table': 'wf_tag_tarefa',
            },
        ),
        migrations.AlterUniqueTogether(
            name='tagtarefa',
            unique_together={('empresa', 'nome')},
        ),
        migrations.CreateModel(
            name='Tarefa',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('descricao', models.TextField(blank=True, null=True)),
                ('prioridade', models.CharField(choices=[('ALTA', 'Alta'), ('MEDIA', 'Média'), ('BAIXA', 'Baixa')], default='MEDIA', max_length=10)),
                ('status', models.CharField(choices=[('A_FAZER', 'A Fazer'), ('EM_ANDAMENTO', 'Em Andamento'), ('REVISAO', 'Revisão'), ('CONCLUIDO', 'Concluído')], default='A_FAZER', max_length=20)),
                ('prazo', models.DateField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tarefas', to='wefixhub.empresa')),
                ('criado_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarefas_criadas', to=settings.AUTH_USER_MODEL)),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarefas_responsavel', to=settings.AUTH_USER_MODEL)),
                ('tags', models.ManyToManyField(blank=True, related_name='tarefas', to='wefixhub.tagtarefa')),
            ],
            options={
                'verbose_name': 'Tarefa',
                'verbose_name_plural': 'Tarefas',
                'db_table': 'wf_tarefa',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='ComentarioTarefa',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('autor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tarefa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comentarios', to='wefixhub.tarefa')),
            ],
            options={
                'verbose_name': 'Comentário de Tarefa',
                'verbose_name_plural': 'Comentários de Tarefas',
                'db_table': 'wf_comentario_tarefa',
                'ordering': ['criado_em'],
            },
        ),
        migrations.CreateModel(
            name='NotificacaoTarefa',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mensagem', models.CharField(max_length=300)),
                ('lida', models.BooleanField(default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('tarefa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes', to='wefixhub.tarefa')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_tarefa', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notificação de Tarefa',
                'verbose_name_plural': 'Notificações de Tarefas',
                'db_table': 'wf_notificacao_tarefa',
                'ordering': ['-criado_em'],
            },
        ),
    ]
