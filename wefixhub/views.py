from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum, F
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
from decimal import Decimal
import json
from .forms import GerarPedidoForm
from .forms import UploadPedidoForm, SelectClientForm
import unicodedata
from django.urls import reverse
import os
from django.conf import settings
from urllib.parse import quote
from django.shortcuts import get_object_or_404, redirect
from io import BytesIO
import requests
import xlsxwriter
from datetime import date
#from unidecode import unidecode 



# View para a página inicial com filtros e paginação
@login_required
def home(request):
    # Lógica de filtragem e busca
    codigo = request.GET.get('codigo', None)
    descricao = request.GET.get('descricao', None)
    grupo = request.GET.get('grupo', None)
    marca = request.GET.get('marca', None)

    data_hoje = datetime.date.today()

    # Apenas produtos com data de hoje
    products = Product.objects.filter(date_product=datetime.date.today()).order_by('product_code')

    if codigo:
        products = products.filter(product_code__icontains=codigo)
    if descricao:
        products = products.filter(product_description__icontains=descricao)
    if grupo:
        products = products.filter(product_group__icontains=grupo)
    if marca:
        products = products.filter(product_brand__icontains=marca)
    
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
                    products = products.exclude(product_value_sp=0)
                elif cliente_logado.client_state.uf_name == 'ES':
                    preco_exibido = 'es'
                    products = products.exclude(product_value_es=0)
            except WfClient.DoesNotExist:
                products = Product.objects.none()
    
    if not request.user.is_authenticated:
        products = Product.objects.none()
    
    # Prepara os produtos para o template, formatando os valores
    for product in products:
        product.valor_sp_formatado = f"{product.product_value_sp.quantize(Decimal('0.01'))}".replace('.', ',') if product.product_value_sp else "0,00"
        product.valor_es_formatado = f"{product.product_value_es.quantize(Decimal('0.01'))}".replace('.', ',') if product.product_value_es else "0,00"
    
    paginator = Paginator(products, 30) 
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
        'data_hoje': data_hoje,
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
        # Recebe os dados do carrinho enviados via campo hidden
        # Garante que o valor padrão seja uma string JSON válida
        cart_data_json = request.POST.get('cart_data', '{}')
        
        # Se a string estiver vazia, redireciona com uma mensagem de erro
        if not cart_data_json:
            messages.error(request, 'Erro ao processar os dados do carrinho.')
            return redirect('home')

        try:
            carrinho_da_sessao = json.loads(cart_data_json)
            
            # Filtra produtos com quantidade zero
            carrinho_filtrado = {
                product_id: quantidade
                for product_id, quantidade in carrinho_da_sessao.items()
                if quantidade > 0
            }
            
            if not carrinho_filtrado:
                messages.error(request, 'Seu carrinho está vazio.')
                return redirect('home')

            # Salva o carrinho na sessão
            request.session['carrinho'] = carrinho_filtrado

            # Redireciona para a página de checkout
            return redirect('checkout')

        except json.JSONDecodeError:
            messages.error(request, 'Erro ao processar os dados do carrinho.')
            return redirect('home')
    
    # Se a requisição não for POST, redireciona de volta
    return redirect('home')


# Fim gerar pedido

# Inicio do carrinho

