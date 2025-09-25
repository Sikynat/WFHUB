from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth
from .models import Product, Pedido, ItemPedido, WfClient
from django.http import HttpResponse
from django.utils import timezone
import openpyxl
from .models import Pedido
from datetime import datetime, timedelta
from .forms import WfClientForm
from .forms import EnderecoForm
from .forms import EnderecoForm # Adicionando o novo formulário
from django.db import connection
import pandas as pd
from django.shortcuts import render
import numpy as np
from .models import Product, WfClient, Endereco, ItemPedido, Pedido
from django.db import transaction
from django.contrib import messages
import datetime



# View para a página inicial com filtros e paginação
def home(request):
    # Lógica de filtragem e busca
    codigo = request.GET.get('codigo', None)
    descricao = request.GET.get('descricao', None)
    grupo = request.GET.get('grupo', None)
    marca = request.GET.get('marca', None)

    # NOVO FILTRO: Apenas produtos com data de hoje
    products = Product.objects.filter(date_product=datetime.date.today()).order_by('product_code')

    if codigo:
        products = products.filter(product_code__icontains=codigo)
    if descricao:
        products = products.filter(product_description__icontains=descricao)
    if grupo:
        products = products.filter(product_group__icontains=grupo)
    if marca:
        products = products.filter(product_brand__icontains=marca)
    
    # Lógica de controle de preço
    preco_exibido = None
    cliente_logado = None

    if request.user.is_authenticated:
        if request.user.is_staff:
            preco_exibido = 'todos'
        else:
            try:
                cliente_logado = request.user.wfclient
                if cliente_logado.client_state.uf_name == 'SP':
                    preco_exibido = 'sp'
                    # FILTRO: Remove produtos com valor 0 para SP
                    products = products.exclude(product_value_sp=0)
                elif cliente_logado.client_state.uf_name == 'ES':
                    preco_exibido = 'es'
                    # FILTRO: Remove produtos com valor 0 para ES
                    products = products.exclude(product_value_es=0)
            except WfClient.DoesNotExist:
                # Se não for cliente de SP ou ES, não exibe produtos
                products = Product.objects.none()
    
    # Se o usuário não estiver autenticado, não exibe nenhum produto
    if not request.user.is_authenticated:
        products = Product.objects.none()
    
    # Paginação
    paginator = Paginator(products, 10) 
    page = request.GET.get('page')

    try:
        product_list = paginator.page(page)
    except PageNotAnInteger:
        product_list = paginator.page(1)
    except EmptyPage:
        product_list = paginator.page(paginator.num_pages)
        
    context = {
        'product_list': product_list,
        'cliente_logado': cliente_logado,
        'preco_exibido': preco_exibido,
    }
            
    return render(request, 'home.html', context)
"""
    # Lógica de Paginação:
    paginator = Paginator(product_list, 10)
    page = request.GET.get('page')
    try:
        produtos_na_pagina = paginator.page(page)
    except PageNotAnInteger:
        produtos_na_pagina = paginator.page(1)
    except EmptyPage:
        produtos_na_pagina = paginator.page(paginator.num_pages)
    
    # NOVO: Puxa o objeto WfClient do usuário logado
    cliente_logado = None
    if request.user.is_authenticated:
        try:
            cliente_logado = request.user.wfclient
        except WfClient.DoesNotExist:
            cliente_logado = None

    carrinho_da_sessao = request.session.get('carrinho', {})
    contexto = {
        'titulo': 'Página Inicial',
        'product_list': produtos_na_pagina,
        'carrinho': carrinho_da_sessao,
        'cliente_logado': cliente_logado, # NOVO: Adiciona o cliente ao contexto
    }
    return render(request, 'home.html', contexto)"""

# Inicio gerar pedido

@login_required
def gerar_pedido(request):
    if request.method == 'POST':
        carrinho_da_sessao = {}
        for key, value in request.POST.items():
            if key.startswith('quantidade_') and value.isdigit() and int(value) > 0:
                product_id = key.split('_')[1]
                quantidade = int(value)
                carrinho_da_sessao[product_id] = quantidade
        
        request.session['carrinho'] = carrinho_da_sessao
        request.session.modified = True
        
        return redirect('checkout')
    
    return redirect('home')


# Fim gerar pedido

# Inicio do carrinho

