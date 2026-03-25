from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wefixhub', '0059_notificacaopedido'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ComentarioPedido',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField()),
                ('interno', models.BooleanField(default=False, verbose_name='Nota interna (só staff)')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('autor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('pedido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comentarios_pedido', to='wefixhub.pedido')),
            ],
            options={
                'verbose_name': 'Comentário de Pedido',
                'verbose_name_plural': 'Comentários de Pedidos',
                'db_table': 'wf_comentario_pedido',
                'ordering': ['criado_em'],
            },
        ),
    ]