@login_required
def carrinho(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    carrinho_detalhes = []
    total_geral = Decimal('0.00')
    
    preco_exibido = None

    try:
        if request.user.is_staff:
            preco_exibido = 'todos'
        else:
            cliente_logado = request.user.wfclient
            if cliente_logado.client_state.uf_name == 'SP':
                preco_exibido = 'sp'
            elif cliente_logado.client_state.uf_name == 'ES':
                preco_exibido = 'es'
    except WfClient.DoesNotExist:
        pass

    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            product = get_object_or_404(Product, product_id=product_id)
            
            if preco_exibido == 'sp':
                valor_unitario = product.product_value_sp
            elif preco_exibido == 'es':
                valor_unitario = product.product_value_es
            elif preco_exibido == 'todos':
                valor_unitario = product.product_value_sp
            else:
                valor_unitario = Decimal('0.00')

            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item

            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario, # Valor numérico para o JavaScript
                'valor_total': valor_total_item,
                'valor_unitario_formatado': f"R$ {valor_unitario.quantize(Decimal('0.01'))}".replace('.', ','),
                'valor_total_formatado': f"R$ {valor_total_item.quantize(Decimal('0.01'))}".replace('.', ','),
            })
        except Product.DoesNotExist:
            continue

    contexto = {
        'titulo': 'Carrinho de Compras',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral, # Valor numérico para o JavaScript
        'total_geral_formatado': f"R$ {total_geral.quantize(Decimal('0.01'))}".replace('.', ','),
        'preco_exibido': preco_exibido,
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
    total_geral = Decimal('0.00')
    preco_exibido = None
    cliente_logado = None

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
        frete_option = request.POST.get('frete_option')
        nota_fiscal = request.POST.get('nota_fiscal')
        
        # 💡 Validação condicional do endereço
        endereco_selecionado = None
        if frete_option != 'ONIBUS':
            if not endereco_id:
                messages.error(request, 'Por favor, selecione um endereço válido.')
                return redirect('checkout')
            
            try:
                endereco_selecionado = Endereco.objects.get(id=endereco_id, cliente=cliente_logado)
            except Endereco.DoesNotExist:
                messages.error(request, 'Endereço inválido.')
                return redirect('checkout')
        
        try:
            data_envio = datetime.datetime.strptime(data_envio, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Data de envio inválida.')
            return redirect('checkout')
        
        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=cliente_logado,
                endereco=endereco_selecionado, # O campo pode ser nulo se o frete for Ônibus
                data_envio_solicitada=data_envio,
                frete_option=frete_option,
                nota_fiscal=nota_fiscal,
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

        messages.success(request, 'Seu pedido foi realizado com sucesso!')
        return redirect('home')
    
    # Este é o bloco de código que roda apenas no método GET
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

@staff_member_required
def detalhes_pedido_admin(request, pedido_id):
    try:
        # Puxa o pedido pelo ID (sem filtrar por cliente)
        pedido = get_object_or_404(Pedido, id=pedido_id) 
        
        # Obtém o estado do cliente do pedido para saber qual preço exibir
        estado_cliente = pedido.cliente.client_state.uf_name

        # Define qual preço será exibido
        preco_exibido = None
        if estado_cliente == 'SP':
            preco_exibido = 'sp'
        elif estado_cliente == 'ES':
            preco_exibido = 'es'
        else:
            preco_exibido = 'sp' # Define um padrão para outros estados
        
        itens_detalhes = []
        itens = ItemPedido.objects.filter(pedido=pedido)

        for item in itens:
            itens_detalhes.append({
                'item': item,
                'valor_unitario': item.valor_unitario, # Usa o valor que já está no banco de dados
                'valor_total': item.valor_unitario * item.quantidade,
            })

        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens_detalhes': itens_detalhes,
            'total_geral': pedido.valor_total, # ✅ Usa o valor que já foi salvo no pedido
            'preco_exibido': preco_exibido
        }
        
        return render(request, 'detalhes_pedido.html', contexto)

    except Pedido.DoesNotExist:
        messages.error(request, "Erro: Pedido não encontrado.")
        return redirect('todos_os_pedidos')
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
    
    # 💡 CORREÇÃO: Calcule o subtotal de cada item e depois some.
    total_vendas_agregadas = ItemPedido.objects.annotate(
        subtotal=F('quantidade') * F('produto__product_value_sp')
    ).aggregate(total_vendas=Sum('subtotal'))
    
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
        cliente = pedido.cliente 
        uf_cliente = cliente.client_state.uf_name
    except Pedido.DoesNotExist:
        return redirect('dashboard_admin')

    # Formata a data para o padrão 'dd-mm-aaaa'
    data_formatada = pedido.data_criacao.strftime('%d-%m-%Y')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.cliente.client_code}_{data_formatada}.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"

    # Define as colunas dinamicamente com base no estado do cliente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'valor_unitario_sp' # <-- Alterado para o campo do ItemPedido
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'valor_unitario_es' # <-- Alterado para o campo do ItemPedido
    else:
        # Padrão caso o estado não seja SP ou ES
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = 'valor_unitario_sp' # <-- Padrão para SP

    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0

    for item in itens:
        row_num += 1

        # ✅ Acessa o valor do item de pedido, não do produto
        valor_unitario = getattr(item, valor_key)
        
        # Garante que o valor não seja None
        if valor_unitario is None:
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

    data_formatada = pedido.data_criacao.strftime('%d-%m-%Y')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.cliente.client_code}_{data_formatada}.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"

    # Define as colunas dinamicamente com base no estado do cliente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'valor_unitario_sp'  # ✅ Alterado para o campo do ItemPedido
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'valor_unitario_es'  # ✅ Alterado para o campo do ItemPedido
    else:
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = 'valor_unitario_sp'  # Padrão para SP

    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0

    for item in itens:
        row_num += 1

        # ✅ Acessa o valor do item de pedido, não do produto
        valor_unitario = getattr(item, valor_key)
        if valor_unitario is None:
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

