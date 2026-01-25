from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from django.http import HttpResponse # Necessário para exportação
from datetime import date # Necessário para data no nome do arquivo
import pandas as pd 
from .models import WfClient, Product, Pedido, ItemPedido, wefixhub_uf, Endereco, ItemPedidoIgnorado

# --- FUNÇÃO DE EXPORTAÇÃO (Adicionada) ---
def exportar_itens_ignorados_xlsx(modeladmin, request, queryset):
    """
    Ação para exportar os itens selecionados no admin para Excel.
    """
    # 1. Prepara os dados em uma lista de dicionários
    data = []
    for item in queryset:
        # Formata a data para ficar legível
        data_formatada = item.data_tentativa.strftime('%d/%m/%Y %H:%M') if item.data_tentativa else ""
        
        # Pega o nome do cliente de forma segura
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

    # 2. Cria o DataFrame
    df = pd.DataFrame(data)

    # 3. Cria a resposta HTTP com o tipo correto para Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="relatorio_erros_{date.today()}.xlsx"'

    # 4. Escreve o arquivo usando a engine do pandas/openpyxl
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens Ignorados')

    return response

exportar_itens_ignorados_xlsx.short_description = "Exportar selecionados para Excel"


# Admin personalizado para WfClient
class ClientAdmin(admin.ModelAdmin):
    # Oculta o campo 'user' do formulário de adição/edição
    exclude = ('user',)
    
    # Exibição na lista de clientes, usando o método 'nome_com_codigo'
    list_display = ['client_is_active', 'client_id', 'client_code', 'nome_com_codigo', 'client_cnpj', 'client_city', 'client_state_subscription', 'client_date', 'frete_preferencia', 'nota_fiscal_preferencia', 'observacao_preferencia', 'client_state']
    
    # Campos de busca
    search_fields = ['client_name', 'client_code', 'client_cnpj']
    
    # Adiciona a ação de edição
    actions = ['editar_cliente']

    # Organiza os campos no formulário de edição do cliente
    fieldsets = (
        (None, {
            'fields': (
                'client_code',
                'client_name',
                'client_cnpj',
                'client_adress',
                'client_city',
                'client_state',
                'client_state_subscription',
                'client_date',
                'client_is_active'
                
            )
        }),
        ('Preferências do Pedido', {
            'fields': ('frete_preferencia', 'nota_fiscal_preferencia', 'observacao_preferencia'),
            'description': 'Configure as opções padrão para este cliente.',
        }),
    )

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
    
    # Novo método para exibir o nome com o código
    def nome_com_codigo(self, obj):
        return f"{obj.client_name} ({obj.client_code})"
    
    # Define o nome da coluna no painel de admin
    nome_com_codigo.short_description = "Nome do Cliente"

# Admin para Product
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_description', 'date_product', 'product_value_sp', 'product_value_es')
    list_filter = ('date_product',)
    search_fields = ('product_code', 'product_description')


# Admin para ItemPedidoIgnorado
@admin.register(ItemPedidoIgnorado)
class ItemPedidoIgnoradoAdmin(admin.ModelAdmin):
    # Colunas da tabela
    list_display = (
        'id', 
        'get_pedido_link', 
        'get_cliente_codigo', 
        'codigo_produto', 
        'quantidade_tentada', 
        'motivo_erro', 
        'data_tentativa'
    )
    
    # Campos de busca
    search_fields = (
        'codigo_produto', 
        'motivo_erro', 
        'pedido__id', 
        'cliente__client_code', 
        'cliente__client_name'
    )
    
    # Filtros laterais
    list_filter = ('data_tentativa', 'motivo_erro')

    # --- AQUI REGISTRAMOS A AÇÃO DE EXPORTAR ---
    actions = [exportar_itens_ignorados_xlsx]
    # -------------------------------------------

    # --- LÓGICA PARA LIBERAR A CRIAÇÃO MANUAL ---
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Se 'obj' existe, significa que você está EDITANDO um registro existente
            # Bloqueia a edição para manter o histórico íntegro
            return ('pedido', 'cliente', 'codigo_produto', 'descricao_produto', 'quantidade_tentada', 'motivo_erro', 'data_tentativa')
        else:  # Se 'obj' é None, você está CRIANDO um novo
            # Libera tudo, exceto a data que é automática pelo sistema
            return ('data_tentativa',)

    # Link para o pedido
    def get_pedido_link(self, obj):
        if obj.pedido:
            return f"Pedido #{obj.pedido.id}"
        return "-"
    get_pedido_link.short_description = 'Pedido Original'

    # Código do Cliente
    def get_cliente_codigo(self, obj):
        if obj.cliente:
            return f"{obj.cliente.client_code} - {obj.cliente.client_name}"
        return "Cliente não identificado"
    get_cliente_codigo.short_description = 'Cliente'
    get_cliente_codigo.admin_order_field = 'cliente__client_code'

# Registra os modelos no painel administrativo
admin.site.register(WfClient, ClientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Pedido)
admin.site.register(ItemPedido)
admin.site.register(wefixhub_uf)
admin.site.register(Endereco)