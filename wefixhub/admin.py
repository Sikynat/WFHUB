from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from .models import WfClient, Product, Pedido, ItemPedido, wefixhub_uf, Endereco

# Admin personalizado para WfClient
class ClientAdmin(admin.ModelAdmin):
    # Oculta o campo 'user' do formulário de adição/edição
    exclude = ('user',)
    
    # Exibição na lista de clientes
    list_display = ['client_is_active', 'client_id', 'client_code', 'client_name', 'client_cnpj', 'client_city', 'client_state_subscription', 'client_date']
    
    # Campos de busca
    search_fields = ['client_name', 'client_code', 'client_cnpj']
    
    # Adiciona a ação de edição
    actions = ['editar_cliente']

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
    
    def editar_cliente(self, request, queryset):
        # Ação que redireciona para a página de edição de um único item
        if queryset.count() == 1:
            obj = queryset.first()
            # Esta linha gera a URL para a página de edição do objeto no admin
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.pk])
            return redirect(url)
        else:
            self.message_user(request, "Por favor, selecione apenas um cliente para editar.", level='WARNING')

    editar_cliente.short_description = "Editar cliente selecionado"

# Admin para Product (declaração única e correta)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_description', 'date_product', 'product_value_sp', 'product_value_es')
    list_filter = ('date_product',)
    search_fields = ('product_code', 'product_description')

# Registra os modelos no painel administrativo
admin.site.register(WfClient, ClientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Pedido)
admin.site.register(ItemPedido)
admin.site.register(wefixhub_uf)
admin.site.register(Endereco)