@login_required
def gerar_pedido(request):
    if request.method == 'POST':
        # Recebe os dados do carrinho enviados via campo hidden
        cart_data_json = request.POST.get('cart_data', '{}')
        
        try:
            carrinho_da_sessao = json.loads(cart_data_json)
            
            # Filtra produtos com quantidade zero
            carrinho_filtrado = {
                product_id: quantidade
                for product_id, quantidade in carrinho_da_sessao.items()
                if quantidade > 0
            }
            
            if not carrinho_filtrado:
                messages.error(request, 'Seu carrinho está vazio.')
                return redirect('home')

            # Salva o carrinho na sessão
            request.session['carrinho'] = carrinho_filtrado

            # Redireciona para a página de checkout
            return redirect('checkout')

        except json.JSONDecodeError:
            messages.error(request, 'Erro ao processar os dados do carrinho.')
            return redirect('home')
    
    # Se a requisição não for POST, redireciona de volta
    return redirect('home')

@staff_member_required
def detalhes_pedido_admin(request, pedido_id):
    try:
        # Puxa o pedido pelo ID (sem filtrar por cliente)
        pedido = get_object_or_404(Pedido, id=pedido_id) 
        
        # Obtém o estado do cliente do pedido
        estado_cliente = pedido.cliente.client_state.uf_name

        # Define qual preço será exibido, com base no estado do cliente
        # A variável 'preco_exibido' agora não depende se é admin ou não
        preco_exibido = 'sp' if estado_cliente == 'SP' else 'es'

        itens_detalhes = []
        total_geral = 0
        itens = ItemPedido.objects.filter(pedido=pedido)

        for item in itens:
            # Seleciona o valor unitário correto com base no estado do cliente
            valor_unitario = item.valor_unitario_sp if estado_cliente == 'SP' else item.valor_unitario_es
            
            # Garante que o valor não seja None
            if valor_unitario is None:
                valor_unitario = 0

            valor_total_item = valor_unitario * item.quantidade
            total_geral += valor_total_item

            itens_detalhes.append({
                'item': item,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
            })

        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens_detalhes': itens_detalhes,
            'total_geral': total_geral,
            'preco_exibido': preco_exibido
        }
        
        return render(request, 'detalhes_pedido.html', contexto)

    except Pedido.DoesNotExist:
        # Redireciona para o dashboard se o pedido não existir
        return redirect('dashboard_admin')
    
