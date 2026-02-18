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
from fpdf import FPDF
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
from django.db.models import OuterRef, Subquery, Max
from django import template
from django.conf import settings
from django.utils import formats
import locale
from django.db.models.functions import Cast
from django.db.models import IntegerField
from django.contrib import messages
import locale
from django.db.models.functions import TruncMonth , Coalesce
from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper 
from datetime import datetime, timedelta, date 

from django.db.models import Count, Sum, F, OuterRef, Subquery, DecimalField, ExpressionWrapper, Value 
from django.db.models.functions import TruncMonth, Coalesce, TruncDate
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required


# Garanta que seus modelos estão importados
from .models import Pedido, ItemPedido, WfClient, ItemPedidoIgnorado


try:
    # Tenta definir o locale ideal
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    # Se falhar, usa um locale padrão que suporta UTF-8
    print("Aviso: Locale 'pt_BR.UTF-8' não encontrado. Usando 'C.UTF-8' como fallback.")
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')

# O resto do seu código continua aqui...
#from unidecode import unidecode 



# View para a página inicial com filtros e paginação
@login_required
def home(request):
    # Lógica de filtragem e busca
    codigo = request.GET.get('codigo', None)
    descricao = request.GET.get('descricao', None)
    grupo = request.GET.get('grupo', None)
    marca = request.GET.get('marca', None)
    pedidos_rascunho_count = Pedido.objects.filter(status='RASCUNHO').count()

    # Obter o registro mais recente para cada produto.
    latest_dates = Product.objects.filter(
        product_code=OuterRef('product_code')
    ).order_by('-date_product').values('date_product')[:1]

    # Aplica o filtro de subconsulta e adiciona a ordenação estável por código.
    products = Product.objects.filter(
        date_product=Subquery(latest_dates)
    ).order_by('product_code') # <-- CORREÇÃO: Adiciona ordem para paginação consistente

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
        # A data exibida será a do último produto atualizado
        'data_hoje': products[0].date_product if products else date.today(),
        'pedidos_rascunho_count': pedidos_rascunho_count,
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
import pdb # Importa o módulo do debugger


# Inicio do carrinho