@login_required
def carrinho(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    carrinho_detalhes = []
    total_geral = 0
    
    # Lógica para determinar o valor de preço a ser usado
    preco_exibido = None
    if request.user.is_authenticated:
        if request.user.is_staff:
            preco_exibido = 'todos'
        else:
            try:
                cliente_logado = request.user.wfclient
                if cliente_logado.client_state.uf_name == 'SP':
                    preco_exibido = 'sp'
                elif cliente_logado.client_state.uf_name == 'ES':
                    preco_exibido = 'es'
            except WfClient.DoesNotExist:
                pass

    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            product = Product.objects.get(product_id=product_id)
            
            # ALTERAÇÃO AQUI: A view do carrinho deve usar o preço atual do produto
            # já que o pedido ainda não foi gerado. A lógica é a mesma que você já tem.
            if preco_exibido == 'sp':
                valor_unitario = product.product_value_sp
            elif preco_exibido == 'es':
                valor_unitario = product.product_value_es
            elif preco_exibido == 'todos':
                valor_unitario = product.product_value_sp # Ou ES, à sua escolha
            else:
                valor_unitario = 0

            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item
            
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item
            })
        except Product.DoesNotExist:
            continue
    
    contexto = {
        'titulo': 'Carrinho de Compras',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral,
        'preco_exibido': preco_exibido
    }
    
    return render(request, 'carrinho.html', contexto)

# Fim do carrinho


@login_required
def remover_item_carrinho(request, product_id):
    carrinho = request.session.get('carrinho', {})
    if str(product_id) in carrinho:
        del carrinho[str(product_id)]
        request.session.modified = True
    return redirect('carrinho')

@login_required
def atualizar_carrinho(request):
    if request.method == 'POST':
        carrinho = request.session.get('carrinho', {})
        for key, value in request.POST.items():
            if key.startswith('quantidade_') and value.isdigit():
                product_id = key.split('_')[1]
                quantidade = int(value)
                if quantidade > 0:
                    carrinho[product_id] = quantidade
                else:
                    del carrinho[product_id]
        request.session.modified = True
    return redirect('carrinho')

@login_required
def limpar_carrinho(request):
    if 'carrinho' in request.session:
        del request.session['carrinho']
        request.session.modified = True
    return redirect('carrinho')


# Inicio Checkout
@login_required
def checkout(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    if not carrinho_da_sessao:
        messages.error(request, 'Seu carrinho está vazio.')
        return redirect('home')

    carrinho_detalhes = []
    total_geral = 0
    preco_exibido = None

    try:
        cliente_logado = request.user.wfclient
        if request.user.is_staff:
            preco_exibido = 'todos'
        else:
            if cliente_logado.client_state.uf_name == 'SP':
                preco_exibido = 'sp'
            elif cliente_logado.client_state.uf_name == 'ES':
                preco_exibido = 'es'
    except WfClient.DoesNotExist:
        messages.error(request, 'Usuário não tem um cliente associado.')
        return redirect('home')

    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            product = get_object_or_404(Product, product_id=product_id)
            
            if preco_exibido == 'sp':
                valor_unitario = product.product_value_sp
            elif preco_exibido == 'es':
                valor_unitario = product.product_value_es
            else:
                valor_unitario = product.product_value_sp
            
            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item
            
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
            })
        except Product.DoesNotExist:
            continue
    
    if request.method == 'POST':
        endereco_id = request.POST.get('endereco_selecionado')
        data_envio = request.POST.get('data_envio')
        
        try:
            endereco_selecionado = Endereco.objects.get(id=endereco_id, cliente=cliente_logado)
            data_envio = datetime.datetime.strptime(data_envio, '%Y-%m-%d').date()
        except (Endereco.DoesNotExist, ValueError):
            messages.error(request, 'Endereço ou data de envio inválidos.')
            return redirect('checkout')
        
        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=cliente_logado,
                endereco=endereco_selecionado,
                data_envio_solicitada=data_envio,
            )
            
            for item in carrinho_detalhes:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=item['product'],
                    quantidade=item['quantidade'],
                    valor_unitario_sp=item['product'].product_value_sp,
                    valor_unitario_es=item['product'].product_value_es,
                )

        if 'carrinho' in request.session:
            del request.session['carrinho']

        # CÓDIGO A SER EXECUTADO
        response = HttpResponse('<script>localStorage.clear(); window.location.href = "/";</script>')
        return response
    
    enderecos = Endereco.objects.filter(cliente=cliente_logado)
    contexto = {
        'titulo': 'Confirmação de Compra',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral,
        'enderecos': enderecos,
        'preco_exibido': preco_exibido,
    }
    return render(request, 'checkout.html', contexto)


