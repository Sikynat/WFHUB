from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wefixhub', '0058_atividade_checklist'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificacaoPedido',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mensagem', models.CharField(max_length=300)),
                ('lida', models.BooleanField(default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_pedido', to='wefixhub.empresa')),
                ('pedido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_pedido', to='wefixhub.pedido')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_pedido', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notificação de Pedido',
                'verbose_name_plural': 'Notificações de Pedidos',
                'db_table': 'wf_notificacao_pedido',
                'ordering': ['-criado_em'],
            },
        ),
    ]