@login_required
def carrinho(request):
    carrinho_da_sessao = request.session.get('carrinho', {})
    carrinho_detalhes = []
    total_geral = Decimal('0.00')

    # AQUI ESTÁ A CORREÇÃO: Busca o ID do pedido rascunho na sessão.
    # A view 'continuar_pedido' é que salva este ID.
    pedido_id_rascunho = request.session.get('pedido_id_rascunho', None)
    
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

            if valor_unitario is None:
                valor_unitario = Decimal('0.00')

            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item

            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
                'valor_unitario_formatado': f"{valor_unitario.quantize(Decimal('0.01'))}".replace('.', ','),
                'valor_total_formatado': f"{valor_total_item.quantize(Decimal('0.01'))}".replace('.', ','),
            })
        except Product.DoesNotExist:
            continue

    contexto = {
        'titulo': 'Carrinho de Compras',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral,
        'total_geral_formatado': f"R$ {total_geral.quantize(Decimal('0.01'))}".replace('.', ','),
        'preco_exibido': preco_exibido,
        # Adiciona o ID ao contexto, garantindo que o template tenha acesso a ele
        'pedido_id_rascunho': pedido_id_rascunho,
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





# views.py

# ... (seus outros imports)

@login_required
def checkout(request, pedido_id_rascunho=None):
    # Lógica para o método POST (quando o formulário de checkout é enviado)
    if request.method == 'POST':
        # Pega os dados do formulário
        endereco_id = request.POST.get('endereco_selecionado')
        data_envio_str = request.POST.get('data_expedicao')
        frete_option = request.POST.get('frete_option')
        nota_fiscal = request.POST.get('nota_fiscal')
        observacao = request.POST.get('observacao')

        # Tenta pegar o ID do pedido rascunho da URL ou do formulário
        id_do_pedido = pedido_id_rascunho or request.POST.get('pedido_id_rascunho')

        # --- DEBUG: Verificando o ID do pedido ---
        print("================ DEBUG POST ================")
        print(f"ID do pedido obtido na requisição POST: {id_do_pedido}")
        print("------------------------------------------")

        endereco_selecionado = None
        fretes_sem_endereco = ['ONIBUS', 'RETIRADA']
        data_envio_obj = None

        try:
            if id_do_pedido:
                pedido_rascunho = get_object_or_404(Pedido, id=id_do_pedido)
                cliente_logado = pedido_rascunho.cliente
            else:
                if request.user.is_staff:
                    messages.error(request, 'Usuários administrativos não podem criar pedidos por esta página.')
                    return redirect('home')
                cliente_logado = request.user.wfclient

            if frete_option not in fretes_sem_endereco:
                if not endereco_id:
                    messages.error(request, 'Por favor, selecione um endereço válido.')
                    if id_do_pedido:
                        return redirect('checkout_rascunho', pedido_id_rascunho=id_do_pedido)
                    else:
                        return redirect('checkout')
                endereco_selecionado = get_object_or_404(Endereco, id=endereco_id, cliente=cliente_logado)
            
            if data_envio_str:
                data_envio_obj = datetime.strptime(data_envio_str, '%Y-%m-%d').date()
            
        except (WfClient.DoesNotExist, Endereco.DoesNotExist, ValueError) as e:
            messages.error(request, f'Dados de cliente, endereço, frete ou data inválidos: {e}')
            return redirect('home')

        with transaction.atomic():
            if id_do_pedido:
                # --- DEBUG: Verificando se o bloco de atualização é acessado ---
                print("================ DEBUG ATUALIZAÇÃO ================")
                print(f"Entrando no bloco para ATUALIZAR o Pedido #{id_do_pedido}")
                print("-------------------------------------------------")
                
                # ATUALIZA o pedido rascunho existente
                pedido_rascunho.endereco = endereco_selecionado
                pedido_rascunho.data_envio_solicitada = data_envio_obj
                pedido_rascunho.frete_option = frete_option
                pedido_rascunho.nota_fiscal = nota_fiscal
                pedido_rascunho.observacao = observacao
                pedido_rascunho.status = 'PENDENTE'
                pedido_rascunho.save()
            else:
                # --- DEBUG: Verificando se o bloco de criação é acessado ---
                print("================ DEBUG CRIAÇÃO ================")
                print("Entrando no bloco para CRIAR um novo pedido")
                print("---------------------------------------------")

                # CRIA um novo pedido a partir do carrinho
                carrinho_da_sessao = request.session.get('carrinho', {})
                if not carrinho_da_sessao:
                    messages.error(request, 'Seu carrinho está vazio.')
                    return redirect('home')

                pedido = Pedido.objects.create(
                    cliente=cliente_logado,
                    endereco=endereco_selecionado,
                    data_envio_solicitada=data_envio_obj,
                    frete_option=frete_option,
                    nota_fiscal=nota_fiscal,
                    observacao=observacao,
                    criado_por=request.user,
                )
                for product_id, quantidade in carrinho_da_sessao.items():
                    product = get_object_or_404(Product, product_id=product_id)
                    ItemPedido.objects.create(
                        pedido=pedido,
                        produto=product,
                        quantidade=quantidade,
                        valor_unitario_sp=product.product_value_sp,
                        valor_unitario_es=product.product_value_es,
                    )
                
                if 'carrinho' in request.session:
                    del request.session['carrinho']

        messages.success(request, 'Seu pedido foi realizado com sucesso!')
        return redirect('home')

    # Lógica para o método GET (primeira vez que a página é acessada)
    cliente_logado = None
    initial_data = {}
    
    if pedido_id_rascunho:
        pedido_para_finalizar = get_object_or_404(Pedido, id=pedido_id_rascunho)
        cliente_logado = pedido_para_finalizar.cliente
        carrinho_detalhes = [
            {
                'product': item.produto,
                'quantidade': item.quantidade,
                'valor_unitario': item.valor_unitario_sp if cliente_logado.client_state.uf_name == 'SP' else item.valor_unitario_es,
                'valor_total': item.get_total(),
            }
            for item in pedido_para_finalizar.itens.all()
        ]
        total_geral = pedido_para_finalizar.get_total_geral()
        initial_data = {
            'endereco_selecionado': pedido_para_finalizar.endereco.id if pedido_para_finalizar.endereco else None,
            'data_envio': pedido_para_finalizar.data_envio_solicitada,
            'frete_option': pedido_para_finalizar.frete_option,
            'nota_fiscal': pedido_para_finalizar.nota_fiscal,
            'observacao': pedido_para_finalizar.observacao,
        }
    else:
        carrinho_da_sessao = request.session.get('carrinho', {})
        if not carrinho_da_sessao:
            messages.error(request, 'Seu carrinho está vazio.')
            return redirect('home')

        if not request.user.is_staff:
            try:
                cliente_logado = request.user.wfclient
            except WfClient.DoesNotExist:
                messages.error(request, 'Usuário não tem um cliente associado.')
                return redirect('home')
        else:
            messages.error(request, 'Usuários administrativos não podem criar pedidos por esta página.')
            return redirect('home')

        carrinho_detalhes = []
        total_geral = Decimal('0.00')

        for product_id, quantidade in carrinho_da_sessao.items():
            product = get_object_or_404(Product, product_id=product_id)
            if cliente_logado.client_state.uf_name == 'SP':
                valor_unitario = product.product_value_sp
            elif cliente_logado.client_state.uf_name == 'ES':
                valor_unitario = product.product_value_es
            else:
                valor_unitario = product.product_value_sp
            if valor_unitario is None: valor_unitario = Decimal('0.00')
            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item
            carrinho_detalhes.append({
                'product': product,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
            })

    if cliente_logado and cliente_logado.client_state.uf_name == 'SP':
        preco_exibido = 'sp'
    elif cliente_logado and cliente_logado.client_state.uf_name == 'ES':
        preco_exibido = 'es'
    else:
        preco_exibido = 'sp'

    enderecos = Endereco.objects.filter(cliente=cliente_logado) if cliente_logado else Endereco.objects.none()

    contexto = {
        'titulo': 'Confirmação de Compra',
        'carrinho_detalhes': carrinho_detalhes,
        'total_geral': total_geral,
        'enderecos': enderecos,
        'preco_exibido': preco_exibido,
        'cliente_logado': cliente_logado,
        'initial_data': initial_data,
        'pedido_id_rascunho': pedido_id_rascunho,
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
    paginator = Paginator(pedidos_qs, 10)
    page = request.GET.get('page')

    try:
        pedidos_page = paginator.page(page)
    except PageNotAnInteger:
        pedidos_page = paginator.page(1)
    except EmptyPage:
        pedidos_page = paginator.page(paginator.num_pages)

    # A view agora só passa a QuerySet paginada para o template
    contexto = {
        'pedidos': pedidos_page, # Passamos o objeto paginado diretamente
        'titulo': 'Histórico de Pedidos',
    }
    return render(request, 'historico_pedidos.html', contexto)
#Inicio detalhes pedido

@login_required
def detalhes_pedido(request, pedido_id):
    try:
        # Acesso ao cliente logado
        cliente_logado = request.user.wfclient
    except WfClient.DoesNotExist:
        messages.error(request, "Erro: Usuário não tem um cliente associado.")
        return redirect('home')

    # Garante que o usuário logado só possa ver o próprio pedido, a menos que seja um admin.
    # A lógica aqui é mais robusta. Admins podem ver qualquer pedido.
    if request.user.is_staff:
        pedido = get_object_or_404(Pedido, id=pedido_id)
    else:
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente_logado)

    # Obtém o estado do cliente do pedido para saber qual preço exibir
    estado_cliente = pedido.cliente.client_state.uf_name

    # Define qual preço será exibido
    preco_exibido = 'sp' if estado_cliente == 'SP' else 'es'

    itens_detalhes = []
    total_geral = Decimal('0.00')
    itens = ItemPedido.objects.filter(pedido=pedido)

    for item in itens:
        # Seleciona o valor unitário correto com base no estado do cliente
        if preco_exibido == 'sp':
            valor_unitario = item.valor_unitario_sp
        else:
            valor_unitario = item.valor_unitario_es

        # Garante que o valor não seja None
        if valor_unitario is None:
            valor_unitario = Decimal('0.00')

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


# Fim detalhes pedido

# Configuração do locale para o formato brasileiro
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')




@staff_member_required
def dashboard_admin(request):
    # Expressão que DEVE calcular o valor congelado (CORRETO)
    calculo_total_vendas_geral = ExpressionWrapper(
        F('quantidade') * Coalesce(
            F('valor_unitario_sp'), 
            F('valor_unitario_es'), 
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        output_field=DecimalField()
    )

    # --- CÁLCULO TOTAL DE VENDAS (HISTÓRICO CORRETO) ---
    total_vendas_correta_agg = ItemPedido.objects.annotate(
        subtotal=calculo_total_vendas_geral
    ).exclude(
        pedido__status='CANCELADO' 
    ).aggregate(total_vendas=Sum('subtotal'))
    
    valor_total_vendas_correta = total_vendas_correta_agg['total_vendas'] or Decimal('0.00')

    # === DEBUG: VERIFICAÇÃO COM PREÇO ATUAL DO PRODUTO ===
    # Esta Query INCORRETA (preço do Produto) está provavelmente causando a divergência.
    # Rodaremos ela para ver se ela gera R$ 771.917,09
    try:
        total_vendas_produto_agg = ItemPedido.objects.annotate(
            # Tenta se ligar ao preço atual do modelo Product (QUE É O ERRO COMUM)
            subtotal_produto=F('quantidade') * F('produto__product_value_sp') 
        ).exclude(
            pedido__status='CANCELADO'
        ).aggregate(total_vendas_produto=Sum('subtotal_produto'))
        
        valor_total_vendas_produto = total_vendas_produto_agg['total_vendas_produto'] or Decimal('0.00')
    except Exception:
         valor_total_vendas_produto = Decimal('0.00')

    print("================ DEBUG DIVERGÊNCIA ADMINISTRATIVO ================")
    print(f"1. VALOR CORRETO (PREÇO CONGELADO ItemPedido): R$ {valor_total_vendas_correta:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"2. VALOR INCONSISTENTE (PREÇO ATUAL Product): R$ {valor_total_vendas_produto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print("------------------------------------------------------------------")
    # Fim do bloco de debug

    # O valor que deve ser enviado é o CORRETO (PREÇO CONGELADO)
    valor_total_vendas_decimal = valor_total_vendas_correta
    valor_total_vendas_formatado = locale.currency(valor_total_vendas_decimal, grouping=True, symbol='R$ ')
    
    # Restante da sua view...
    total_clientes = WfClient.objects.count()
    total_pedidos = Pedido.objects.count()
    pedidos_pendentes = Pedido.objects.filter(status='PENDENTE').count()
    pedidos_concluidos = Pedido.objects.filter(status='FINALIZADO').count()
    pedidos_orcamento = Pedido.objects.filter(status='ORCAMENTO').count()
    pedidos_adc = Pedido.objects.filter(status='FINANCEIRO').count()
    pedidos_separacao = Pedido.objects.filter(status='SEPARACAO').count()
    pedidos_expedicao = Pedido.objects.filter(status='EXPEDICAO').count()
    pedidos_atrasados = Pedido.objects.filter(status='ATRASADO').count()
    
    pedidos_recentes_qs = Pedido.objects.all().order_by('-data_criacao')[:5]
    pedidos_com_total = []
    for pedido in pedidos_recentes_qs:
        total_pedido = pedido.get_total_geral() or Decimal('0.00')
        pedidos_com_total.append({
            'id': pedido.id,
            'cliente': pedido.cliente,
            'data_criacao': pedido.data_criacao,
            'total': locale.currency(total_pedido, grouping=True, symbol='R$ ')
        })
        
    contexto = {
        'titulo': 'Dashboard Administrativo',
        'total_clientes': total_clientes,
        'total_pedidos': total_pedidos,
        'total_vendas': valor_total_vendas_formatado, 
        'pedidos_recentes': pedidos_com_total,
        'pedidos_pendentes': pedidos_pendentes,
        'pedidos_concluidos': pedidos_concluidos,
        'pedidos_orcamento': pedidos_orcamento,
        'pedidos_adc': pedidos_adc,
        'pedidos_separacao': pedidos_separacao,
        'pedidos_expedicao': pedidos_expedicao,
        'pedidos_atrasados': pedidos_atrasados,
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
    # MUDANÇA 1: Inclusão de 'Grupo' e 'Marca' nos cabeçalhos
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'valor_unitario_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'valor_unitario_es'
    else:
        # Padrão caso o estado não seja SP ou ES
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = 'valor_unitario_sp'

    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=row_num, column=col_num, value=column_title)

    itens = ItemPedido.objects.filter(pedido=pedido)
    total_geral = 0

    for item in itens:
        row_num += 1

        valor_unitario = getattr(item, valor_key)
        
        if valor_unitario is None:
            valor_unitario = 0

        subtotal = valor_unitario * item.quantidade
        total_geral += subtotal

        # MUDANÇA 2: Preenchimento das células com os novos índices
        worksheet.cell(row=row_num, column=1, value=item.produto.product_code)
        worksheet.cell(row=row_num, column=2, value=item.produto.product_description)
        
        # Novas Colunas
        worksheet.cell(row=row_num, column=3, value=item.produto.product_group) # Grupo
        worksheet.cell(row=row_num, column=4, value=item.produto.product_brand) # Marca
        
        # Colunas deslocadas (+2 posições)
        worksheet.cell(row=row_num, column=5, value=item.quantidade)
        worksheet.cell(row=row_num, column=6, value=valor_unitario)
        worksheet.cell(row=row_num, column=7, value=subtotal)

    row_num += 1
    
    # MUDANÇA 3: Ajuste da posição do Total Geral (agora nas colunas 6 e 7)
    worksheet.cell(row=row_num, column=6, value="Total Geral:")
    worksheet.cell(row=row_num, column=7, value=total_geral)

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


# GARANTA QUE APENAS ESTA VERSÃO DA FUNÇÃO EXISTA NO SEU views.py
# NOVO ARQUIVO views.py (versão limpa)

@staff_member_required
def todos_os_pedidos(request):
    pedidos_qs = Pedido.objects.all().order_by('-data_criacao')

    paginator = Paginator(pedidos_qs, 20)
    page_number = request.GET.get('page', 1)
    
    try:
        pedidos_paginados = paginator.page(page_number)
    except PageNotAnInteger:
        pedidos_paginados = paginator.page(1)
    except EmptyPage:
        pedidos_paginados = paginator.page(paginator.num_pages)

    hoje = timezone.localdate()
    for pedido in pedidos_paginados:
        if pedido.data_envio_solicitada and pedido.data_envio_solicitada < hoje and pedido.status not in ['FINALIZADO', 'CANCELADO']:
            pedido.is_atrasado = True
        else:
            pedido.is_atrasado = False

    contexto = {
        'titulo': 'Todos os Pedidos',
        'pedidos': pedidos_paginados,
    }

    # --- ESTA É A PARTE QUE REATIVA O SCROLL INFINITO ---
    if request.htmx:
        # Quando o usuário rola a página, o HTMX faz uma requisição especial.
        # Esta linha responde a essa requisição enviando APENAS as novas linhas da tabela.
        return render(request, '_pedidos_rows.html', contexto)

    # Quando o usuário carrega a página pela primeira vez, esta linha é executada.
    return render(request, 'todos_os_pedidos.html', contexto)
# Deixe o resto do arquivo em branco por enquanto


'''
@staff_member_required
def todos_os_pedidos(request):
    pedidos_qs = Pedido.objects.all().order_by('-data_criacao')

    paginator = Paginator(pedidos_qs, 20)
    page_number = request.GET.get('page', 1)
    
    try:
        pedidos_paginados = paginator.page(page_number)
    except PageNotAnInteger:
        pedidos_paginados = paginator.page(1)
    except EmptyPage:
        pedidos_paginados = paginator.page(paginator.num_pages)

    hoje = timezone.localdate()
    for pedido in pedidos_paginados:
        if pedido.data_envio_solicitada and pedido.data_envio_solicitada < hoje and pedido.status not in ['FINALIZADO', 'CANCELADO']:
            pedido.is_atrasado = True
        else:
            pedido.is_atrasado = False

    contexto = {
        'titulo': 'Todos os Pedidos',
        'pedidos': pedidos_paginados,
    }

    # Verifica se a requisição é do HTMX (para o scroll infinito)
    if request.htmx:
        # Se for, renderiza apenas o template parcial com as novas linhas
        return render(request, '_pedidos_rows.html', contexto) # <-- CAMINHO CORRIGIDO

    # Se for uma requisição normal, renderiza a página completa
    return render(request, 'todos_os_pedidos.html', contexto) # <-- CAMINHO CORRIGIDO'''

# Modelo de Pedido
    
@staff_member_required
def atualizar_status_pedido(request, pedido_id):
    if request.method == 'POST':
        pedido = get_object_or_404(Pedido, id=pedido_id)
        novo_status = request.POST.get('status')
        # CORREÇÃO AQUI: Atualize a lista de status permitidos
        if novo_status in ['PENDENTE', 'ORCAMENTO', 'FINANCEIRO', 'SEPARACAO', 'EXPEDICAO', 'FINALIZADO', 'CANCELADO']:
            pedido.status = novo_status
            pedido.save()
            messages.success(request, f'Status do Pedido #{pedido.id} alterado para {novo_status} com sucesso!')
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
                            'date_product': date.today(),
                        }
                    )
                    produtos_processados += 1
                
            messages.success(request, f'{produtos_processados} produtos processados com sucesso.')
            return redirect('pagina_upload')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao processar as planilhas: {e}')
            return redirect('pagina_upload')

    return render(request, 'upload_planilha.html')

# Início da função gerar_pedido
@login_required
def gerar_pedido(request):
    if request.method == 'POST':
        cart_data_json = request.POST.get('cart_data', '{}')
        
        if not cart_data_json:
            messages.error(request, 'Erro ao processar os dados do carrinho.')
            return redirect('home')

        try:
            carrinho_da_sessao = json.loads(cart_data_json)
            carrinho_filtrado = {}
            for product_id_str, quantidade_str in carrinho_da_sessao.items():
                try:
                    quantidade = int(quantidade_str)
                    if quantidade > 0:
                        carrinho_filtrado[product_id_str] = quantidade
                except (ValueError, TypeError):
                    continue
            
            if not carrinho_filtrado:
                messages.error(request, 'Seu carrinho está vazio ou contém itens inválidos.')
                return redirect('home')

            request.session['carrinho'] = carrinho_filtrado
            
            # --- AQUI ESTÁ A CORREÇÃO ---
            # Verifica se há um ID de pedido rascunho na sessão
            pedido_id_rascunho = request.session.get('pedido_id_rascunho')

            if pedido_id_rascunho:
                # Se houver, redireciona para o checkout com o ID do rascunho
                return redirect('checkout_rascunho', pedido_id_rascunho=pedido_id_rascunho)
            else:
                # Se não houver, redireciona para o checkout padrão
                return redirect('checkout')

        except json.JSONDecodeError:
            messages.error(request, 'Erro ao processar os dados do carrinho.')
            return redirect('home')
    
    return redirect('home')
# Fim da função gerar_pedido


# views.py
# ... (seus imports) ...

# views.py

@login_required
def atualizar_rascunho(request):
    if request.method == 'POST':
        carrinho_da_sessao = request.session.get('carrinho', {})
        pedido_id_rascunho = request.session.get('pedido_id_rascunho')

        if not pedido_id_rascunho:
            messages.error(request, 'Não há pedido rascunho na sessão para atualizar.')
            return redirect('carrinho')

        try:
            pedido = get_object_or_404(Pedido, id=pedido_id_rascunho)
        except Pedido.DoesNotExist:
            messages.error(request, 'Pedido rascunho não encontrado.')
            return redirect('home')

        with transaction.atomic():
            # Apaga todos os itens do pedido antigo
            pedido.itens.all().delete()

            # Adiciona os itens atualizados do carrinho na sessão
            for product_id, quantidade in carrinho_da_sessao.items():
                product = get_object_or_404(Product, product_id=product_id)
                
                # ... (sua lógica de valor unitário) ...

                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=product,
                    quantidade=quantidade,
                    valor_unitario_sp=product.product_value_sp,
                    valor_unitario_es=product.product_value_es,
                )

        messages.success(request, 'Pedido rascunho atualizado com sucesso!')
        
        # AQUI ESTÁ A LINHA DE REDIRECIONAMENTO QUE PRECISA SER VERIFICADA
        return redirect('checkout_rascunho', pedido_id_rascunho=pedido_id_rascunho)
    
    return redirect('carrinho')

# Em views.py
# GARANTA QUE APENAS ESTA VERSÃO DA FUNÇÃO EXISTA NO ARQUIVO

@staff_member_required
def detalhes_pedido_admin(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id) 
        
        estado_cliente = pedido.cliente.client_state.uf_name
        preco_exibido = 'sp' if estado_cliente == 'SP' else 'es'
        
        itens_detalhes = []
        total_geral = Decimal('0.00')
        itens = ItemPedido.objects.filter(pedido=pedido)

        for item in itens:
            valor_unitario = item.valor_unitario_sp if estado_cliente == 'SP' else item.valor_unitario_es
            
            if valor_unitario is None:
                valor_unitario = Decimal('0.00')

            # Garante que a quantidade não seja None para o cálculo
            quantidade = item.quantidade if item.quantidade is not None else 0
            valor_total_item = valor_unitario * quantidade
            total_geral += valor_total_item

            itens_detalhes.append({
                'item': item,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total_item,
            })
        
        # Lógica para verificar se o pedido está atrasado
        hoje = timezone.localdate()
        is_atrasado = False
        if pedido.data_envio_solicitada and pedido.data_envio_solicitada < hoje and pedido.status not in ['FINALIZADO', 'CANCELADO']:
            is_atrasado = True
        
        # Dicionário de contexto que é enviado para o template
        contexto = {
            'titulo': f"Detalhes do Pedido #{pedido.id}",
            'pedido': pedido,
            'itens_detalhes': itens_detalhes,
            'total_geral': total_geral,
            'preco_exibido': preco_exibido,
            'is_atrasado': is_atrasado, # <-- A linha que faltava na versão antiga
        }
        
        return render(request, 'detalhes_pedido.html', contexto)

    except Pedido.DoesNotExist:
        messages.error(request, "Erro: Pedido não encontrado.")
        return redirect('todos_os_pedidos')
    except WfClient.DoesNotExist:
        messages.error(request, "Erro: Cliente associado ao pedido não encontrado.")
        return redirect('todos_os_pedidos')
    
@staff_member_required
def pedidos_para_hoje(request):
    """
    View que filtra e exibe os pedidos agendados para a data atual
    e também os pedidos atrasados que ainda estão pendentes.
    """
    # Pega a data de hoje, respeitando o timezone do seu projeto
    hoje = timezone.localdate()

    # --- Consulta 1: Pedidos agendados para HOJE que ainda precisam de ação ---
    pedidos_hoje = Pedido.objects.filter(
        data_envio_solicitada=hoje
    ).exclude(
        status__in=['FINALIZADO', 'CANCELADO'] # Exclui os que já foram concluídos
    )

    # --- Consulta 2: Pedidos ATRASADOS que ainda precisam de ação ---
    pedidos_atrasados = Pedido.objects.filter(
        data_envio_solicitada__lt=hoje  # __lt = 'less than' (data anterior a hoje)
    ).exclude(
        status__in=['FINALIZADO', 'CANCELADO'] # Exclui os que já foram concluídos
    ).order_by('data_envio_solicitada') # Mostra os mais antigos primeiro

    # Monta o contexto com as duas listas de pedidos
    context = {
        'pedidos_hoje': pedidos_hoje,
        'pedidos_atrasados': pedidos_atrasados,
        'data_hoje': hoje,
        'titulo': 'Pedidos para Saída' # Adicionado para o título da página
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
        observacao = request.POST.get('observacao') # <-- ADICIONE ESTA LINHA
        
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
            data_envio = datetime.strptime(data_envio, '%Y-%m-%d').date()
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
                    valor_total=Decimal('0.00'),
                    observacao=observacao # <-- ADICIONE ESTA LINHA

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
    """Normaliza o texto, remove acentos, e converte para minúsculas."""
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
# --- FIM DA CORREÇÃO ---


# Sua view views.py

# Seu arquivo views.py

# views.py

# ... (todos os seus imports)




# views.py

@staff_member_required
def upload_pedido(request):
    """
    Processa o upload de uma planilha de pedido, cria um Pedido (Rascunho),
    salva os itens válidos em ItemPedido e os itens com falha em ItemPedidoIgnorado.
    Ignora linhas de somatório (TOTAL, SUBTOTAL) silenciosamente.
    """
    clientes_ordenados = WfClient.objects.all().order_by('client_code')
    cliente_selecionado = None
    form_cliente = SelectClientForm(request.GET or None)
    initial_data = {}
    upload_form = None

    # Lógica de seleção prévia do cliente (via GET)
    if form_cliente.is_valid():
        cliente_selecionado = form_cliente.cleaned_data.get('cliente')
        if cliente_selecionado:
            initial_data['frete_preferencia'] = cliente_selecionado.frete_preferencia
            initial_data['nota_fiscal_preferencia'] = cliente_selecionado.nota_fiscal_preferencia
            initial_data['observacao_preferencia'] = cliente_selecionado.observacao_preferencia
            endereco_padrao = Endereco.objects.filter(cliente=cliente_selecionado, is_default=True).first()
            if endereco_padrao:
                initial_data['endereco_selecionado'] = endereco_padrao.id
    
    if request.method == 'POST':
        cliente_id_post = request.POST.get('cliente_id')
        if not cliente_id_post:
            messages.error(request, 'Por favor, selecione um cliente.')
            return redirect('upload_pedido')

        cliente_para_validacao = get_object_or_404(WfClient, pk=cliente_id_post)
        
        form = UploadPedidoForm(request.POST, request.FILES)
        enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_para_validacao)
        form.fields['endereco_selecionado'].queryset = enderecos_do_cliente

        if form.is_valid():
            try:
                planilha_pedido = request.FILES.get('planilha_pedido')
                if not planilha_pedido:
                    messages.error(request, 'Nenhum arquivo de planilha foi selecionado.')
                    return redirect('upload_pedido')
                    
                # 1. Leitura do arquivo (Excel ou CSV)
                if planilha_pedido.name.endswith('.csv'):
                    df_list = [pd.read_csv(planilha_pedido)]
                else:
                    xls_data = pd.read_excel(planilha_pedido, sheet_name=None)
                    df_list = list(xls_data.values())
                
                if not df_list:
                     messages.error(request, 'A planilha de upload está vazia.')
                     return redirect('upload_pedido')
                     
                df_completo = pd.concat(df_list, ignore_index=True)
                df = df_completo.dropna(how='all') 

                if df.empty:
                    messages.error(request, 'A planilha de upload não contém dados após a leitura.')
                    return redirect('upload_pedido')

                # 2. Normalização e Mapeamento de Colunas
                # Certifique-se de que a função normalize_text existe no seu código ou imports
                df.columns = [normalize_text(col) for col in df.columns]
                
                expected_cols = {
                    'codigo': ['codigo', 'código', 'cod'],
                    'quantidade': ['quantidade', 'qtd', 'qtde'],
                    'descricao': ['descricao', 'descrição', 'produto', 'nome', 'description']
                }
                
                col_mapping = {
                    key: next((c for c in values if c in df.columns), None)
                    for key, values in expected_cols.items()
                }

                if not col_mapping['codigo'] or not col_mapping['quantidade']:
                    messages.error(request, "A planilha deve ter colunas para 'código' e 'quantidade'.")
                    return redirect('upload_pedido')
                
                with transaction.atomic():
                    # 3. Criação do Pedido Rascunho
                    novo_pedido = Pedido.objects.create(
                        cliente=cliente_para_validacao,
                        endereco=form.cleaned_data.get('endereco_selecionado'),
                        data_criacao=timezone.now(),
                        data_envio_solicitada=form.cleaned_data['data_expedicao'],
                        frete_option=form.cleaned_data['frete_option'],
                        nota_fiscal=form.cleaned_data['nota_fiscal'],
                        status='RASCUNHO',
                        criado_por=request.user,
                        observacao=form.cleaned_data['observacao_preferencia'],
                    )
                    
                    erros_texto = [] # Log para o campo texto do pedido e display
                    itens_pedido_para_criar = [] # Itens válidos
                    itens_ignorados_db = [] # Itens inválidos (para tabela de erros)
                    total_valor_pedido = Decimal('0.0')

                    # Otimização: Busca produtos em lote para evitar N queries
                    latest_dates = Product.objects.filter(product_code=OuterRef('product_code')).order_by('-date_product').values('date_product')[:1]
                    produtos_atuais = Product.objects.filter(date_product=Subquery(latest_dates)).in_bulk(field_name='product_code')

                    # 4. Processamento linha a linha
                    for index, row in df.iterrows():
                        
                        codigo_produto_raw = row[col_mapping['codigo']]
                        if pd.isna(codigo_produto_raw):
                             continue
                             
                        codigo_produto = str(codigo_produto_raw).strip()

                        # --- FILTRO DE RODAPÉ (TOTAL GERAL) ---
                        # Ignora silenciosamente linhas que contêm palavras de somatório
                        termos_ignorar = ['TOTAL', 'SUBTOTAL', 'GERAL', 'VALOR TOTAL']
                        codigo_upper = codigo_produto.upper()
                        if any(termo in codigo_upper for termo in termos_ignorar):
                            continue
                        # --------------------------------------

                        quantidade_raw = row[col_mapping['quantidade']]
                        
                        # Tenta obter a descrição da planilha (fallback caso produto não exista)
                        descricao_excel = row.get(col_mapping.get('descricao'), 'Descrição não informada na planilha')
                        
                        # --- Validação A: Quantidade Nula ---
                        if pd.isnull(quantidade_raw):
                            continue

                        # --- Validação B: Quantidade Numérica ---
                        try:
                            quantidade = int(quantidade_raw)
                        except ValueError:
                            msg = "Quantidade inválida (não-numérica)"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido,
                                cliente=cliente_para_validacao,
                                codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel),
                                quantidade_tentada=0,
                                motivo_erro=msg
                            ))
                            continue

                        # --- Validação C: Quantidade Zero ou Negativa ---
                        if quantidade <= 0:
                            msg = "Quantidade zero ou negativa"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido,
                                cliente=cliente_para_validacao,
                                codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel),
                                quantidade_tentada=quantidade,
                                motivo_erro=msg
                            ))
                            continue

                        # --- Validação D: Produto Existe no Catálogo? ---
                        produto = produtos_atuais.get(codigo_produto)
                        if not produto:
                            msg = "Não encontrado no catálogo"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido,
                                cliente=cliente_para_validacao,
                                codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel),
                                quantidade_tentada=quantidade,
                                motivo_erro=msg
                            ))
                            continue
                            
                        # --- Validação E: Estoque e Preço ---
                        regiao = cliente_para_validacao.client_state.uf_name
                        valor_field = 'product_value_sp' if regiao == 'SP' else 'product_value_es'
                        valor_unitario = getattr(produto, valor_field)
                        
                        if valor_unitario is None or valor_unitario <= 0:
                            msg = "Produto indisponível no estoque/tabela"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido,
                                cliente=cliente_para_validacao,
                                codigo_produto=codigo_produto,
                                descricao_produto=produto.product_description, # Usa descrição oficial
                                quantidade_tentada=quantidade,
                                motivo_erro=msg
                            ))
                            continue

                        # Se passou por tudo, adiciona aos itens válidos
                        total_valor_pedido += valor_unitario * Decimal(quantidade)
                        itens_pedido_para_criar.append(ItemPedido(
                            pedido=novo_pedido,
                            produto=produto,
                            quantidade=quantidade,
                            valor_unitario_sp=produto.product_value_sp,
                            valor_unitario_es=produto.product_value_es,
                        ))
                    
                    # 5. Finalização
                    
                    # Se a planilha não gerou NADA (nem válido, nem erro - vazia de dados úteis)
                    if not itens_pedido_para_criar and not itens_ignorados_db:
                        messages.error(request, "Nenhum dado processável encontrado na planilha.")
                        novo_pedido.delete()
                        return redirect('upload_pedido')
                    
                    # Salva Itens Válidos em lote
                    if itens_pedido_para_criar:
                        ItemPedido.objects.bulk_create(itens_pedido_para_criar)
                    
                    # Salva Itens Ignorados em lote
                    if itens_ignorados_db:
                        ItemPedidoIgnorado.objects.bulk_create(itens_ignorados_db)
                    
                    # Mensagens e Logs
                    if erros_texto:
                        novo_pedido.erros_upload = '\n'.join(erros_texto)
                        
                        erros_msg = 'Alguns itens foram ignorados:\n' + '\n'.join(erros_texto[:5])
                        if len(erros_texto) > 5:
                            erros_msg += f'\n...e mais {len(erros_texto) - 5} erros.'
                        messages.warning(request, f"Pedido criado parcialmente. {erros_msg}")
                    else:
                        messages.success(request, f"Itens carregados com sucesso. Por favor, confira os dados e finalize o pedido.")
                    
                    novo_pedido.valor_total = total_valor_pedido
                    novo_pedido.save()
                    
                    return redirect('checkout_rascunho', pedido_id_rascunho=novo_pedido.id)
            
            except Exception as e:
                messages.error(request, f"Erro crítico ao processar a planilha: {e}")
                # Garante que não fica lixo no banco se der erro fatal
                if 'novo_pedido' in locals():
                    novo_pedido.delete()
                upload_form = form
        else:
            upload_form = form
    else:
        # GET request
        upload_form = UploadPedidoForm(initial=initial_data)
        if cliente_selecionado:
            enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_selecionado)
            upload_form.fields['endereco_selecionado'].queryset = enderecos_do_cliente

    context = {
        'form_cliente': form_cliente,
        'clientes_ordenados': clientes_ordenados,
        'cliente_selecionado': cliente_selecionado,
        'upload_form': upload_form,
    }
    
    return render(request, 'upload_pedido.html', context)

















