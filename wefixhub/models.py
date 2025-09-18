from django.db import models

# Create your models here.

# Uf Model
class wefixhub_uf (models.Model):
    uf_id = models.AutoField(primary_key=True)
    uf_name = models.CharField(max_length=2)

    class Meta:
        db_table = 'wefixhub_uf'
        verbose_name = 'wefixhub_uf'
        verbose_name_plural = 'wefixhub_uf'
    
    def __str__(self):
        return self.uf_name

# Client Model

class WfClient(models.Model):
    client_id = models.AutoField(primary_key=True)
    client_code = models.IntegerField()
    client_name = models.CharField(max_length=128)
    client_cnpj = models.CharField(max_length=14, unique=True)
    client_adress = models.CharField(max_length=255)
    client_city = models.CharField(max_length=100)
    client_state = models.ForeignKey(wefixhub_uf,on_delete=models.PROTECT, related_name='state_uf')
    client_state_subscription = models.CharField(max_length=14, blank=True, null=True)
    client_date = models.DateField(blank=True, null=True)
    client_is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'wf_client'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.client_name

# Product model

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    product_code = models.CharField(max_length=5, unique=True)
    product_description = models.CharField(max_length=255, blank=True, null=True)
    product_group = models.CharField(max_length=32, blank=True, null=True)
    product_brand = models.CharField(max_length=32, blank=True, null=True)
    product_value = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        db_table = 'wf_products'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'

    def __str__(self):
        return self.product_description