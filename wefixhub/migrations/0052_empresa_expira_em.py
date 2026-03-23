from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wefixhub', '0051_alter_wfclient_client_cnpj_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='expira_em',
            field=models.DateField(blank=True, null=True, verbose_name='Expira em'),
        ),
    ]