# Fim Checkout

# Inicio salvar pedido

@login_required
def salvar_pedido(request):
    if request.method == 'POST':
        endereco_id = request.POST.get('endereco')
        data_envio = request.POST.get('data_envio')

        try:
            endereco_selecionado = Endereco.objects.get(id=endereco_id, cliente=request.user.wfclient)
            # ALTERAÇÃO AQUI: Use datetime.datetime.strptime()
            data_envio = datetime.datetime.strptime(data_envio, '%Y-%m-%d').date()
        except (Endereco.DoesNotExist, ValueError):
            messages.error(request, 'Endereço ou data de envio inválidos.')
            return redirect('checkout')
        
        # ... (restante do código para salvar o pedido)
        # O restante do seu código aqui...

    return redirect('checkout')

# Fim Salvar Pedido

def pedido_concluido(request):
    return render(request, 'pedido_concluido.html')

@login_required
def historico_pedidos(request):
    try:
        cliente_logado = request.user.wfclient
    except WfClient.DoesNotExist:
        return redirect('home')

    pedidos_qs = Pedido.objects.filter(cliente=cliente_logado).order_by('-data_criacao')

    # Lógica de Paginação
    paginator = Paginator(pedidos_qs, 10) # 10 pedidos por página para o cliente
    page = request.GET.get('page')

    try:
        pedidos = paginator.page(page)
    except PageNotAnInteger:
        pedidos = paginator.page(1)
    except EmptyPage:
        pedidos = paginator.page(paginator.num_pages)

    contexto = {
        'pedidos': pedidos,
    }
    return render(request, 'historico_pedidos.html', contexto)

#Inicio detalhes pedido

@login_required
def detalhes_pedido(request, pedido_id):
    try:
        cliente_logado = request.user.wfclient
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente_logado)
        
        # Lógica de controle de preço
        preco_exibido = None
        if request.user.is_staff:
            preco_exibido = 'todos'
        elif cliente_logado.client_state.uf_name == 'SP':
            preco_exibido = 'sp'
        elif cliente_logado.client_state.uf_name == 'ES':
            preco_exibido = 'es'

        itens_detalhes = []
        total_geral = 0
        itens = ItemPedido.objects.filter(pedido=pedido)

        for item in itens:
            if preco_exibido == 'sp':
                valor_unitario = item.valor_unitario_sp
            elif preco_exibido == 'es':
                valor_unitario = item.valor_unitario_es
            elif preco_exibido == 'todos':
                valor_unitario_sp = item.valor_unitario_sp
                valor_unitario_es = item.valor_unitario_es
                valor_unitario = valor_unitario_sp
            else:
                valor_unitario = 0
            
            valor_total_item = valor_unitario * item.quantidade
            total_geral += valor_total_item

            itens_detalhes.append({
                'item': item,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
                'valor_unitario_sp': item.valor_unitario_sp,
                'valor_unitario_es': item.valor_unitario_es
            })

        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens_detalhes': itens_detalhes,
            'total_geral': total_geral,
            'preco_exibido': preco_exibido
        }
        
        # Redireciona para a home
        return render(request, 'detalhes_pedido.html', contexto)
    
    except WfClient.DoesNotExist:
        messages.error(request, "Erro: Cliente não encontrado.")
        return redirect('pedidos')
    except Pedido.DoesNotExist:
        messages.error(request, "Erro: Pedido não encontrado.")
        return redirect('pedidos')

# Fim detalhes pedido

@staff_member_required
def dashboard_admin(request):
    total_clientes = WfClient.objects.count()
    total_pedidos = Pedido.objects.count()
    total_vendas_agregadas = ItemPedido.objects.aggregate(total_vendas=Sum('produto__product_value'))
    valor_total_vendas = total_vendas_agregadas['total_vendas'] if total_vendas_agregadas['total_vendas'] else 0
    pedidos_recentes_qs = Pedido.objects.all().order_by('-data_criacao')[:5]
    pedidos_com_total = []
    for pedido in pedidos_recentes_qs:
        pedidos_com_total.append({
            'id': pedido.id,
            'cliente': pedido.cliente,
            'data_criacao': pedido.data_criacao,
            'total': pedido.get_total_geral()
        })
    contexto = {
        'titulo': 'Dashboard Administrativo',
        'total_clientes': total_clientes,
        'total_pedidos': total_pedidos,
        'total_vendas': valor_total_vendas,
        'pedidos_recentes': pedidos_com_total
    }
    return render(request, 'dashboard.html', contexto)