@staff_member_required
def pedidos_em_andamento(request):
    """
    Exibe uma lista de pedidos com o status 'ORCAMENTO' (rascunhos)
    para que o administrador possa visualizá-los e continuar a edição.
    """
    pedidos_rascunho = Pedido.objects.filter(
        status='RASCUNHO'
    ).order_by('-data_criacao')
    
    context = {
        'titulo': 'Pedidos em Andamento (Rascunhos)',
        'pedidos': pedidos_rascunho,
    }
    
    # AQUI ESTÁ O AJUSTE. O caminho aponta direto para o arquivo.
    return render(request, 'pedidos_em_andamento.html', context)


# No seu arquivo views.py

# views.py

# ... (restante do código)

@staff_member_required
def continuar_pedido(request, pedido_id):
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id, status='RASCUNHO')
    except Pedido.DoesNotExist:
        messages.error(request, 'O pedido especificado não é um rascunho válido.')
        return redirect('pedidos_em_andamento')

    # ... (restante da sua lógica de sessão) ...

    # 1. Popula o carrinho da sessão com os itens do pedido rascunho
    carrinho_da_sessao = {}
    for item in pedido.itens.all():
        carrinho_da_sessao[str(item.produto.product_id)] = item.quantidade
    request.session['carrinho'] = carrinho_da_sessao
    
    # 2. Salva o ID do pedido na sessão
    request.session['pedido_id_rascunho'] = pedido.id

    messages.info(request, f'Você está continuando a edição do Pedido #{pedido.id}.')
    
    # --- DEBUG COM PRINT() ---
    url_nome = 'checkout_rascunho'
    url_kwargs = {'pedido_id_rascunho': pedido.id}
    print("================ DEBUG URL ================")
    print(f"Tentando redirecionar para a URL com nome: '{url_nome}'")
    print(f"Com os argumentos de palavra-chave: {url_kwargs}")
    print("-------------------------------------------")
    
    # 3. Redireciona para o checkout usando a URL específica com o ID
    return redirect(url_nome, **url_kwargs)