@staff_member_required
def pedidos_para_hoje(request):
    """
    View que filtra e exibe os pedidos agendados para a data atual.
    """
    # Pega a data de hoje, sem a hora
    hoje = timezone.localdate()

    # Filtra os pedidos onde a data_envio_solicitada é igual à data de hoje
    pedidos_hoje = Pedido.objects.filter(data_envio_solicitada=hoje)

    context = {
        'pedidos_hoje': pedidos_hoje,
        'data_hoje': hoje,
    }
    return render(request, 'pedidos/pedidos_hoje.html', context)


@staff_member_required
def gerar_pedido_manual(request):
    cliente_selecionado = None
    form_cliente = SelectClientForm(request.GET or None)
    product_list = []
    query_params = request.GET.copy()
    preco_exibido = 'todos'
    
    # Dicionário para armazenar dados iniciais para o template
    initial_data = {}

    if 'page' in query_params:
        query_params.pop('page')

    if form_cliente.is_valid():
        cliente_selecionado = form_cliente.cleaned_data['cliente']
        # Se um cliente for selecionado, pega as preferências dele
        if cliente_selecionado:
            initial_data['frete_preferencia'] = cliente_selecionado.frete_preferencia
            initial_data['nota_fiscal_preferencia'] = cliente_selecionado.nota_fiscal_preferencia
        # NOVO CÓDIGO: Busca o endereço padrão e adiciona ao initial_data
            endereco_padrao = Endereco.objects.filter(cliente=cliente_selecionado, is_default=True).first()
            if endereco_padrao:
                initial_data['endereco_padrao_id'] = endereco_padrao.id


    context = {
        'form_cliente': form_cliente,
        'cliente_selecionado': cliente_selecionado,
        'initial_data': initial_data, # Adiciona o dicionário com os dados iniciais
        'query_params': query_params,
        'preco_exibido': preco_exibido,
    }
    
    if cliente_selecionado:
        enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_selecionado)
        
        hoje = timezone.localdate()
        products = Product.objects.filter(date_product=hoje).order_by('product_code')

        codigo = request.GET.get('codigo')
        descricao = request.GET.get('descricao')
        grupo = request.GET.get('grupo')
        marca = request.GET.get('marca')

        if codigo:
            products = products.filter(product_code__icontains=codigo)
        if descricao:
            products = products.filter(product_description__icontains=descricao)
        if grupo:
            products = products.filter(product_group__icontains=grupo)
        if marca:
            products = products.filter(product_brand__icontains=marca)
        
        estado_cliente = cliente_selecionado.client_state.uf_name
        preco_exibido = estado_cliente.lower()

        for product in products:
            if estado_cliente == 'SP':
                if product.product_value_sp is not None:
                    product.valor_sp_formatado = f"R$ {product.product_value_sp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    product.valor_sp_formatado = "N/A"
            elif estado_cliente == 'ES':
                if product.product_value_es is not None:
                    product.valor_es_formatado = f"R$ {product.product_value_es:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    product.valor_es_formatado = "N/A"
            else:
                product.valor_formatado = "N/A"
            
        paginator = Paginator(products, 30)
        page_number = request.GET.get('page')
        product_list = paginator.get_page(page_number)

        context.update({
            'enderecos': enderecos_do_cliente,
            'preco_exibido': preco_exibido,
            'product_list': product_list,
        })
    
    return render(request, 'gerar_pedido_manual.html', context)