# View para exportação de pedidos
@staff_member_required
def exportar_pedidos_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="pedidos_recentes.xlsx"'
    try:
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Pedidos Recentes"
        columns = ['ID do Pedido', 'Cliente', 'Data', 'Valor Total']
        row_num = 1
        for col_num, column_title in enumerate(columns, 1):
            worksheet.cell(row=row_num, column=col_num, value=column_title)
        pedidos_recentes = Pedido.objects.all().order_by('-data_criacao')[:10]
        for pedido in pedidos_recentes:
            row_num += 1
            data_sem_tz = timezone.localtime(pedido.data_criacao).replace(tzinfo=None)
            worksheet.cell(row=row_num, column=1, value=pedido.id)
            worksheet.cell(row=row_num, column=2, value=pedido.cliente.client_name)
            worksheet.cell(row=row_num, column=3, value=data_sem_tz)
            worksheet.cell(row=row_num, column=4, value=pedido.get_total_geral())
        workbook.save(response)
        return response
    except Exception as e:
        return redirect('dashboard_admin')

@login_required
def exportar_detalhes_pedido_excel(request, pedido_id):
    try:
        # Garante que o usuário logado só pode exportar o próprio pedido
        cliente_logado = request.user.wfclient
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente_logado)
        uf_cliente = cliente_logado.client_state.uf_name
    except WfClient.DoesNotExist:
        # Se o usuário não tiver um cliente associado, redireciona
        return redirect('pedidos')
    except Pedido.DoesNotExist:
        # Se o pedido não existir ou não pertencer ao cliente, retorna um erro
        return redirect('pedidos')
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.xlsx"'
    
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"
    
    # Define as colunas dinamicamente com base no estado do cliente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'product_value_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'product_value_es'
    else:
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = None
        
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)
        
    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0
    
    for item in itens:
        row_num += 1
        
        # Acessa o valor do produto dinamicamente
        if valor_key:
            valor_unitario = getattr(item.produto, valor_key, 0)
        else:
            valor_unitario = 0

        # Calcula o subtotal diretamente
        subtotal = valor_unitario * item.quantidade
        total_geral += subtotal
        
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=valor_unitario)
        worksheet.cell(row=row_num, column=5, value=subtotal)
        
    row_num += 1
    worksheet.cell(row=row_num, column=4, value="Total Geral:")
    worksheet.cell(row=row_num, column=5, value=total_geral)
    
    workbook.save(response)
    return response

@staff_member_required
def exportar_detalhes_pedido_admin_excel(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
    except Pedido.DoesNotExist:
        return redirect('dashboard_admin')
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.xlsx"'
    
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"
    
    # Colunas agora mostram apenas o preço de SP
    columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal (Base SP)']
    
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)
    
    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0
    
    for item in itens:
        row_num += 1
        
        # Usa o valor de SP para o cálculo do subtotal
        valor_unitario = item.produto.product_value_sp
        subtotal = valor_unitario * item.quantidade
        total_geral += subtotal
        
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=valor_unitario)
        worksheet.cell(row=row_num, column=5, value=subtotal)
        
    row_num += 1
    worksheet.cell(row=row_num, column=4, value="Total Geral:")
    worksheet.cell(row=row_num, column=5, value=total_geral)
    
    workbook.save(response)
    return response

@staff_member_required
def detalhes_pedido_admin(request, pedido_id):
    try:
        # Puxa o pedido pelo ID (sem filtrar por cliente)
        pedido = get_object_or_404(Pedido, id=pedido_id) 
        itens = ItemPedido.objects.filter(pedido=pedido)
        
        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens': itens,
        }
        return render(request, 'detalhes_pedido.html', contexto)

    except Pedido.DoesNotExist:
        # Redireciona para o dashboard se o pedido não existir
        return redirect('dashboard_admin')
    
@staff_member_required
def detalhes_pedido_admin(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        itens = ItemPedido.objects.filter(pedido=pedido)
        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens': itens,
        }
        return render(request, 'detalhes_pedido.html', contexto)
    except Pedido.DoesNotExist:
        return redirect('dashboard_admin')


