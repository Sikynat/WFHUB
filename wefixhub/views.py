# wefixhub/views.py

from django.shortcuts import render, redirect, get_object_or_404
from .models import Product
from django.db.models import Q
from django.contrib.auth.decorators import login_required


@login_required
def home(request):
    # ... (o código da sua view home permanece o mesmo)
    product_list = Product.objects.all()

    # Pega os parâmetros do filtro da URL (GET request)
    codigo = request.GET.get('codigo')
    descricao = request.GET.get('descricao')
    grupo = request.GET.get('grupo')
    marca = request.GET.get('marca')
    valor_min = request.GET.get('valor_min')
    valor_max = request.GET.get('valor_max')

    # Aplica os filtros se os campos foram preenchidos
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

    carrinho_da_sessao = request.session.get('carrinho', {})

    contexto = {
        'titulo': 'Página Inicial',
        'product_list': product_list,
        'carrinho': carrinho_da_sessao,
    }
    return render(request, 'home.html', contexto)


def gerar_pedido(request):
    # ... (o código da sua view gerar_pedido permanece o mesmo)
    if request.method == 'POST':
        if 'carrinho' not in request.session:
            request.session['carrinho'] = {}

        for key, value in request.POST.items():
            if key.startswith('quantidade_') and value.isdigit() and int(value) > 0:
                product_id = key.split('_')[1]
                quantidade = int(value)

                request.session['carrinho'][product_id] = quantidade

        request.session.modified = True

    return redirect('home')


# NOVA VIEW PARA O CARRINHO DE COMPRAS
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
            continue  # Ignora produtos que não existem mais

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
                    # Remove o item se a quantidade for 0
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
        # Redireciona para o carrinho se estiver vazio
        return redirect('carrinho')

    for product_id, quantidade in carrinho_da_sessao.items():
        try:
            # Puxa o produto do banco de dados para ter todos os detalhes
            product = Product.objects.get(product_id=product_id)
            valor_total_item = product.product_value * quantidade
            total_geral += valor_total_item
            
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_total': valor_total_item
            })
        except Product.DoesNotExist:
            continue  # Pula se o produto não existir mais

    contexto = {
        'titulo': 'Confirmação de Compra',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral
    }
    return render(request, 'checkout.html', contexto)


from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .models import Product, Pedido, ItemPedido, WfClient


@login_required
def pedido_concluido(request):
    return render(request, 'pedido_concluido.html')

@login_required
def salvar_pedido(request):
    if request.method == 'POST':
        carrinho_da_sessao = request.session.get('carrinho', {})

        if not carrinho_da_sessao:
            return redirect('carrinho')

        try:
            # CORREÇÃO AQUI: Pega o WfClient diretamente através do usuário logado
            cliente_logado = request.user.wfclient
        except WfClient.DoesNotExist:
            return redirect('home')

        pedido_criado = Pedido.objects.create(cliente=cliente_logado)

        # ... (o restante da sua view para criar ItemPedido)
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
def historico_pedidos(request):
    try:
        # Puxa todos os pedidos do cliente logado
        cliente_logado = request.user.wfclient
        pedidos = Pedido.objects.filter(cliente=cliente_logado).order_by('-data_criacao')
    except:
        pedidos = []
    
    contexto = {
        'titulo': 'Histórico de Pedidos',
        'pedidos': pedidos
    }
    return render(request, 'historico_pedidos.html', contexto)

@login_required
def detalhes_pedido(request, pedido_id):
    try:
        # Puxa o pedido pelo ID e verifica se ele pertence ao usuário logado
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user.wfclient)
        itens = ItemPedido.objects.filter(pedido=pedido)
        
        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens': itens,
        }
        return render(request, 'detalhes_pedido.html', contexto)

    except Pedido.DoesNotExist:
        return redirect('pedidos')