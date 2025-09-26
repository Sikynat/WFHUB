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
        if self.is_default:
            Endereco.objects.filter(cliente=self.cliente, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs) # Salva o endereço atual

# Modelo para Produtos
# Modelo para Produtos
class Product(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ENTREGUE', 'Entregue'),
    ]

    product_id = models.AutoField(primary_key=True)
    product_code = models.CharField(max_length=20, unique=True)
    product_description = models.CharField(max_length=255, blank=True, null=True)
    product_group = models.CharField(max_length=32, blank=True, null=True)
    product_brand = models.CharField(max_length=32, blank=True, null=True)
    
    # NOVOS CAMPOS PARA ARMAZENAR OS VALORES
    product_value_sp = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    product_value_es = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    # NOVO CAMPO
    date_product = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'wf_products'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'

    def __str__(self):
        return self.product_description or self.product_code or ''

# Modelo de Pedido
class Pedido(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ENVIO', 'Em Envio'),
        ('ENTREGUE', 'Entregue'),
    ]
    
    cliente = models.ForeignKey(WfClient, on_delete=models.CASCADE, related_name='pedidos_cliente')
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_envio_solicitada = models.DateField(null=True, blank=True)
    endereco = models.ForeignKey(Endereco, on_delete=models.PROTECT, null=True, related_name='pedidos_endereco')

    def __str__(self):
        return f"Pedido #{self.id} de {self.cliente.client_name} - Status: {self.status}"

    def get_total_geral(self):
        # A lógica agora garante que os valores sejam números antes de somar
        total = 0
        for item in self.itens.all():
            if self.cliente.client_state.uf_name == 'SP':
                valor = item.valor_unitario_sp
            elif self.cliente.client_state.uf_name == 'ES':
                valor = item.valor_unitario_es
            else:
                # Caso o estado não seja SP ou ES, usa SP como padrão
                valor = item.valor_unitario_sp
            
            # Garante que o valor não seja nulo antes de multiplicar
            valor_final = valor if valor is not None else 0
            total += valor_final * (item.quantidade if item.quantidade is not None else 0)
            
        return total

# Modelo de Item do Pedido
class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='itens_do_pedido') # Alterado para PROTECT para evitar deleção
    quantidade = models.IntegerField(default=1)
    
    # NOVOS CAMPOS PARA CONGELAR O PREÇO
    valor_unitario_sp = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    valor_unitario_es = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.quantidade} x {self.produto.product_description} em {self.pedido.id}"
        
    def get_total(self):
        # **NOVO CÓDIGO AQUI**
        # Lógica para o total do item
        # Garante que o valor não seja nulo
        valor_sp = self.valor_unitario_sp if self.valor_unitario_sp is not None else 0
        valor_es = self.valor_unitario_es if self.valor_unitario_es is not None else 0

        if self.pedido.cliente.client_state.uf_name == 'SP':
            valor = valor_sp
        elif self.pedido.cliente.client_state.uf_name == 'ES':
            valor = valor_es
        else:
            valor = valor_sp # Valor padrão
        
        return valor * self.quantidade