@staff_member_required
def exportar_detalhes_pedido_admin_excel(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        cliente = pedido.cliente # Pega o cliente do pedido
        uf_cliente = cliente.client_state.uf_name
    except Pedido.DoesNotExist:
        return redirect('dashboard_admin')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"

    # Define as colunas dinamicamente com base no estado do cliente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'product_value_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'product_value_es'
    else:
        # Padrão caso o estado não seja SP ou ES
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = None # ou um valor padrão

    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0

    for item in itens:
        row_num += 1

        # Acessa o valor do produto dinamicamente
        if valor_key:
            valor_unitario = getattr(item.produto, valor_key, 0)
        else:
            valor_unitario = 0

        subtotal = valor_unitario * item.quantidade
        total_geral += subtotal

        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=valor_unitario)
        worksheet.cell(row=row_num, column=5, value=subtotal)

    row_num += 1
    worksheet.cell(row=row_num, column=4, value="Total Geral:")
    worksheet.cell(row=row_num, column=5, value=total_geral)

    workbook.save(response)
    return response

# Exportar para o cliente
@login_required
def exportar_detalhes_pedido_cliente_excel(request, pedido_id):
    try:
        # Garante que o usuário logado só possa exportar o próprio pedido
        cliente_logado = request.user.wfclient
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente_logado)
        uf_cliente = cliente_logado.client_state.uf_name
    except WfClient.DoesNotExist:
        # Se o usuário não tiver um cliente associado, redireciona para a página de pedidos
        return redirect('pedidos')
    except Pedido.DoesNotExist:
        # Se o pedido não existir ou não pertencer ao cliente, retorna um erro 404
        return redirect('pedidos')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"

    # Define as colunas dinamicamente com base no estado do cliente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'product_value_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'product_value_es'
    else:
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = None

    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0

    for item in itens:
        row_num += 1

        if valor_key:
            valor_unitario = getattr(item.produto, valor_key, 0)
        else:
            valor_unitario = 0

        # CÁLCULO DIRETO DO SUBTOTAL
        subtotal = valor_unitario * item.quantidade
        total_geral += subtotal

        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=valor_unitario)
        worksheet.cell(row=row_num, column=5, value=subtotal)

    row_num += 1
    worksheet.cell(row=row_num, column=4, value="Total Geral:")
    worksheet.cell(row=row_num, column=5, value=total_geral)

    workbook.save(response)
    return response






@staff_member_required
def todos_os_pedidos(request):
    pedidos_qs = Pedido.objects.all().order_by('-data_criacao')

    # Lógica de Paginação
    paginator = Paginator(pedidos_qs, 20) # 20 pedidos por página
    page = request.GET.get('page')

    try:
        pedidos = paginator.page(page)
    except PageNotAnInteger:
        pedidos = paginator.page(1)
    except EmptyPage:
        pedidos = paginator.page(paginator.num_pages)

    contexto = {
        'titulo': 'Todos os Pedidos',
        'pedidos': pedidos,
    }
    return render(request, 'todos_os_pedidos.html', contexto)



from django.db import models
from django.contrib.auth.models import User

# ... (seus outros modelos)

# Modelo de Pedido
class PedidoStatus(models.Model):
    # Opções de status do pedido
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('SOLICITADO', 'Solicitado'),
        ('EM_ENVIO', 'Em Envio'),
        ('ENTREGUE', 'Entregue'),
    ]

    cliente = models.ForeignKey(WfClient, on_delete=models.CASCADE, related_name='pedidos')
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE') # NOVO: Campo de status

    def __str__(self):
        return f"Pedido #{self.id} de {self.cliente.client_name} - Status: {self.status}"

    def get_total_geral(self):
        total = sum(item.get_total() for item in self.itens.all())
        return total
    
@staff_member_required
def atualizar_status_pedido(request, pedido_id):
    # NOVO: Adicione estas duas linhas para depuração

    #print(request.POST) 
   # print(f"Pedido ID: {pedido_id}")
    
    if request.method == 'POST':
        pedido = get_object_or_404(Pedido, id=pedido_id)
        novo_status = request.POST.get('status')
        if novo_status in ['PENDENTE', 'SOLICITADO', 'EM_ENVIO', 'ENTREGUE']:
            pedido.status = novo_status
            pedido.save()
    return redirect('todos_os_pedidos')

