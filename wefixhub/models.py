from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
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
# Seu arquivo models.py

# ... (seus outros modelos e imports)

# Modelo para Clientes
class WfClient(models.Model):
    # Opções de frete (copiadas do Pedido)
    FRETE_CHOICES = [
        ('SEDEX', 'Sedex'),
        ('CORREIOS', 'Correios'),
        ('ONIBUS', 'Ônibus'),
        ('TRANSPORTADORA', 'Transportadora'),
         ('RETIRADA', 'Retirada'), # Nova opção
    ]

    # Opções de nota fiscal (copiadas do Pedido)
    NOTA_FISCAL_CHOICES = [
        ('COM', 'Com Nota Fiscal'),
        ('SEM', 'Sem Nota Fiscal'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    client_id = models.AutoField(primary_key=True)
    client_code = models.IntegerField(unique=True)
    client_name = models.CharField(max_length=128)
    client_cnpj = models.CharField(max_length=14, unique=True)
    client_adress = models.CharField(max_length=255)
    client_city = models.CharField(max_length=100)
    client_state = models.ForeignKey(wefixhub_uf, on_delete=models.PROTECT, related_name='state_uf')
    client_state_subscription = models.CharField(max_length=14, blank=True, null=True)
    client_date = models.DateField(blank=True, null=True)
    client_is_active = models.BooleanField(default=False)
    
    # NOVOS CAMPOS PARA SALVAR AS PREFERÊNCIAS
    frete_preferencia = models.CharField(max_length=20, choices=FRETE_CHOICES, default='CORREIOS', null=True, blank=True)
    nota_fiscal_preferencia = models.CharField(max_length=3, choices=NOTA_FISCAL_CHOICES, default='SEM', null=True, blank=True)

    # Campo de observação padra

    observacao_preferencia = models.TextField(blank=True, null=True, verbose_name="Observação Padrão") # <-- Adicione esta linha


    class Meta:
        db_table = 'wf_client'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
         return f"{self.client_code} - ({self.client_name})"
        
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
        ('ENTREGUE', 'Entregue'),
        ('EM_ENVIO', 'Em Envio'),
        #novos
        ('ORCAMENTO', 'Orçamento'),
        ('FINANCEIRO', 'Analise De Credito'),
        ('SEPARACAO', 'Separação'),
        ('EXPEDICAO', 'Expedição'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
        ('ATRASADO', 'Atrasado'),
    ]

     # NOVO: Opções de frete
    FRETE_CHOICES = [
        ('SEDEX', 'Sedex'),
        ('CORREIOS', 'Correios'),
        ('ONIBUS', 'Ônibus'),
        ('TRANSPORTADORA', 'Transportadora'),
        ('RETIRADA', 'Retirada'), # Nova opção
    ]
    
    NOTA_FISCAL_CHOICES = [
        ('COM', 'Com Nota Fiscal'),
        ('SEM', 'Sem Nota Fiscal'),
    ]

    
    cliente = models.ForeignKey(WfClient, on_delete=models.CASCADE, related_name='pedidos_cliente')
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_envio_solicitada = models.DateField(null=True, blank=True)
    endereco = models.ForeignKey(Endereco, on_delete=models.PROTECT, null=True, related_name='pedidos_endereco')
    frete_option = models.CharField(max_length=20, choices=FRETE_CHOICES, default='CORREIOS', null=True, blank=True)
    nota_fiscal = models.CharField(max_length=3, choices=NOTA_FISCAL_CHOICES, default='SEM', null=True, blank=True)
    orcamento_pdf = models.FileField(upload_to='orcamentos/', blank=True, null=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_criados')
    observacao = models.TextField(blank=True, null=True)

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
    produto = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='itens_do_pedido')
    quantidade = models.IntegerField(default=1)
    
    # Campos para congelar o preço no momento da criação do pedido
    valor_unitario_sp = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    valor_unitario_es = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # O campo valor_unitario pode ser removido pois os valores são armazenados acima
    # valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.quantidade} x {self.produto.product_description} em {self.pedido.id}"

    def get_total(self):
        """
        Calcula o subtotal do item do pedido com base no estado do cliente.
        """
        # Verifica se o pedido e o cliente existem antes de acessar
        if self.pedido and self.pedido.cliente and self.pedido.cliente.client_state:
            uf = self.pedido.cliente.client_state.uf_name
            
            if uf == 'SP':
                valor = self.valor_unitario_sp
            elif uf == 'ES':
                valor = self.valor_unitario_es
            else:
                # Retorna zero ou o valor padrão, caso o estado não seja SP ou ES
                valor = self.valor_unitario_sp if self.valor_unitario_sp is not None else Decimal('0.00')

            # Garante que o valor e a quantidade não sejam nulos antes de multiplicar
            valor_final = valor if valor is not None else Decimal('0.00')
            quantidade_final = self.quantidade if self.quantidade is not None else 0
            
            return valor_final * quantidade_final
            
        return Decimal('0.00') 