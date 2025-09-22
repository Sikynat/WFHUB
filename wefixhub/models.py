from django.db import models
from django.contrib.auth.models import User

# Modelo para UF
class wefixhub_uf (models.Model):
    uf_id = models.AutoField(primary_key=True)
    uf_name = models.CharField(max_length=2)

    class Meta:
        db_table = 'wefixhub_uf'
        verbose_name = 'wefixhub_uf'
        verbose_name_plural = 'wefixhub_uf'
    
    def __str__(self):
        return self.uf_name

# Modelo para Clientes
class WfClient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
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
        
# Modelo para Endereços
class Endereco(models.Model):
    cliente = models.ForeignKey(WfClient, on_delete=models.CASCADE, related_name='enderecos')
    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=10)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.ForeignKey(wefixhub_uf, on_delete=models.PROTECT, related_name='enderecos')
    cep = models.CharField(max_length=9)
    is_default = models.BooleanField(default=False) # Campo para definir como padrão

    def __str__(self):
        return f"{self.logradouro}, {self.numero} - {self.cidade}"

    def save(self, *args, **kwargs):
        # Se este endereço está sendo marcado como padrão...
        if self.is_default:
            # Desmarca qualquer outro endereço padrão para este cliente
            Endereco.objects.filter(cliente=self.cliente, is_default=True).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs) # Salva o endereço atual

# Modelo para Produtos
class Product(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ENTREGUE', 'Entregue'),
    ]

    product_id = models.AutoField(primary_key=True)
    product_code = models.CharField(max_length=5, unique=True)
    product_description = models.CharField(max_length=255, blank=True, null=True)
    product_group = models.CharField(max_length=32, blank=True, null=True)
    product_brand = models.CharField(max_length=32, blank=True, null=True)
    product_value = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')

    class Meta:
        db_table = 'wf_products'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'

    def __str__(self):
        return self.product_description

# Modelo de Pedido
class Pedido(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ENVIO', 'Em Envio'),
        ('ENTREGUE', 'Entregue'),
    ]
    
    cliente = models.ForeignKey(WfClient, on_delete=models.CASCADE, related_name='pedidos')
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_envio_solicitada = models.DateField(null=True, blank=True)
    endereco = models.ForeignKey(Endereco, on_delete=models.PROTECT, null=True, related_name='pedidos')

    def __str__(self):
        return f"Pedido #{self.id} de {self.cliente.client_name}"

    def get_total_geral(self):
        total = sum(item.get_total() for item in self.itens.all())
        return total

# Modelo de Item do Pedido
class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='itens_do_pedido')
    quantidade = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantidade} x {self.produto.product_description} em {self.pedido.id}"
        
    def get_total(self):
        return self.produto.product_value * self.quantidade