@staff_member_required
def processar_pedido_manual(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        cart_data_json = request.POST.get('cart_data')
        endereco_id = request.POST.get('endereco_selecionado')
        data_envio = request.POST.get('data_envio')
        frete_option = request.POST.get('frete_option')
        nota_fiscal = request.POST.get('nota_fiscal')
        usuario_logado = request.user

        # Lógica de validação do endereço ajustada
        fretes_sem_endereco = ['ONIBUS', 'RETIRADA']
        endereco_selecionado = None
        
        if frete_option not in fretes_sem_endereco:
            if not endereco_id:
                messages.error(request, 'Por favor, selecione um endereço válido.')
                return redirect('gerar_pedido_manual')
            try:
                endereco_selecionado = get_object_or_404(Endereco, id=endereco_id)
            except Endereco.DoesNotExist:
                messages.error(request, 'Endereço inválido.')
                return redirect('gerar_pedido_manual')

        try:
            cliente_selecionado = get_object_or_404(WfClient, client_id=cliente_id)
            data_envio = datetime.datetime.strptime(data_envio, '%Y-%m-%d').date()
            cart_data = json.loads(cart_data_json)

            if not cart_data:
                messages.error(request, 'Não há itens para gerar o pedido.')
                return redirect('gerar_pedido_manual')

            with transaction.atomic():
                pedido_criado = Pedido.objects.create(
                    cliente=cliente_selecionado,
                    endereco=endereco_selecionado,
                    data_envio_solicitada=data_envio,
                    frete_option=frete_option,
                    nota_fiscal=nota_fiscal,
                    status='PENDENTE',
                    criado_por=usuario_logado,
                    valor_total=Decimal('0.00')
                )
                
                for product_id, quantidade in cart_data.items():
                    try:
                        produto = get_object_or_404(Product, product_id=product_id)
                        
                        # Lógica para salvar o valor no campo correto
                        if cliente_selecionado.client_state.uf_name == 'SP':
                            ItemPedido.objects.create(
                                pedido=pedido_criado,
                                produto=produto,
                                quantidade=quantidade,
                                valor_unitario_sp=produto.product_value_sp,
                                valor_unitario_es=None
                            )
                        elif cliente_selecionado.client_state.uf_name == 'ES':
                            ItemPedido.objects.create(
                                pedido=pedido_criado,
                                produto=produto,
                                quantidade=quantidade,
                                valor_unitario_sp=None,
                                valor_unitario_es=produto.product_value_es
                            )
                        else:
                            messages.warning(request, f'Produto {produto.product_code} não pôde ser adicionado ao pedido. Estado do cliente inválido.')
                            continue
                    except Product.DoesNotExist:
                        messages.warning(request, f'Produto com ID {product_id} não encontrado e foi ignorado.')
                        continue

                # Cálculo e atualização do Valor Total
                total_pedido = ItemPedido.objects.filter(pedido=pedido_criado).aggregate(
                    total_sp=Sum(F('quantidade') * F('valor_unitario_sp')),
                    total_es=Sum(F('quantidade') * F('valor_unitario_es'))
                )
                
                valor_final_do_pedido = total_pedido['total_sp'] if total_pedido['total_sp'] is not None else total_pedido['total_es']
                
                pedido_criado.valor_total = valor_final_do_pedido if valor_final_do_pedido is not None else Decimal('0.00')
                pedido_criado.save()

            messages.success(request, f'Pedido #{pedido_criado.id} criado com sucesso para o cliente {cliente_selecionado.client_name}!')
            return redirect(reverse('gerar_pedido_manual') + '?pedido_gerado=sucesso')

        except (WfClient.DoesNotExist, Endereco.DoesNotExist, ValueError) as e:
            messages.error(request, f'Dados de cliente, endereço, frete ou data inválidos. Erro: {e}')
            return redirect('gerar_pedido_manual')
        except json.JSONDecodeError:
            messages.error(request, 'Erro nos dados do pedido. Tente novamente.')
            return redirect('gerar_pedido_manual')

    return redirect('gerar_pedido_manual')



def normalize_text(text):
    if text:
        text = str(text).strip().lower()
        text = str(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8'))
        return text
    return ''
# --- FIM DA CORREÇÃO ---


# Sua view views.py

# Seu arquivo views.py

# views.py

# ... (todos os seus imports)

@staff_member_required
def upload_pedido(request):
    cliente_selecionado = None
    form_cliente = SelectClientForm(request.GET or None)
    initial_data = {}
    upload_form = None

    if form_cliente.is_valid():
        cliente_selecionado = form_cliente.cleaned_data['cliente']
        if cliente_selecionado:
            initial_data['frete_preferencia'] = cliente_selecionado.frete_preferencia
            initial_data['nota_fiscal_preferencia'] = cliente_selecionado.nota_fiscal_preferencia
            endereco_padrao = Endereco.objects.filter(cliente=cliente_selecionado, is_default=True).first()
            if endereco_padrao:
                initial_data['endereco_padrao_id'] = endereco_padrao.id

    if request.method == 'POST':
        cliente_id_post = request.POST.get('cliente_id')
        cliente_para_validacao = get_object_or_404(WfClient, pk=cliente_id_post)
        
        form = UploadPedidoForm(request.POST, request.FILES)
        enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_para_validacao)
        form.fields['endereco_selecionado'].queryset = enderecos_do_cliente

        if form.is_valid():
            frete_option = form.cleaned_data['frete_option']
            endereco_selecionado = form.cleaned_data.get('endereco_selecionado', None)
            
            # Capturar o usuário logado
            usuario_logado = request.user 

            if frete_option.upper() not in ['ONIBUS', 'RETIRADA'] and not endereco_selecionado:
                messages.error(request, "O campo de endereço é obrigatório para a opção de frete selecionada.")
                upload_form = form
            else:
                try:
                    with transaction.atomic():
                        novo_pedido = Pedido.objects.create(
                            cliente=cliente_para_validacao,
                            endereco=endereco_selecionado,
                            data_criacao=timezone.now(),
                            data_envio_solicitada=form.cleaned_data['data_expedicao'],
                            frete_option=frete_option,
                            nota_fiscal=form.cleaned_data['nota_fiscal'],
                            status='PENDENTE',
                            criado_por=usuario_logado,
                        )

                        planilha_pedido = request.FILES['planilha_pedido']
                        if planilha_pedido.name.endswith('.csv'):
                            df = pd.read_csv(planilha_pedido)
                        else:
                            df = pd.read_excel(planilha_pedido)
                        
                        expected_codigo_cols = ['codigo', 'código', 'cod']
                        expected_quantidade_cols = ['quantidade', 'qtd', 'qtde']

                        df.columns = [normalize_text(col) for col in df.columns]
                        
                        codigo_col_name = None
                        quantidade_col_name = None
                        
                        for col in df.columns:
                            if col in expected_codigo_cols:
                                codigo_col_name = col
                                break
                        
                        for col in df.columns:
                            if col in expected_quantidade_cols:
                                quantidade_col_name = col
                                break

                        if not codigo_col_name or not quantidade_col_name:
                            messages.error(request, "A planilha deve ter colunas 'codigo' (ou similar) e 'quantidade' (ou similar).")
                            raise ValueError("Colunas obrigatórias não encontradas.")
                        
                        regiao = cliente_para_validacao.client_state.uf_name
                        valor_field = 'product_value_sp' if regiao == 'SP' else 'product_value_es'

                        itens_pedido = []
                        erros = []

                        for index, row in df.iterrows():
                            codigo_produto = str(row[codigo_col_name]).strip()
                            quantidade_raw = row[quantidade_col_name]
                            if pd.isnull(quantidade_raw) or not isinstance(quantidade_raw, (int, float)):
                                quantidade = 0
                            else:
                                quantidade = int(quantidade_raw)
                            
                            if quantidade == 0:
                                erros.append(f"Produto '{codigo_produto}' foi desconsiderado, pois a quantidade é zero ou inválida.")
                                continue

                            try:
                                produto = get_object_or_404(Product, product_code=codigo_produto)
                                valor_unitario = getattr(produto, valor_field)
                                
                                if valor_unitario is not None and valor_unitario > 0:
                                    itens_pedido.append(ItemPedido(
                                        pedido=novo_pedido,
                                        produto=produto,
                                        quantidade=quantidade,
                                        valor_unitario_sp=produto.product_value_sp,
                                        valor_unitario_es=produto.product_value_es,
                                    ))
                                else:
                                    erros.append(f"Produto '{codigo_produto}' foi desconsiderado por estar em falta no estoque")
                            except Product.DoesNotExist:
                                erros.append(f"Produto com código '{codigo_produto}' não encontrado.")
                                raise ValueError(f"Erro crítico: Produto '{codigo_produto}' não encontrado.")
                            except Exception as e:
                                erros.append(f"Erro ao processar o item '{codigo_produto}': {e}")
                                raise ValueError(f"Erro crítico: {e}")
                        
                        if erros:
                            for erro in erros:
                                messages.warning(request, erro)
                        
                        ItemPedido.objects.bulk_create(itens_pedido)
                        
                    messages.success(request, f"Pedido #{novo_pedido.id} para {cliente_para_validacao.client_name} criado com sucesso.")
                    return redirect('upload_pedido')
                    
                except ValueError as e:
                    messages.error(request, f"Erro ao processar a planilha: {e}")
                    upload_form = form
                
                except Exception as e:
                    messages.error(request, f"Erro ao processar a planilha: {e}")
                    upload_form = form
        else:
            upload_form = form
    else:
        upload_form = UploadPedidoForm(initial=initial_data)
        if cliente_selecionado:
            enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_selecionado)
            upload_form.fields['endereco_selecionado'].queryset = enderecos_do_cliente

    context = {
        'form_cliente': form_cliente,
        'cliente_selecionado': cliente_selecionado,
        'initial_data': initial_data,
        'upload_form': upload_form,
    }
    
    return render(request, 'upload_pedido.html', context)