# ... (restante do código)




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
    # MUDANÇA 1: Adicionei 'Grupo' e 'Marca' nas listas de colunas abaixo
    if uf_cliente == 'SP':
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário (SP)', 'Subtotal']
        valor_key = 'valor_unitario_sp'
    elif uf_cliente == 'ES':
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário (ES)', 'Subtotal']
        valor_key = 'valor_unitario_es'
    else:
        # Padrão caso o estado não seja SP ou ES
        columns = ['Código', 'Descrição', 'Grupo', 'Marca', 'Quantidade', 'Valor Unitário', 'Subtotal']
        valor_key = 'valor_unitario_sp'

    # Criação do DataFrame com os dados dos itens
    data = []
    total_geral = 0

    for item in itens_pedido:
        # Acessa o valor do item de pedido usando a chave definida
        valor_unitario = getattr(item, valor_key)
        if valor_unitario is None:
            valor_unitario = 0
            
        subtotal = float(item.get_total())

        # Adiciona os dados à lista
        # MUDANÇA 2: Adicionei o mapeamento de Group e Brand
        data.append({
            'Código': item.produto.product_code,
            'Descrição': item.produto.product_description,
            'Grupo': item.produto.product_group,  # Novo campo
            'Marca': item.produto.product_brand,  # Novo campo
            'Quantidade': item.quantidade,
            'Valor Unitário': float(valor_unitario),
            'Subtotal': subtotal
        })
        
        total_geral += subtotal

    df = pd.DataFrame(data)

    # Renomeia a coluna 'Valor Unitário' para o nome correto (SP ou ES)
    df = df.rename(columns={'Valor Unitário': columns[5]}) # Ajustei o índice de 3 para 5, pois inserimos 2 colunas novas
    df = df[columns] # Reordena as colunas

    # MUDANÇA 3: Ajuste na linha de totais
    # A tabela agora tem 7 colunas. Precisamos de 5 vazias, 1 rótulo e 1 valor.
    df.loc[len(df)] = ['', '', '', '', '', 'Total Geral:', total_geral]

    # Criação da resposta HTTP
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens do Pedido')
        
        # Opcional: Ajuste automático da largura das colunas (melhoria visual)
        worksheet = writer.sheets['Itens do Pedido']
        worksheet.set_column('A:A', 15) # Código
        worksheet.set_column('B:B', 40) # Descrição
        worksheet.set_column('C:D', 20) # Grupo e Marca
        worksheet.set_column('E:G', 15) # Qtd e Valores

    output.seek(0)

    # Renomeia o arquivo com as novas informações
    data_hoje = date.today().strftime('%d-%m-%Y')
    filename = f"pedido_{pedido.cliente.client_code}_{data_hoje}.xlsx"
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


