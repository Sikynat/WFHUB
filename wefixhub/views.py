from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Product, Pedido, ItemPedido, WfClient

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
    paginator = Paginator(product_list, 10)  # Mostra 10 produtos por página
    page = request.GET.get('page')

    try:
        produtos_na_pagina = paginator.page(page)
    except PageNotAnInteger:
        produtos_na_pagina = paginator.page(1)
    except EmptyPage:
        produtos_na_pagina = paginator.page(paginator.num_pages)
    
    carrinho_da_sessao = request.session.get('carrinho', {})
    contexto = {
        'titulo': 'Página Inicial',
        'product_list': produtos_na_pagina,
        'carrinho': carrinho_da_sessao,
    }
    return render(request, 'home.html', contexto)


# View para adicionar itens ao carrinho
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


# View para a página do carrinho
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


# Views para gerenciar o carrinho
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


# View para a página de checkout
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


# View para salvar o pedido no banco de dados
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


# View de sucesso após o pedido
@login_required
def pedido_concluido(request):
    return render(request, 'pedido_concluido.html')


# View para o histórico de pedidos
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


# View para os detalhes de um pedido específico
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