@staff_member_required
def upload_orcamento_pdf(request, pedido_id):
    if request.method == 'POST':
        pedido = get_object_or_404(Pedido, id=pedido_id)
        orcamento_file = request.FILES.get('orcamento_pdf_file')

        if orcamento_file:
            # 1. Pega o código do cliente, o ID do pedido e a data atual
            client_code = pedido.cliente.client_code
            id_do_pedido = pedido.id # Acessa o ID do pedido
            hoje = timezone.localdate().strftime('%d-%m-%Y')
            
            # 2. Define o novo nome e o caminho completo para salvar o arquivo
            novo_nome = f'orcamento_{client_code}_{id_do_pedido}_{hoje}.pdf'
            caminho_orcamentos = os.path.join(settings.MEDIA_ROOT, 'orcamentos')
            caminho_completo = os.path.join(caminho_orcamentos, novo_nome)

            # Garante que o diretório de destino exista
            if not os.path.exists(caminho_orcamentos):
                os.makedirs(caminho_orcamentos)

            # 3. Salva o arquivo manualmente
            try:
                with open(caminho_completo, 'wb+') as destination:
                    for chunk in orcamento_file.chunks():
                        destination.write(chunk)
            except IOError as e:
                messages.error(request, f'Erro ao salvar o arquivo: {e}')
                return redirect(reverse('detalhes_pedido_admin', args=[pedido_id]))
            
            # 4. Salva o caminho do arquivo no modelo, relativo à pasta MEDIA_ROOT
            pedido.orcamento_pdf.name = os.path.join('orcamentos', novo_nome)
            pedido.save()

            messages.success(request, f'Orçamento PDF "{novo_nome}" enviado com sucesso!')
        else:
            messages.error(request, 'Nenhum arquivo foi selecionado.')
            
        return redirect(reverse('detalhes_pedido_admin', args=[pedido_id]))

    return redirect('dashboard_admin')


