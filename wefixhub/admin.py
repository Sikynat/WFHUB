from django.contrib import admin
from django.contrib.auth.models import User
from .models import WfClient, Product, Pedido, ItemPedido, wefixhub_uf, Endereco

# Admin personalizado para WfClient
class ClientAdmin(admin.ModelAdmin):
    # Oculta o campo 'user' do formulário de adição/edição
    exclude = ('user',)
    
    # Exibição na lista de clientes
    list_display = ['client_is_active', 'client_id', 'client_code', 'client_name', 'client_cnpj', 'client_city', 'client_state_subscription', 'client_date']
    
    # Campos de busca
    search_fields = ['client_name', 'client_code', 'client_cnpj']

    def save_model(self, request, obj, form, change):
        # Se for um novo cliente (não uma edição)
        if not obj.pk:
            # Cria um novo usuário automaticamente com base no client_code
            username = str(obj.client_code)
            password = 'senha_temporaria_123'
            
            user = User.objects.create_user(username=username, password=password)
            
            # Vincula o novo usuário ao objeto WfClient
            obj.user = user
            
        # Salva o objeto no banco de dados
        super().save_model(request, obj, form, change)

# Admin para Product
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_id', 'product_code', 'product_description', 'product_brand', 'product_value']
    search_fields = ['product_id', 'product_description', 'product_brand', 'product_code']
    list_filter = ['status']

# Registra os modelos no painel administrativo
admin.site.register(WfClient, ClientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Pedido)
admin.site.register(ItemPedido)
admin.site.register(wefixhub_uf)