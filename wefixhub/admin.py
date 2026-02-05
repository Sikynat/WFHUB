from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from django.http import HttpResponse # Necessário para exportação
from datetime import date # Necessário para data no nome do arquivo
import pandas as pd 
from .models import WfClient, Product, Pedido, ItemPedido, wefixhub_uf, Endereco, ItemPedidoIgnorado

# --- FUNÇÃO DE EXPORTAÇÃO ---
def exportar_itens_ignorados_xlsx(modeladmin, request, queryset):
    """
    Ação para exportar os itens selecionados no admin para Excel.
    """
    data = []
    for item in queryset:
        data_formatada = item.data_tentativa.strftime('%d/%m/%Y %H:%M') if item.data_tentativa else ""
        nome_cliente = f"{item.cliente.client_code} - {item.cliente.client_name}" if item.cliente else "N/A"
        
        data.append({
            'ID Erro': item.id,
            'Pedido Original': f"#{item.pedido.id}" if item.pedido else "N/A",
            'Cliente': nome_cliente,
            'Código Produto': item.codigo_produto,
            'Descrição (Tentativa)': item.descricao_produto,
            'Qtd Tentada': item.quantidade_tentada,
            'Motivo do Erro': item.motivo_erro,
            'Data da Tentativa': data_formatada
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="relatorio_erros_{date.today()}.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens Ignorados')

    return response

exportar_itens_ignorados_xlsx.short_description = "Exportar selecionados para Excel"


# --- ADMIN CLIENTES ---
class ClientAdmin(admin.ModelAdmin):
    exclude = ('user',)
    list_display = ['client_is_active', 'client_id', 'client_code', 'nome_com_codigo', 'client_cnpj', 'client_city', 'client_state_subscription', 'client_date', 'frete_preferencia', 'nota_fiscal_preferencia', 'observacao_preferencia', 'client_state']
    search_fields = ['client_name', 'client_code', 'client_cnpj']
    actions = ['editar_cliente']

    fieldsets = (
        (None, {
            'fields': (
                'client_code', 'client_name', 'client_cnpj', 'client_adress',
                'client_city', 'client_state', 'client_state_subscription',
                'client_date', 'client_is_active'
            )
        }),
        ('Preferências do Pedido', {
            'fields': ('frete_preferencia', 'nota_fiscal_preferencia', 'observacao_preferencia'),
            'description': 'Configure as opções padrão para este cliente.',
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            username = str(obj.client_code)
            password = 'senha_temporaria_123'
            user = User.objects.create_user(username=username, password=password)
            obj.user = user
        super().save_model(request, obj, form, change)

    def editar_cliente(self, request, queryset):
        if queryset.count() == 1:
            obj = queryset.first()
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.pk])
            return redirect(url)
        else:
            self.message_user(request, "Por favor, selecione apenas um cliente para editar.", level='WARNING')
    editar_cliente.short_description = "Editar cliente selecionado"
    
    def nome_com_codigo(self, obj):
        return f"{obj.client_name} ({obj.client_code})"
    nome_com_codigo.short_description = "Nome do Cliente"


# --- ADMIN PRODUTOS ---
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_description', 'date_product', 'product_value_sp', 'product_value_es')
    list_filter = ('date_product',)
    search_fields = ('product_code', 'product_description')


# --- ADMIN ITEM PEDIDO IGNORADO ---
@admin.register(ItemPedidoIgnorado)
class ItemPedidoIgnoradoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'get_pedido_link', 'get_cliente_codigo', 
        'codigo_produto', 'quantidade_tentada', 'motivo_erro', 'data_tentativa'
    )
    search_fields = ('codigo_produto', 'motivo_erro', 'pedido__id', 'cliente__client_code', 'cliente__client_name')
    list_filter = ('data_tentativa', 'motivo_erro')
    actions = [exportar_itens_ignorados_xlsx]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('pedido', 'cliente', 'codigo_produto', 'descricao_produto', 'quantidade_tentada', 'motivo_erro', 'data_tentativa')
        else:
            return ('data_tentativa',)

    def get_pedido_link(self, obj):
        if obj.pedido:
            return f"Pedido #{obj.pedido.id}"
        return "-"
    get_pedido_link.short_description = 'Pedido Original'

    def get_cliente_codigo(self, obj):
        if obj.cliente:
            return f"{obj.cliente.client_code} - {obj.cliente.client_name}"
        return "Cliente não identificado"
    get_cliente_codigo.short_description = 'Cliente'
    get_cliente_codigo.admin_order_field = 'cliente__client_code'


# --- ADMIN ITEM PEDIDO (NOVO/ATUALIZADO) ---
@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    # Colunas da tabela
    list_display = (
        'id', 
        'get_pedido_link',   # Link para o Pedido
        'get_cliente',       # Nome do Cliente
        'get_codigo_produto',# Código do Produto (Product)
        'produto',           # Descrição do Produto
        'quantidade',
        'get_total_item',    # Valor total
        'get_data_compra'    # Data (Pedido)
    )

    # Campos de Busca
    search_fields = (
        'pedido__id',                    # ID do Pedido
        'produto__product_code',         # Código do produto
        'produto__product_description',  # Descrição do produto
        'pedido__cliente__client_name',  # Nome do cliente
        'pedido__cliente__client_code'   # Código do cliente
    )

    # Filtros laterais
    list_filter = ('pedido__data_criacao', 'pedido__status')

    # Métodos Auxiliares
    def get_pedido_link(self, obj):
        if obj.pedido:
            # Gera URL para editar o pedido pai
            url = reverse('admin:%s_%s_change' % (obj.pedido._meta.app_label, obj.pedido._meta.model_name), args=[obj.pedido.pk])
            return format_html('<a href="{}">Pedido #{}</a>', url, obj.pedido.id)
        return "-"
    get_pedido_link.short_description = 'Pedido'

    def get_cliente(self, obj):
        if obj.pedido and obj.pedido.cliente:
            return f"{obj.pedido.cliente.client_code} - {obj.pedido.cliente.client_name}"
        return "N/A"
    get_cliente.short_description = 'Cliente'

    def get_codigo_produto(self, obj):
        return obj.produto.product_code
    get_codigo_produto.short_description = 'Cód. Produto'

    def get_data_compra(self, obj):
        if obj.pedido and obj.pedido.data_criacao:
            return obj.pedido.data_criacao.strftime('%d/%m/%Y %H:%M')
        return "-"
    get_data_compra.short_description = 'Data Compra'
    get_data_compra.admin_order_field = 'pedido__data_criacao'

    def get_total_item(self, obj):
        return f"R$ {obj.get_total():.2f}"
    get_total_item.short_description = 'Total'


# --- REGISTROS GERAIS ---
admin.site.register(WfClient, ClientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Pedido)
# ItemPedido já foi registrado com o decorator @admin.register acima
admin.site.register(wefixhub_uf)
admin.site.register(Endereco)