def exportar_detalhes_pedido_publico_excel(request, pedido_id):
    """
    Exporta os detalhes de um pedido para uma planilha Excel.
    A planilha é personalizada para o estado do cliente.
    """
    pedido = get_object_or_404(Pedido, id=pedido_id)
    itens_pedido = ItemPedido.objects.filter(pedido=pedido).select_related('produto')
    
    # Obtém o estado do cliente para definir a lógica de exportação
    uf_cliente = pedido.cliente.client_state.uf_name

    # Define as colunas e a chave de valor dinamicamente
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'valor_unitario_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'valor_unitario_es'
    else:
        # Padrão caso o estado não seja SP ou ES
        columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = 'valor_unitario_sp'

    # Criação do DataFrame com os dados dos itens
    data = []
    total_geral = 0 # ✅ Inicializa o total geral

    for item in itens_pedido:
        # Acessa o valor do item de pedido usando a chave definida
        valor_unitario = getattr(item, valor_key)
        if valor_unitario is None:
            valor_unitario = 0
            
        subtotal = float(item.get_total()) # ✅ Calcula o subtotal

        # Adiciona os dados à lista
        data.append({
            'Código': item.produto.product_code,
            'Descrição': item.produto.product_description,
            'Quantidade': item.quantidade,
            'Valor Unitário': float(valor_unitario),
            'Subtotal': subtotal
        })
        
        total_geral += subtotal # ✅ Soma ao total geral

    df = pd.DataFrame(data)

    # ✅ Renomeia a coluna 'Valor Unitário' para o nome correto
    df = df.rename(columns={'Valor Unitário': columns[3]})
    df = df[columns] # Reordena as colunas

    # ✅ Adiciona a linha de total ao final do DataFrame
    df.loc[len(df)] = ['', '', '', 'Total Geral:', total_geral]

    # Criação da resposta HTTP
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens do Pedido')

    output.seek(0)

    # ✅ Renomeia o arquivo com as novas informações
    data_hoje = date.today().strftime('%d-%m-%Y')
    filename = f"pedido_{pedido.cliente.client_code}_{data_hoje}.xlsx"
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response