@login_required
def editar_perfil(request):
    try:
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = EnderecoForm(request.POST)
        if form.is_valid():
            novo_endereco = form.save(commit=False)
            novo_endereco.cliente = cliente
            novo_endereco.save()
            return redirect('editar_perfil')
    else:
        form = EnderecoForm()

    enderecos = Endereco.objects.filter(cliente=cliente)
    
    contexto = {
        'form': form,
        'enderecos': enderecos,
        'titulo': 'Gerenciar Endereços',
    }
    return render(request, 'editar_perfil.html', contexto)


@login_required
def gerenciar_enderecos(request):
    try:
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        return redirect('home')
        
    enderecos = Endereco.objects.filter(cliente=cliente)
    
    if request.method == 'POST':
        form = EnderecoForm(request.POST)
        if form.is_valid():
            novo_endereco = form.save(commit=False)
            novo_endereco.cliente = cliente
            novo_endereco.save()
            return redirect('gerenciar_enderecos')
    else:
        form = EnderecoForm()

    contexto = {
        'titulo': 'Gerenciar Endereços',
        'enderecos': enderecos,
        'form': form
    }
    return render(request, 'gerenciar_enderecos.html', contexto)


@login_required
def editar_endereco(request, endereco_id):
    try:
        endereco = get_object_or_404(Endereco, id=endereco_id, cliente=request.user.wfclient)
    except WfClient.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = EnderecoForm(request.POST, instance=endereco)
        if form.is_valid():
            form.save()
            return redirect('editar_perfil')
    else:
        form = EnderecoForm(instance=endereco)

    contexto = {
        'form': form,
        'titulo': 'Editar Endereço',
    }
    return render(request, 'editar_endereco.html', contexto)


# A página para exibir o formulário de upload
def pagina_upload(request):
    return render(request, 'upload_planilha.html')

def processar_upload(request):
    if request.method == 'POST':
        planilha_es_file = request.FILES.get('planilha_es')
        planilha_sp_file = request.FILES.get('planilha_sp')

        if not planilha_es_file or not planilha_sp_file:
            messages.error(request, 'Por favor, selecione ambas as planilhas.')
            return redirect('pagina_upload')

        try:
            # Lógica para ler, tratar e juntar as planilhas
            # ALTERAÇÃO: Incluir a coluna 'MARCA' na leitura da planilha de ES
            df_es = pd.read_excel(planilha_es_file, usecols=['CÓDIGO', 'DESCRIÇÃO', 'GRUPO', 'MARCA', 'TABELA'])
            df_es = df_es.rename(columns={'CÓDIGO': 'product_code', 'DESCRIÇÃO': 'product_description', 'GRUPO': 'product_group', 'MARCA': 'product_brand', 'TABELA': 'product_value_es'})

            df_sp = pd.read_excel(planilha_sp_file, usecols=['CÓDIGO', 'TABELA'])
            df_sp = df_sp.rename(columns={'CÓDIGO': 'product_code', 'TABELA': 'product_value_sp'})
            
            df_es.loc[df_es['product_value_es'] == 'SEM ESTOQUE', 'product_value_es'] = 0
            df_sp.loc[df_sp['product_value_sp'] == 'SEM ESTOQUE', 'product_value_sp'] = 0

            df_final = pd.merge(df_es, df_sp, on='product_code', how='left')
            df_final = df_final.replace({np.nan: None})

            with transaction.atomic():
                produtos_processados = 0
                for _, row in df_final.iterrows():
                    # NOVO CÓDIGO: Usar update_or_create para garantir unicidade
                    Product.objects.update_or_create(
                        product_code=row['product_code'],
                        defaults={
                            'product_description': row['product_description'],
                            'product_group': row['product_group'],
                            'product_brand': row['product_brand'], # ALTERAÇÃO: Adicionar a marca aqui
                            'product_value_sp': row['product_value_sp'],
                            'product_value_es': row['product_value_es'],
                            'status': 'PENDENTE',
                            'date_product': datetime.date.today(),
                        }
                    )
                    produtos_processados += 1
                
            messages.success(request, f'{produtos_processados} produtos processados com sucesso.')
            return redirect('pagina_upload')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao processar as planilhas: {e}')
            return redirect('pagina_upload')

    return render(request, 'upload_planilha.html')