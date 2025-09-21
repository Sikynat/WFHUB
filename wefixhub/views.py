from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum
from .models import Product, Pedido, ItemPedido, WfClient
from django.http import HttpResponse
from django.utils import timezone
import openpyxl

from django.db.models.functions import ExtractMonth
# View para a página inicial com filtros e paginação
@login_required
def home(request):
    product_list = Product.objects.all()
    codigo = request.GET.get('codigo')
    descricao = request.GET.get('descricao')
    grupo = request.GET.get('grupo')
    marca = request.GET.get('marca')
    valor_min = request.GET.get('valor_min')
    valor_max = request.GET.get('valor_max')

    if codigo:
        product_list = product_list.filter(product_code__icontains=codigo)
    if descricao:
        product_list = product_list.filter(product_description__icontains=descricao)
    if grupo:
        product_list = product_list.filter(product_group__icontains=grupo)
    if marca:
        product_list = product_list.filter(product_brand__icontains=marca)
    if valor_min:
        try:
            product_list = product_list.filter(product_value__gte=valor_min)
        except (ValueError, TypeError):
            pass
    if valor_max:
        try:
            product_list = product_list.filter(product_value__lte=valor_max)
        except (ValueError, TypeError):
            pass

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
    return render(request, 'home.html', contexto)

@login_required
def gerar_pedido(request):
    if request.method == 'POST':
        request.session['carrinho'] = {}
        for key, value in request.POST.items():
            if key.startswith('quantidade_') and value.isdigit() and int(value) > 0:
                product_id = key.split('_')[1]
                quantidade = int(value)
                request.session['carrinho'][product_id] = quantidade
        request.session.modified = True
    return redirect('carrinho')

@login_required
def carrinho(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    carrinho_detalhes = []
    total_geral = 0
    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            product = Product.objects.get(product_id=product_id)
            valor_total_item = product.product_value * quantidade
            total_geral += valor_total_item
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_total': valor_total_item
            })
        except Product.DoesNotExist:
            continue
    contexto = {
        'titulo': 'Carrinho de Compras',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral
    }
    return render(request, 'carrinho.html', contexto)

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

@login_required
def checkout(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    carrinho_detalhes = []
    total_geral = 0
    if not carrinho_da_sessao:
        return redirect('carrinho')
    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            product = Product.objects.get(product_id=product_id)
            valor_total_item = product.product_value * quantidade
            total_geral += valor_total_item
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_total': valor_total_item
            })
        except Product.DoesNotExist:
            continue
    contexto = {
        'titulo': 'Confirmação de Compra',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral
    }
    return render(request, 'checkout.html', contexto)

@login_required
def salvar_pedido(request):
    if request.method == 'POST':
        carrinho_da_sessao = request.session.get('carrinho', {})
        if not carrinho_da_sessao:
            return redirect('carrinho')
        try:
            cliente_logado = request.user.wfclient
        except WfClient.DoesNotExist:
            return redirect('home')
        pedido_criado = Pedido.objects.create(cliente=cliente_logado)
        for product_id, quantidade in carrinho_da_sessao.items():
            try:
                product = Product.objects.get(product_id=product_id)
                ItemPedido.objects.create(
                    pedido=pedido_criado,
                    produto=product,
                    quantidade=quantidade
                )
            except Product.DoesNotExist:
                continue
        del request.session['carrinho']
        request.session.modified = True
        return redirect('pedido_concluido')
    return redirect('checkout')

@login_required
def pedido_concluido(request):
    return render(request, 'pedido_concluido.html')

@login_required
def historico_pedidos(request):
    try:
        cliente_logado = request.user.wfclient
        pedidos = Pedido.objects.filter(cliente=cliente_logado).order_by('-data_criacao')
    except WfClient.DoesNotExist:
        pedidos = []
    contexto = {
        'titulo': 'Histórico de Pedidos',
        'pedidos': pedidos
    }
    return render(request, 'historico_pedidos.html', contexto)

@login_required
def detalhes_pedido(request, pedido_id):
    try:
        cliente_logado = request.user.wfclient
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente_logado)
        itens = ItemPedido.objects.filter(pedido=pedido)
        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens': itens,
        }
        return render(request, 'detalhes_pedido.html', contexto)
    except WfClient.DoesNotExist:
        return redirect('pedidos')
    except Pedido.DoesNotExist:
        return redirect('pedidos')

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
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user.wfclient)
    except WfClient.DoesNotExist:
        return redirect('pedidos')
    except Pedido.DoesNotExist:
        return redirect('pedidos')
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.xlsx"'
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"Pedido #{pedido.id}"
    columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)
    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0
    for item in itens:
        row_num += 1
        subtotal = item.get_total()
        total_geral += subtotal
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=item.produto.product_value)
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
    columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)
    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0
    for item in itens:
        row_num += 1
        subtotal = item.get_total()
        total_geral += subtotal
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=item.produto.product_value)
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

    # Dados do Pedido
    worksheet.cell(row=1, column=1, value="Pedido ID:")
    worksheet.cell(row=1, column=2, value=pedido.id)
    worksheet.cell(row=2, column=1, value="Cliente:")
    worksheet.cell(row=2, column=2, value=pedido.cliente.client_name)
    worksheet.cell(row=3, column=1, value="Data da Compra:")
    data_sem_tz = timezone.localtime(pedido.data_criacao).replace(tzinfo=None)
    worksheet.cell(row=3, column=2, value=data_sem_tz)

    # Tabela de Itens
    worksheet.cell(row=5, column=1, value="Itens do Pedido:")
    columns = ['Código', 'Descrição', 'Quantidade', 'Valor Unitário', 'Subtotal']
    row_num = 6
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0
    for item in itens:
        row_num += 1
        subtotal = item.get_total()
        total_geral += subtotal
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        worksheet.cell(row=row_num, column=3, value=item.quantidade)
        worksheet.cell(row=row_num, column=4, value=item.produto.product_value)
        worksheet.cell(row=row_num, column=5, value=subtotal)
    
    row_num += 1
    worksheet.cell(row=row_num, column=4, value="Total Geral:")
    worksheet.cell(row=row_num, column=5, value=total_geral)

    workbook.save(response)
    return response