def encurtar_url(long_url):
    """
    Encurta uma URL usando a API da TinyURL.
    """
    api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text
    except requests.RequestException:
        pass
    return long_url










@staff_member_required
def enviar_whatsapp(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Construir o link de download público da planilha
    link_download_excel = request.build_absolute_uri(
        reverse('exportar_detalhes_pedido_publico_excel', args=[pedido.id])
    )

    # Encurtar a URL
    link_encurtado = encurtar_url(link_download_excel)

    # Informações básicas do pedido
    mensagem_base = (
        f"*Dados do Pedido*\n\n"
        f"*Codigo Interno:* {pedido.id}\n"
        f"*Código do Cliente:* {pedido.cliente.client_code}\n"
        f"*Razão Social:* {pedido.cliente.client_name}\n"
        f"*Data da Expedição:* {pedido.data_envio_solicitada.strftime('%d/%m/%Y')}\n"
        f"*Opção de Frete:* {pedido.get_frete_option_display()}\n"
    )

    # Adiciona o endereço de entrega apenas se não for ÔNIBUS ou RETIRADA
    fretes_com_endereco = ['SEDEX', 'CORREIOS', 'TRANSPORTADORA']
    endereco_texto = ""
    if pedido.frete_option in fretes_com_endereco and pedido.endereco:
        endereco = pedido.endereco
        endereco_texto = (
            f"*Endereço de Entrega:* "
            f"{endereco.logradouro}, {endereco.bairro}, {endereco.numero} "
            f"{endereco.cidade} - {endereco.estado} (CEP: {endereco.cep})\n"
        )
    else:
        endereco_texto = ""

    # Conclui a mensagem com a opção de nota fiscal e adiciona o link de download encurtado
    mensagem_final = (
        f"{mensagem_base}"
        f"{endereco_texto}"
        f"*Opção de Nota Fiscal:* {pedido.get_nota_fiscal_display()}\n\n"
        f"*Download da Planilha de Itens:*\n"
        f"{link_encurtado}"
    )

    # ✅ Use a função 'quote' para codificar a URL
    link_whatsapp = f"https://wa.me/5516991273974?text={quote(mensagem_final)}"

    return redirect(link_whatsapp)