'''
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
        f"*OBS:* {pedido.observacao}\n"
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
'''

@staff_member_required
def enviar_whatsapp(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # 1. Construir o link de download público da planilha (isso permanece igual)
    link_download_excel = request.build_absolute_uri(
        reverse('exportar_detalhes_pedido_publico_excel', args=[pedido.id])
    )

    # 2. A linha do encurtador foi REMOVIDA
    # link_encurtado = encurtar_url(link_download_excel)

    # Informações básicas do pedido
    mensagem_base = (
        f"*Dados do Pedido*\n\n"
        f"*Codigo Interno:* {pedido.id}\n"
        f"*Código do Cliente:* {pedido.cliente.client_code}\n"
        f"*Razão Social:* {pedido.cliente.client_name}\n"
        f"*Data da Expedição:* {pedido.data_envio_solicitada.strftime('%d/%m/%Y')}\n"
        f"*Opção de Frete:* {pedido.get_frete_option_display()}\n"
        
        
    )

    # Adiciona o endereço de entrega (lógica inalterada)
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

    # 3. Conclui a mensagem usando o link original e completo
    mensagem_final = (
        f"{mensagem_base}"
        f"{endereco_texto}"
        f"*Opção de Nota Fiscal:* {pedido.get_nota_fiscal_display()}\n"
        f"*Valor total:* {pedido.valor_total}\n"
        f"*OBS:* {pedido.observacao}\n\n"
        f"*Download da Planilha de Itens:*\n" 
        f"{link_download_excel}"  # <- MUDANÇA AQUI: usando o link direto
    )

    # Codifica a mensagem para a URL do WhatsApp (lógica inalterada)
    link_whatsapp = f"https://wa.me/5516991273974?text={quote(mensagem_final)}"

    return redirect(link_whatsapp)



def pedidos_atrasados_view(request):
    # Pega a data de hoje para comparação
    hoje = date.today()

    # Esta é a consulta principal:
    pedidos_atrasados = Pedido.objects.filter(
        data_envio_solicitada__lt=hoje  # __lt significa 'less than' (menor que)
    ).exclude(
        status__in=['FINALIZADO', 'CANCELADO']  # Exclui os status da lista
    ).order_by('data_envio_solicitada')  # Opcional: ordena pelos mais antigos primeiro

    contexto = {
        'titulo': 'Pedidos Atrasados',
        'pedidos_atrasados': pedidos_atrasados
    }

    return render(request, 'pedidos_atrasados.html', contexto)

# Em seu arquivo views.py

@staff_member_required
def marcar_pedido_finalizado(request, pedido_id):
    # Apenas aceita requisições POST por segurança
    if request.method == 'POST':
        # Pega o pedido ou retorna um erro 404 se não existir
        pedido = get_object_or_404(Pedido, id=pedido_id)
        
        # Altera o status para 'FINALIZADO'
        pedido.status = 'FINALIZADO'
        pedido.save()
        
        # Envia uma mensagem de sucesso para o usuário
        messages.success(request, f'O Pedido #{pedido.id} foi marcado como FINALIZADO.')
    
    # Redireciona o usuário de volta para a página de detalhes de onde ele veio
    return redirect('detalhes_pedido_admin', pedido_id=pedido_id)

# views.py (ADICIONE AO SEU ARQUIVO)
from django.db.models import Sum, Count, F, Q, Case, When, Value, ExpressionWrapper, DecimalField, Subquery, OuterRef, CharField





@staff_member_required
def analise_dados_dashboard(request):
    periodo_geral_solicitado = 'periodo_geral' in request.GET
    
    # --- 1. Definição Inicial das Variáveis do Filtro ---
    data_fim_str = request.GET.get('data_fim')
    data_inicio_str = request.GET.get('data_inicio')
    
    # --- 2. Lógica de Conversão e Definição de Data ---
    if data_fim_str and not periodo_geral_solicitado:
        try:
            data_fim = datetime.strptime(data_fim_str, '%d/%m/%Y').date()
        except ValueError:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    else:
        data_fim = timezone.localdate()
        
    if periodo_geral_solicitado:
        # Quando 'Todo o Histórico' é clicado, forçamos as datas para exibição
        data_inicio = datetime(2000, 1, 1).date()
        data_inicio_display = data_inicio.strftime('%Y-%m-%d')
        data_fim_display = data_fim.strftime('%Y-%m-%d')
    elif data_inicio_str and data_fim_str: 
        # Lógica para filtro customizado
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%d/%m/%Y').date()
        except ValueError:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            
        data_inicio_display = data_inicio_str
        data_fim_display = data_fim_str
    else:
        # Período padrão (90 dias)
        data_inicio = data_fim - timedelta(days=90)
        data_inicio_display = data_inicio.strftime('%Y-%m-%d')
        data_fim_display = data_fim.strftime('%Y-%m-%d')
        
    CAMPO_DATA_FILTRO = 'pedido__data_envio_solicitada' 
    
    # --- 3. EXPRESSÕES REUTILIZÁVEIS DE VALOR ---
    valor_unitario_preferencial = Coalesce(
        F('valor_unitario_sp'), F('valor_unitario_es'), Value(Decimal('0.00'), output_field=DecimalField()) 
    )
    calculo_total_preferencial = ExpressionWrapper(
        F('quantidade') * valor_unitario_preferencial, output_field=DecimalField() 
    )
    calculo_total_itempedido_es = ExpressionWrapper(
        F('quantidade') * Coalesce(F('valor_unitario_es'), Value(Decimal('0.00'), output_field=DecimalField())), 
        output_field=DecimalField()
    )

    # --- 4. QuerySet Base (Histórico) ---
    base_queryset_com_dados = ItemPedido.objects.exclude(
        pedido__status='CANCELADO'
    )
    
    # --- 5. QuerySet Filtrado (ANOTAÇÃO DE VALOR) ---
    itens_filtrados = base_queryset_com_dados
    
    # APLICA O FILTRO DE DATA SOMENTE SE NÃO ESTIVER NO MODO HISTÓRICO TOTAL
    if not periodo_geral_solicitado:
        itens_filtrados = itens_filtrados.filter(
            **{f'{CAMPO_DATA_FILTRO}__gte': data_inicio, 
               f'{CAMPO_DATA_FILTRO}__lte': data_fim}
        ).exclude(
            **{f'{CAMPO_DATA_FILTRO}__isnull': True} 
        )
    
    # ANOTA O VALOR NO QUERYSET FINAL
    itens_filtrados = itens_filtrados.annotate(
        valor_total_item=calculo_total_preferencial 
    )

    # --- 6. Clientes que Mais Compraram (SEPARAÇÃO POR ESTADO) ---
    def get_top_clients_by_state(uf_name):
        return itens_filtrados.filter(
            pedido__cliente__client_state__uf_name=uf_name
        ).values(
            'pedido__cliente__client_id',
        ).annotate(
            nome=F('pedido__cliente__client_name'),  
            codigo=F('pedido__cliente__client_code'),
            total_gasto=Sum('valor_total_item'), 
            estado=Value(uf_name, output_field=CharField()), 
            num_pedidos=Count('pedido__id', distinct=True) 
        ).order_by('-total_gasto')[:5]

    clientes_top_sp = list(get_top_clients_by_state('SP'))
    clientes_top_es = list(get_top_clients_by_state('ES'))
    
    # --- 7. Produtos Mais Vendidos ---
    produtos_top = itens_filtrados.values(
        'produto__product_code', 
        'produto__product_description'
    ).annotate(
        total_vendido=Sum('quantidade')
    ).order_by('-total_vendido')[:5]
    
    # --- 8. Últimas Compras (placeholder) ---
    clientes_com_ultima_compra = [] 
    
    # --- 9. TOTAIS DE VENDA POR CLIENTE/ESTADO (para os cartões) ---
    total_vendas_sp_clientes = itens_filtrados.filter(
        pedido__cliente__client_state__uf_name='SP'
    ).aggregate(
        total=Sum('valor_total_item')
    )['total'] or Decimal('0.00')

    total_vendas_es_clientes = itens_filtrados.filter(
        pedido__cliente__client_state__uf_name='ES'
    ).annotate(
        valor_total_item_es=calculo_total_itempedido_es 
    ).aggregate(
        total=Sum('valor_total_item_es')
    )['total'] or Decimal('0.00')
    
    # NOVO: Total Geral Filtrado (Soma de todos os estados no período)
    total_vendas_periodo_calculado = itens_filtrados.aggregate(
        total=Sum('valor_total_item')
    )['total'] or Decimal('0.00')
    
    # --- 10. Vendas por Mês (Incluindo ES) ---
    vendas_por_mes = itens_filtrados.annotate(
        mes_ano=TruncMonth(CAMPO_DATA_FILTRO),
    ).values('mes_ano').annotate(
        total_vendas=Sum('valor_total_item'),
        total_vendas_es=Sum(calculo_total_itempedido_es)
    ).order_by('mes_ano')
    
    # --- 11. Total Geral Histórico (TESTE) ---
    # Este valor é o valor real do banco (usado para o card amarelo)
    total_historico_teste = total_vendas_periodo_calculado 
    
    # --- 12. Montagem do Contexto ---
    contexto = {
        'titulo': 'Dashboard de Análise de Dados',
        'data_inicio': data_inicio_display, 
        'data_fim': data_fim_display,
        'clientes_top_sp': clientes_top_sp,
        'clientes_top_es': clientes_top_es,
        'produtos_top': produtos_top,
        'clientes_com_ultima_compra': clientes_com_ultima_compra,
        'vendas_por_mes': vendas_por_mes,
        'total_vendas_sp_clientes': total_vendas_sp_clientes, 
        'total_vendas_es_clientes': total_vendas_es_clientes, 
        'total_vendas_periodo_calculado': total_vendas_periodo_calculado,
        'total_historico_teste': total_historico_teste,
        'periodo_geral_ativo': periodo_geral_solicitado
    }
    
    return render(request, 'analise/analise_dashboard.html', contexto)


# Função cliente upload


@login_required
def upload_pedido_cliente(request):
    try:
        # Puxa o cliente vinculado ao usuário logado
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        messages.error(request, 'Seu usuário não possui um perfil de cliente vinculado.')
        return redirect('home')

    # Dados iniciais baseados nas preferências do cliente
    initial_data = {
        'frete_option': cliente.frete_preferencia,
        'nota_fiscal': cliente.nota_fiscal_preferencia,
        'observacao_preferencia': cliente.observacao_preferencia,
    }

    if request.method == 'POST':
        form = UploadPedidoForm(request.POST, request.FILES)
        # Filtra os endereços apenas para o cliente logado
        form.fields['endereco_selecionado'].queryset = Endereco.objects.filter(cliente=cliente)

        if form.is_valid():
            try:
                planilha_pedido = request.FILES.get('planilha_pedido')
                if not planilha_pedido:
                    messages.error(request, 'Nenhum arquivo foi selecionado.')
                    return redirect('upload_pedido_cliente')
                
                # 1. Leitura do arquivo (Excel ou CSV)
                if planilha_pedido.name.endswith('.csv'):
                    df_list = [pd.read_csv(planilha_pedido)]
                else:
                    xls_data = pd.read_excel(planilha_pedido, sheet_name=None)
                    df_list = list(xls_data.values())
                
                df_completo = pd.concat(df_list, ignore_index=True)
                df = df_completo.dropna(how='all') 

                if df.empty:
                    messages.error(request, 'A planilha está vazia.')
                    return redirect('upload_pedido_cliente')

                # 2. Normalização e Mapeamento de Colunas
                df.columns = [normalize_text(col) for col in df.columns]
                
                expected_cols = {
                    'codigo': ['codigo', 'código', 'cod'],
                    'quantidade': ['quantidade', 'qtd', 'qtde'],
                    'descricao': ['descricao', 'descrição', 'produto', 'nome', 'description']
                }
                
                col_mapping = {
                    key: next((c for c in values if c in df.columns), None)
                    for key, values in expected_cols.items()
                }

                if not col_mapping['codigo'] or not col_mapping['quantidade']:
                    messages.error(request, "A planilha deve ter colunas para 'código' e 'quantidade'.")
                    return render(request, 'upload_pedido_cliente.html', {'upload_form': form, 'cliente': cliente})

                with transaction.atomic():
                    # 3. Criação do Pedido Rascunho
                    novo_pedido = Pedido.objects.create(
                        cliente=cliente,
                        endereco=form.cleaned_data.get('endereco_selecionado'),
                        data_criacao=timezone.now(),
                        data_envio_solicitada=form.cleaned_data['data_expedicao'],
                        frete_option=form.cleaned_data['frete_option'],
                        nota_fiscal=form.cleaned_data['nota_fiscal'],
                        status='RASCUNHO',
                        criado_por=request.user,
                        observacao=form.cleaned_data['observacao_preferencia'],
                    )
                    
                    erros_texto = []
                    itens_pedido_para_criar = []
                    itens_ignorados_db = []
                    total_valor_pedido = Decimal('0.0')

                    # Otimização: Busca produtos em lote
                    latest_dates = Product.objects.filter(product_code=OuterRef('product_code')).order_by('-date_product').values('date_product')[:1]
                    produtos_atuais = Product.objects.filter(date_product=Subquery(latest_dates)).in_bulk(field_name='product_code')

                    # 4. Processamento linha a linha
                    for index, row in df.iterrows():
                        codigo_raw = row[col_mapping['codigo']]
                        if pd.isna(codigo_raw): continue
                             
                        codigo_produto = str(codigo_raw).strip()

                        # Filtro de rodapé
                        termos_ignorar = ['TOTAL', 'SUBTOTAL', 'GERAL', 'VALOR TOTAL']
                        if any(termo in codigo_produto.upper() for termo in termos_ignorar):
                            continue

                        quantidade_raw = row[col_mapping['quantidade']]
                        descricao_excel = row.get(col_mapping.get('descricao'), 'Descrição não informada')
                        
                        if pd.isnull(quantidade_raw): continue

                        # Validação: Quantidade Numérica
                        try:
                            quantidade = int(quantidade_raw)
                        except ValueError:
                            msg = "Quantidade inválida (não-numérica)"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido, cliente=cliente, codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel), quantidade_tentada=0, motivo_erro=msg
                            ))
                            continue

                        # Validação: Quantidade Positiva
                        if quantidade <= 0:
                            msg = "Quantidade zero ou negativa"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido, cliente=cliente, codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel), quantidade_tentada=quantidade, motivo_erro=msg
                            ))
                            continue

                        # Validação: Catálogo
                        produto = produtos_atuais.get(codigo_produto)
                        if not produto:
                            msg = "Não encontrado no catálogo"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido, cliente=cliente, codigo_produto=codigo_produto,
                                descricao_produto=str(descricao_excel), quantidade_tentada=quantidade, motivo_erro=msg
                            ))
                            continue
                            
                        # Validação: Preço por Região (SP ou ES)
                        regiao = cliente.client_state.uf_name
                        valor_field = 'product_value_sp' if regiao == 'SP' else 'product_value_es'
                        valor_unitario = getattr(produto, valor_field)
                        
                        if valor_unitario is None or valor_unitario <= 0:
                            msg = f"Indisponível no estoque"
                            erros_texto.append(f"Produto '{codigo_produto}' na linha {index + 2}: {msg}.")
                            itens_ignorados_db.append(ItemPedidoIgnorado(
                                pedido=novo_pedido, cliente=cliente, codigo_produto=codigo_produto,
                                descricao_produto=produto.product_description, quantidade_tentada=quantidade, motivo_erro=msg
                            ))
                            continue

                        # Sucesso: Prepara para criar
                        total_valor_pedido += valor_unitario * Decimal(quantidade)
                        itens_pedido_para_criar.append(ItemPedido(
                            pedido=novo_pedido,
                            produto=produto,
                            quantidade=quantidade,
                            valor_unitario_sp=produto.product_value_sp,
                            valor_unitario_es=produto.product_value_es,
                        ))
                    
                    # 5. Finalização
                    if not itens_pedido_para_criar and not itens_ignorados_db:
                        messages.error(request, "Nenhum dado processável encontrado.")
                        novo_pedido.delete()
                        return redirect('upload_pedido_cliente')
                    
                    if itens_pedido_para_criar:
                        ItemPedido.objects.bulk_create(itens_pedido_para_criar)
                    
                    if itens_ignorados_db:
                        ItemPedidoIgnorado.objects.bulk_create(itens_ignorados_db)
                    
                    if erros_texto:
                        novo_pedido.erros_upload = '\n'.join(erros_texto)
                        erros_msg = 'Alguns itens foram ignorados:\n' + '\n'.join(erros_texto[:3])
                        if len(erros_texto) > 3: erros_msg += f'\n... e mais {len(erros_texto) - 3} erros.'
                        messages.warning(request, erros_msg)
                    else:
                        messages.success(request, "Itens carregados com sucesso!")
                    
                    novo_pedido.valor_total = total_valor_pedido
                    novo_pedido.save()
                    
                    return redirect('checkout_rascunho', pedido_id_rascunho=novo_pedido.id)
            
            except Exception as e:
                messages.error(request, f"Erro crítico no processamento: {e}")
                if 'novo_pedido' in locals(): novo_pedido.delete()
        
    else:
        # GET: Prepara formulário com endereços do cliente e sugestão de endereço padrão
        form = UploadPedidoForm(initial=initial_data)
        form.fields['endereco_selecionado'].queryset = Endereco.objects.filter(cliente=cliente)
        end_padrao = Endereco.objects.filter(cliente=cliente, is_default=True).first()
        if end_padrao:
            form.initial['endereco_selecionado'] = end_padrao.id

    return render(request, 'upload_pedido_cliente.html', {'upload_form': form, 'cliente': cliente})