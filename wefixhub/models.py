from django.db import models

# Create your models here.

class UF(models.Model):
    uf_id = models.AutoField(primary_key=True)
    uf_name = models.CharField(max_length=2)



class WfClient(models.Model):
    client_id = models.AutoField(primary_key=True)
    client_code = models.IntegerField()
    client_name = models.CharField(max_length=128)
    client_cnpj = models.CharField(max_length=14, unique=True)
    client_adress = models.CharField(max_length=255)
    client_city = models.CharField(max_length=100)
    client_state = models.ForeignKey(UF,on_delete=models.PROTECT, related_name='state_uf')
    client_state_subscription = models.CharField(max_length=14, blank=True, null=True)
    client_date = models.DateField(blank=True, null=True)
    client_is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'wf_client'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.client_name