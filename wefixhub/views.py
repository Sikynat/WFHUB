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
from django.core.cache import cache
from django.db.models import Count, Sum, F, OuterRef, Subquery, DecimalField, ExpressionWrapper, Value 
from django.db.models.functions import TruncMonth, Coalesce, TruncDate
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from .models import VendaReal
from django.db.models.functions import TruncDay
import json
# Garanta que seus modelos estão importados
from .models import Pedido, ItemPedido, WfClient, ItemPedidoIgnorado
from django.shortcuts import render
from django.db.models import Sum
from .models import VendaReal
from decimal import Decimal
import json
import calendar
from datetime import date
from .models import StatusPedidoERP
import pdfplumber
import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Carrinho, ItemCarrinho

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
    # 1. Parâmetros de Filtro e Busca
    codigo = request.GET.get('codigo', None)
    descricao = request.GET.get('descricao', None)
    grupo = request.GET.get('grupo', None)
    marca = request.GET.get('marca', None)
    pedidos_rascunho_count = Pedido.objects.filter(status='RASCUNHO').count()

    # 2. Obter o registro mais recente para cada produto (Otimização de Subquery)
    latest_dates = Product.objects.filter(
        product_code=OuterRef('product_code')
    ).order_by('-date_product').values('date_product')[:1]

    products = Product.objects.filter(
        date_product=Subquery(latest_dates)
    ).order_by('product_code')

    # 3. Aplicação dos Filtros de Busca
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
    itens_frequentes = [] 
    produtos_wishlist_cliente = [] 
    total_carrinho_real = Decimal('0.00') # Inicializa o total como zero

    # 4. Lógica de Preços, Recomendações, WISHLIST e SINCRONIZAÇÃO DE CARRINHO
    if request.user.is_authenticated:
        if request.user.is_staff:
            preco_exibido = 'todos'
        else:
            try:
                cliente_logado = request.user.wfclient
                itens_frequentes = cliente_logado.get_frequent_items(limit=6)
                estado_cliente = cliente_logado.client_state.uf_name
                
                if estado_cliente == 'SP':
                    preco_exibido = 'sp'
                    products = products.exclude(product_value_sp=0)
                elif estado_cliente == 'ES':
                    preco_exibido = 'es'
                    products = products.exclude(product_value_es=0)

                # --- SINCRONIZAÇÃO DO TOTAL DO CARRINHO (NOVO) ---
                # Importação local para evitar importação circular no topo do arquivo
                from .models import Carrinho 
                carrinho = Carrinho.objects.filter(cliente=cliente_logado).first()
                if carrinho:
                    total_carrinho_real = carrinho.get_total_carrinho()

                # --- ALERTA DE WISHLIST NO FRONT-END ---
                data_limite = timezone.localdate() - timedelta(days=30)
                itens_pendentes = ItemPedidoIgnorado.objects.filter(
                    cliente=cliente_logado,
                    notificado=False,
                    motivo_erro__icontains="estoque",
                    data_tentativa__gte=data_limite
                )

                if itens_pendentes.exists():
                    codigos_pendentes = itens_pendentes.values_list('codigo_produto', flat=True).distinct()
                    produtos_dict = {p.product_code: p for p in Product.objects.filter(product_code__in=codigos_pendentes)}

                    for item in itens_pendentes:
                        produto = produtos_dict.get(item.codigo_produto)
                        if not produto: continue

                        preco_atual = getattr(produto, 'product_value_sp' if estado_cliente == 'SP' else 'product_value_es')
                        
                        if preco_atual and preco_atual > 0:
                            if not any(p['codigo'] == produto.product_code for p in produtos_wishlist_cliente):
                                produtos_wishlist_cliente.append({
                                    'codigo': produto.product_code,
                                    'descricao': produto.product_description,
                                    'preco': f"{preco_atual.quantize(Decimal('0.01'))}".replace('.', ',')
                                })

            except WfClient.DoesNotExist:
                products = Product.objects.none()
    
    if not request.user.is_authenticated:
        products = Product.objects.none()
    
    # 5. Formatação de Valores para Exibição
    for product in products:
        product.valor_sp_formatado = f"{product.product_value_sp.quantize(Decimal('0.01'))}".replace('.', ',') if product.product_value_sp else "0,00"
        product.valor_es_formatado = f"{product.product_value_es.quantize(Decimal('0.01'))}".replace('.', ',') if product.product_value_es else "0,00"
    
    # 6. Paginação
    paginator = Paginator(products, 30)
    page = request.GET.get('page')

    try:
        product_list = paginator.page(page)
    except PageNotAnInteger:
        product_list = paginator.page(1)
    except EmptyPage:
        product_list = paginator.page(paginator.num_pages)
        
    # 7. Contexto do Template
    context = {
        'product_list': product_list,
        'itens_frequentes': itens_frequentes, 
        'produtos_wishlist_cliente': produtos_wishlist_cliente,
        'cliente_logado': cliente_logado,
        'preco_exibido': preco_exibido,
        'data_hoje': products[0].date_product if products else date.today(),
        'pedidos_rascunho_count': pedidos_rascunho_count,
        # INJETADO: Valor numérico puro para o data-attribute do HTML
        'total_carrinho_real': float(total_carrinho_real), 
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
    # 1. Identifica o cliente logado
    try:
        cliente_logado = request.user.wfclient
    except WfClient.DoesNotExist:
        messages.error(request, "Cliente não encontrado.")
        return redirect('home')

    # 2. Busca o carrinho do banco de dados
    carrinho_obj = Carrinho.objects.filter(cliente=cliente_logado).first()
    
    itens_carrinho = []
    total_carrinho = Decimal('0.00')

    # 3. Se existir um carrinho, pega os itens
    if carrinho_obj:
        # Pega o estado para definir qual preço mostrar (SP ou ES)
        uf_cliente = cliente_logado.client_state.uf_name if cliente_logado.client_state else 'SP'
        
        # Otimização: select_related traz o Produto junto, evitando consultas extras ao banco
        itens_db = carrinho_obj.itens.select_related('produto').all()
        
        for item in itens_db:
            preco_unitario = item.produto.product_value_sp if uf_cliente == 'SP' else item.produto.product_value_es
            preco_unitario = preco_unitario or Decimal('0.00')
            subtotal = preco_unitario * item.quantidade
            
            # Monta o dicionário para a tela (HTML) ler
            itens_carrinho.append({
                'item_id': item.id,
                'produto': item.produto,
                'quantidade': item.quantidade,
                'preco_unitario': preco_unitario,
                'subtotal': subtotal
            })
            total_carrinho += subtotal

    context = {
        'itens_carrinho': itens_carrinho,
        'total_carrinho': total_carrinho,
        'cliente_logado': cliente_logado,
    }
    
    return render(request, 'carrinho.html', context)


# Fim do carrinho


@login_required
def remover_item(request, product_id):
    """Remove um item específico do carrinho no Banco de Dados."""
    try:
        cliente_logado = request.user.wfclient
        # Deleta apenas o item especificado atrelado ao cliente logado
        ItemCarrinho.objects.filter(
            carrinho__cliente=cliente_logado, 
            produto__product_id=product_id
        ).delete()
        messages.success(request, "Item removido do carrinho.")
    except Exception as e:
        messages.error(request, f"Erro ao remover item: {e}")
        
    return redirect('carrinho')

@login_required
def limpar_carrinho(request):
    """Esvazia o carrinho no Banco de Dados."""
    try:
        # Apagar o Carrinho inteiro limpa todos os itens por causa do CASCADE
        Carrinho.objects.filter(cliente=request.user.wfclient).delete()
        messages.success(request, "Carrinho limpo com sucesso.")
    except Exception as e:
        messages.error(request, "Erro ao limpar o carrinho.")
        
    return redirect('carrinho')

@login_required
def atualizar_carrinho(request):
    """Atualiza as quantidades se o usuário digitar os números e clicar em 'Atualizar'."""
    if request.method == 'POST':
        try:
            cliente_logado = request.user.wfclient
            carrinho_obj = Carrinho.objects.filter(cliente=cliente_logado).first()
            
            if carrinho_obj:
                for key, value in request.POST.items():
                    # Procura pelos inputs de quantidade que nomeamos no HTML
                    if key.startswith('quantidade_'):
                        produto_id = key.split('_')[1]
                        nova_qtd = int(value)
                        
                        if nova_qtd > 0:
                            ItemCarrinho.objects.filter(
                                carrinho=carrinho_obj, 
                                produto__product_id=produto_id
                            ).update(quantidade=nova_qtd)
                        else:
                            # Se ele botar zero, deleta o item
                            ItemCarrinho.objects.filter(
                                carrinho=carrinho_obj, 
                                produto__product_id=produto_id
                            ).delete()
                            
                messages.success(request, "Carrinho atualizado com sucesso!")
        except Exception as e:
            messages.error(request, "Erro ao atualizar o carrinho.")
            
    return redirect('carrinho')


# Inicio Checkout





# views.py

# ... (seus outros imports)

# --- SUBSTITUA A VIEW CHECKOUT EXISTENTE POR ESTA VERSÃO OTIMIZADA ---

@login_required
def checkout(request, pedido_id_rascunho=None):
    if request.method == 'POST':
        endereco_id = request.POST.get('endereco_selecionado')
        data_envio_str = request.POST.get('data_expedicao')
        frete_option = request.POST.get('frete_option')
        nota_fiscal = request.POST.get('nota_fiscal')
        observacao = request.POST.get('observacao')

        id_do_pedido = pedido_id_rascunho or request.POST.get('pedido_id_rascunho')

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
                    return redirect('checkout')
                endereco_selecionado = get_object_or_404(Endereco, id=endereco_id, cliente=cliente_logado)
            
            if data_envio_str:
                data_envio_obj = datetime.strptime(data_envio_str, '%Y-%m-%d').date()
            
        except (WfClient.DoesNotExist, Endereco.DoesNotExist, ValueError) as e:
            messages.error(request, f'Dados inválidos: {e}')
            return redirect('home')

        with transaction.atomic():
            if id_do_pedido:
                # Fluxo de Atualização de Rascunho
                pedido_rascunho.endereco = endereco_selecionado
                pedido_rascunho.data_envio_solicitada = data_envio_obj
                pedido_rascunho.frete_option = frete_option
                pedido_rascunho.nota_fiscal = nota_fiscal
                pedido_rascunho.observacao = observacao
                pedido_rascunho.status = 'PENDENTE'
                
                # RECALCULA O TOTAL ANTES DE SALVAR O RASCUNHO FINALIZADO
                pedido_rascunho.valor_total = pedido_rascunho.get_total_geral()
                pedido_rascunho.save()
                pedido_final = pedido_rascunho
            else:
                # Fluxo de Criação de Novo Pedido (Carrinho Manual)
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
                
                # --- OTIMIZAÇÃO APLICADA: 1 SELECT IN (...) ---
                product_ids = [int(pid) for pid in carrinho_da_sessao.keys()]
                produtos_dict = Product.objects.in_bulk(product_ids, field_name='product_id')
                
                itens_para_criar = []
                for product_id_str, quantidade in carrinho_da_sessao.items():
                    product = produtos_dict.get(int(product_id_str))
                    if product:
                        # Prepara o objeto em memória (Não salva no banco ainda)
                        itens_para_criar.append(ItemPedido(
                            pedido=pedido,
                            produto=product,
                            quantidade=quantidade,
                            valor_unitario_sp=product.product_value_sp,
                            valor_unitario_es=product.product_value_es,
                        ))
                
                # --- OTIMIZAÇÃO APLICADA: 1 INSERT MÚLTIPLO ---
                if itens_para_criar:
                    ItemPedido.objects.bulk_create(itens_para_criar)
                
                # Calcula o total usando a função do model
                total_calculado = pedido.get_total_geral()
                
                # Salva o valor no banco de dados
                pedido.valor_total = total_calculado
                pedido.save()
                pedido_final = pedido
                
                if 'carrinho' in request.session:
                    del request.session['carrinho']

        messages.success(request, f'Pedido #{pedido_final.id} realizado com sucesso!')
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
        data_envio_str = request.POST.get('data_envio') # Renomeei para evitar conflito

        try:
            cliente = request.user.wfclient
            endereco_selecionado = Endereco.objects.get(id=endereco_id, cliente=cliente)
            data_envio = datetime.datetime.strptime(data_envio_str, '%Y-%m-%d').date()
            
            # Puxa o carrinho do cliente (ajuste conforme o nome da sua variável de sessão ou model)
            # Supondo que você use uma lógica de itens no banco ou sessão:
            itens_carrinho = Carrinho.objects.filter(cliente=cliente) # Exemplo

            with transaction.atomic():
                # 1. Cria o Pedido primeiro
                novo_pedido = Pedido.objects.create(
                    cliente=cliente,
                    endereco=endereco_selecionado,
                    data_envio_solicitada=data_envio,
                    status='RASCUNHO', # Ou o status inicial do seu sistema
                    criado_por=request.user,
                    # ... outros campos como frete_option, nota_fiscal ...
                )

                # 2. Cria os Itens do Pedido (Loop)
                for item in itens_carrinho:
                    ItemPedido.objects.create(
                        pedido=novo_pedido,
                        produto=item.produto,
                        quantidade=item.quantidade,
                        valor_unitario_sp=item.produto.product_value_sp,
                        valor_unitario_es=item.produto.product_value_es,
                    )

                # 3. AGORA SIM: Atualiza o total e salva de novo
                # O get_total_geral() vai somar os ItemPedido que acabamos de criar acima
                novo_pedido.valor_total = novo_pedido.get_total_geral()
                novo_pedido.save() 

                # 4. Limpa o carrinho após salvar
                itens_carrinho.delete()

            messages.success(request, 'Pedido realizado com sucesso!')
            return redirect('pedido_concluido') # Ou para a tela de checkout final

        except (Endereco.DoesNotExist, ValueError):
            messages.error(request, 'Endereço ou data de envio inválidos.')
            return redirect('checkout')
        except Exception as e:
            messages.error(request, f'Erro ao salvar pedido: {e}')
            return redirect('checkout')

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




from .models import VendaReal, Pedido, WfClient, ItemPedido # Certifique-se de importar VendaReal
from django.db.models import Sum
from decimal import Decimal
import locale

@staff_member_required
def dashboard_admin(request):
    filtro = request.GET.get('filtro')
    hoje = timezone.localdate()

    # =========================================================
    # 1. CÁLCULO DO FATURAMENTO REAL (CACHE: 15 MINUTOS)
    # =========================================================
    faturamento_formatado = cache.get('dashboard_faturamento')
    
    if not faturamento_formatado:
        total_faturamento_real = VendaReal.objects.aggregate(
            total=Sum('Total')
        )['total'] or Decimal('0.00')
        faturamento_formatado = "{:,.2f}".format(float(total_faturamento_real)).replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Salva na memória por 900 segundos (15 minutos)
        cache.set('dashboard_faturamento', faturamento_formatado, 900)

    # =========================================================
    # 2. MÉTRICAS DO SITE E STATUS ERP (CACHE: 5 MINUTOS)
    # =========================================================
    metricas = cache.get('dashboard_metricas')
    
    if not metricas:
        metricas = {
            'total_clientes': WfClient.objects.count(),
            'total_pedidos': Pedido.objects.count(),
            
            # (Mantidos por segurança caso você use no futuro)
            'pendentes': Pedido.objects.filter(status='PENDENTE').count(),
            'concluidos': Pedido.objects.filter(status='FINALIZADO').count(),
            'orcamento': Pedido.objects.filter(status='ORCAMENTO').count(),
            'adc': Pedido.objects.filter(status='FINANCEIRO').count(),
            'separacao': Pedido.objects.filter(status='SEPARACAO').count(),
            'expedicao': Pedido.objects.filter(status='EXPEDICAO').count(),
            'atrasados': Pedido.objects.filter(status='ATRASADO').count(),
            
            # --- NOVAS MÉTRICAS: STATUS DO ERP ---
            # ATENÇÃO: Se o nome do seu modelo não for StatusPedidoERP, troque aqui abaixo:
            'erp_total': StatusPedidoERP.objects.count(),
            'erp_credito': StatusPedidoERP.objects.filter(situacao__icontains='Crédito').count(),
            'erp_preco': StatusPedidoERP.objects.filter(situacao__icontains='Preço').count(),
            'erp_separacao': StatusPedidoERP.objects.filter(Q(situacao__icontains='Separação') | Q(situacao__icontains='Bloqueado')).count(),
            'erp_faturados': StatusPedidoERP.objects.filter(situacao__icontains='Faturado').count(),
            'erp_expedidos': StatusPedidoERP.objects.filter(expedido=True).count(),
        }
        # Salva na memória por 300 segundos (5 minutos)
        cache.set('dashboard_metricas', metricas, 300)
    
    # =========================================================
    # 3. FILTRAGEM DE PEDIDOS (SEM CACHE - TEMPO REAL)
    # =========================================================
    if filtro == 'sincronizados':
        status_erp = ['SEPARACAO', 'EXPEDICAO', 'FINALIZADO']
        pedidos_qs = Pedido.objects.filter(
            status__in=status_erp, 
            data_criacao__date=hoje
        ).order_by('-data_criacao')[:20]
    else:
        pedidos_qs = Pedido.objects.all().order_by('-data_criacao')[:5]
    
    pedidos_com_total = []
    for pedido in pedidos_qs:
        total_pedido = float(pedido.get_total_geral() or 0)
        total_p_formatado = "{:,.2f}".format(total_pedido).replace(",", "X").replace(".", ",").replace("X", ".")
        
        pedidos_com_total.append({
            'id': pedido.id,
            'cliente': pedido.cliente,
            'data_criacao': pedido.data_criacao,
            'status': pedido.status,
            'status_display': pedido.get_status_display(),
            'total_str': total_p_formatado,
            'is_sincronizado': filtro == 'sincronizados'
        })

    # =========================================================
    # 4. OPORTUNIDADES DE RETORNO (WISHLIST) (CACHE: 15 MINUTOS)
    # =========================================================
    oportunidades_wishlist_cache = cache.get('dashboard_wishlist')
    
    # Usamos "is None" porque a lista de cache pode estar propositalmente vazia []
    if oportunidades_wishlist_cache is None:
        data_limite = hoje - timedelta(days=30)
        itens_pendentes = ItemPedidoIgnorado.objects.filter(
            notificado=False, 
            motivo_erro__icontains="estoque",
            data_tentativa__gte=data_limite
        ).select_related('cliente', 'cliente__client_state')

        oportunidades_wishlist = {}
        codigos_pendentes = itens_pendentes.values_list('codigo_produto', flat=True).distinct()
        produtos_dict = {p.product_code: p for p in Product.objects.filter(product_code__in=codigos_pendentes)}

        for item in itens_pendentes:
            produto = produtos_dict.get(item.codigo_produto)
            if not produto or not item.cliente:
                continue
                
            estado = item.cliente.client_state.uf_name
            preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
            
            if preco_atual and preco_atual > 0:
                c_id = item.cliente.client_id
                if c_id not in oportunidades_wishlist:
                    oportunidades_wishlist[c_id] = {
                        'cliente': item.cliente,
                        'produtos': []
                    }
                if produto.product_description not in [p['descricao'] for p in oportunidades_wishlist[c_id]['produtos']]:
                    oportunidades_wishlist[c_id]['produtos'].append({
                        'codigo': produto.product_code,
                        'descricao': produto.product_description,
                        'preco': float(preco_atual)
                    })
        
        # Converte o dicionário em lista para facilitar a renderização e o cache
        oportunidades_wishlist_cache = list(oportunidades_wishlist.values())
        cache.set('dashboard_wishlist', oportunidades_wishlist_cache, 900)

    # --- CONTEXTO ---
    contexto = {
        'titulo': 'Dashboard Administrativo',
        'total_clientes': metricas['total_clientes'],
        'total_pedidos': metricas['total_pedidos'],
        'total_vendas': faturamento_formatado,
        'pedidos_recentes': pedidos_com_total,
        
        # Enviando os novos números do ERP para a tela HTML
        'erp_total': metricas['erp_total'],
        'erp_credito': metricas['erp_credito'],
        'erp_preco': metricas['erp_preco'],
        'erp_separacao': metricas['erp_separacao'],
        'erp_faturados': metricas['erp_faturados'],
        'erp_expedidos': metricas['erp_expedidos'],
        
        'filtro_ativo': filtro,
        'oportunidades_wishlist': oportunidades_wishlist_cache, 
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
            # 1. Leitura Dinâmica (Lê tudo como texto inicialmente para evitar quebras)
            df_es_raw = pd.read_excel(planilha_es_file, dtype=str)
            df_sp_raw = pd.read_excel(planilha_sp_file, dtype=str)

            # 2. Mapeamento Inteligente de Colunas (Apelidos)
            # O sistema vai procurar por qualquer uma destas palavras no cabeçalho
            aliases = {
                'codigo': ['CÓDIGO', 'CODIGO', 'PRODUTO', 'COD'],
                'descricao': ['DESCRIÇÃO', 'DESCRICAO', 'NOME DO PRODUTO'],
                'grupo': ['GRUPO', 'CATEGORIA'],
                'marca': ['MARCA', 'FABRICANTE'],
                'tabela': ['TABELA', 'PREÇO NOVO', 'PRECO', 'VALOR']
            }

            def encontrar_coluna(df, nomes_possiveis):
                for nome in nomes_possiveis:
                    if nome in df.columns:
                        return nome
                return None

            # Processa as colunas da Planilha ES
            col_cod_es = encontrar_coluna(df_es_raw, aliases['codigo'])
            col_tab_es = encontrar_coluna(df_es_raw, aliases['tabela'])
            
            # Processa as colunas da Planilha SP
            col_cod_sp = encontrar_coluna(df_sp_raw, aliases['codigo'])
            col_tab_sp = encontrar_coluna(df_sp_raw, aliases['tabela'])

            # Validação: Se não achar Código e Preço, avisa o usuário sem dar Erro 500
            if not col_cod_es or not col_tab_es:
                messages.error(request, 'Planilha ES inválida: É obrigatório ter as colunas de "Código/Produto" e "Tabela/Preço".')
                return redirect('pagina_upload')
            if not col_cod_sp or not col_tab_sp:
                messages.error(request, 'Planilha SP inválida: É obrigatório ter as colunas de "Código/Produto" e "Tabela/Preço".')
                return redirect('pagina_upload')

            # 3. Montagem dos DataFrames limpos
            # ES
            df_es = pd.DataFrame()
            df_es['product_code'] = df_es_raw[col_cod_es].str.strip()
            df_es['product_value_es'] = pd.to_numeric(df_es_raw[col_tab_es].str.replace(',', '.'), errors='coerce').fillna(0)
            
            col_desc = encontrar_coluna(df_es_raw, aliases['descricao'])
            col_grupo = encontrar_coluna(df_es_raw, aliases['grupo'])
            col_marca = encontrar_coluna(df_es_raw, aliases['marca'])
            
            if col_desc: df_es['product_description'] = df_es_raw[col_desc].str.strip()
            if col_grupo: df_es['product_group'] = df_es_raw[col_grupo].str.strip()
            if col_marca: df_es['product_brand'] = df_es_raw[col_marca].str.strip()

            # SP
            df_sp = pd.DataFrame()
            df_sp['product_code'] = df_sp_raw[col_cod_sp].str.strip()
            df_sp['product_value_sp'] = pd.to_numeric(df_sp_raw[col_tab_sp].str.replace(',', '.'), errors='coerce').fillna(0)

            # 4. Merge das planilhas (how='outer' garante que não perca itens que só estão em uma planilha)
            df_final = pd.merge(df_es, df_sp, on='product_code', how='outer')
            df_final = df_final.replace({np.nan: None})
            df_final = df_final.drop_duplicates(subset=['product_code'])
            
            # Remove linhas vazias/lixo da planilha
            df_final = df_final[df_final['product_code'].notnull()]
            df_final = df_final[df_final['product_code'] != ""]

            # --- 5. OTIMIZAÇÃO DE BANCO E PREVENÇÃO DE PERDA DE DADOS ---
            codigos_na_planilha = df_final['product_code'].tolist()
            hoje = date.today()
            
            produtos_existentes = {
                p.product_code: p for p in Product.objects.filter(product_code__in=codigos_na_planilha)
            }

            produtos_para_criar = []
            produtos_para_atualizar = []

            for _, row in df_final.iterrows():
                codigo = str(row['product_code']).strip()
                
                # Extração segura dos dados
                desc_planilha = row.get('product_description')
                grupo_planilha = row.get('product_group')
                marca_planilha = row.get('product_brand')
                
                val_es = row.get('product_value_es', 0)
                val_sp = row.get('product_value_sp', 0)

                if codigo in produtos_existentes:
                    obj = produtos_existentes[codigo]
                    
                    # ATUALIZAÇÃO CONDICIONAL: Só atualiza se a célula da planilha não for nula/vazia
                    if desc_planilha and str(desc_planilha).strip().lower() not in ['nan', 'none', '']:
                        obj.product_description = str(desc_planilha).strip()[:255]
                    
                    if grupo_planilha and str(grupo_planilha).strip().lower() not in ['nan', 'none', '']:
                        obj.product_group = str(grupo_planilha).strip()[:100]
                    
                    if marca_planilha and str(marca_planilha).strip().lower() not in ['nan', 'none', '']:
                        obj.product_brand = str(marca_planilha).strip()[:100]
                    
                    # Atualização de preços (se a planilha não tiver, mantém o 0 que foi tratado no fillna)
                    if val_sp is not None: obj.product_value_sp = val_sp
                    if val_es is not None: obj.product_value_es = val_es
                    
                    obj.status = 'PENDENTE'
                    obj.date_product = hoje
                    
                    produtos_para_atualizar.append(obj)
                else:
                    # Criação de um produto novo
                    produtos_para_criar.append(Product(
                        product_code=codigo,
                        product_description=str(desc_planilha).strip()[:255] if desc_planilha and str(desc_planilha).strip().lower() not in ['nan', 'none', ''] else "",
                        product_group=str(grupo_planilha).strip()[:100] if grupo_planilha and str(grupo_planilha).strip().lower() not in ['nan', 'none', ''] else "",
                        product_brand=str(marca_planilha).strip()[:100] if marca_planilha and str(marca_planilha).strip().lower() not in ['nan', 'none', ''] else "",
                        product_value_sp=val_sp if val_sp is not None else 0,
                        product_value_es=val_es if val_es is not None else 0,
                        status='PENDENTE',
                        date_product=hoje
                    ))

            # 6. Gravação Atômica e em Massa
            with transaction.atomic():
                if produtos_para_criar:
                    Product.objects.bulk_create(produtos_para_criar, batch_size=500)
                
                if produtos_para_atualizar:
                    # Informa exatamente quais campos devem ser tocados
                    Product.objects.bulk_update(
                        produtos_para_atualizar, 
                        fields=['product_description', 'product_group', 'product_brand', 'product_value_sp', 'product_value_es', 'status', 'date_product'],
                        batch_size=500
                    )
            
            messages.success(request, f'Processamento concluído: {len(produtos_para_criar)} novos e {len(produtos_para_atualizar)} atualizados.')
            return redirect('pagina_upload')

        except Exception as e:
            messages.error(request, f'Erro crítico no processamento: {e}')
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
  
    # 1. Lógica de Limpeza (DEVE vir antes de qualquer outra coisa)
    if 'limpar' in request.GET:
        cliente_id = request.GET.get('cliente')
        # Redireciona para a mesma página apenas com o ID do cliente, limpando os filtros
        return redirect(f"{reverse('gerar_pedido_manual')}?cliente={cliente_id}")

    cliente_selecionado = None
    # Usamos request.GET para manter o estado do formulário de seleção de cliente
    form_cliente = SelectClientForm(request.GET or None)
    product_list = []
    query_params = request.GET.copy()
    preco_exibido = 'todos'
    initial_data = {}

    # Remove o parâmetro de página para não quebrar os filtros de busca
    if 'page' in query_params:
        query_params.pop('page')

    # 2. Identificação do Cliente
    # Tentamos pegar o cliente tanto pelo form quanto direto pelo GET (para o redirecionamento do 'limpar')
    cliente_id_get = request.GET.get('cliente')
    
    if form_cliente.is_valid() and form_cliente.cleaned_data.get('cliente'):
        cliente_selecionado = form_cliente.cleaned_data['cliente']
    elif cliente_id_get:
        cliente_selecionado = get_object_or_404(WfClient, pk=cliente_id_get)
        # Atualiza o form para mostrar o cliente correto no select
        form_cliente = SelectClientForm(initial={'cliente': cliente_selecionado})

    context = {
        'form_cliente': form_cliente,
        'cliente_selecionado': cliente_selecionado,
        'initial_data': initial_data,
        'query_params': query_params,
        'preco_exibido': preco_exibido,
    }
    
    # 3. Processamento de Produtos se houver cliente
    if cliente_selecionado:
        # Preferências do Cliente
        initial_data['frete_preferencia'] = cliente_selecionado.frete_preferencia
        initial_data['nota_fiscal_preferencia'] = cliente_selecionado.nota_fiscal_preferencia
        
        endereco_padrao = Endereco.objects.filter(cliente=cliente_selecionado, is_default=True).first()
        if endereco_padrao:
            initial_data['endereco_padrao_id'] = endereco_padrao.id

        enderecos_do_cliente = Endereco.objects.filter(cliente=cliente_selecionado)
        
        # Filtros de Produtos
        hoje = timezone.localdate()
        products = Product.objects.filter(date_product=hoje).order_by('product_code')

        # Captura dos filtros do GET
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
        
        # Lógica de Preço baseada no Estado
        estado_cliente = cliente_selecionado.client_state.uf_name.upper()
        preco_exibido = estado_cliente.lower()

        # Formatação de valores
        for product in products:
            if estado_cliente == 'SP':
                if product.product_value_sp:
                    product.valor_sp_formatado = f"R$ {product.product_value_sp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    product.valor_sp_formatado = "N/A"
            elif estado_cliente == 'ES':
                if product.product_value_es:
                    product.valor_es_formatado = f"R$ {product.product_value_es:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    product.valor_es_formatado = "N/A"
            
        # Paginação
        paginator = Paginator(products, 30)
        page_number = request.GET.get('page')
        product_list = paginator.get_page(page_number)

        context.update({
            'enderecos': enderecos_do_cliente,
            'preco_exibido': preco_exibido,
            'product_list': product_list,
            'initial_data': initial_data,
        })
    
    return render(request, 'gerar_pedido_manual.html', context)

# --- SUBSTITUA A VIEW PROCESSAR_PEDIDO_MANUAL EXISTENTE POR ESTA VERSÃO OTIMIZADA ---

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
        observacao = request.POST.get('observacao')
        
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
                    observacao=observacao
                )
                
                # --- OTIMIZAÇÃO APLICADA: 1 SELECT IN (...) ---
                product_ids = [int(pid) for pid in cart_data.keys()]
                produtos_dict = Product.objects.in_bulk(product_ids, field_name='product_id')
                
                itens_para_criar = []
                estado_cliente = cliente_selecionado.client_state.uf_name

                for product_id_str, quantidade in cart_data.items():
                    produto = produtos_dict.get(int(product_id_str))
                    
                    if not produto:
                        messages.warning(request, f'Produto com ID {product_id_str} não encontrado e foi ignorado.')
                        continue
                    
                    # Lógica para salvar o valor no campo correto e manter o outro nulo
                    if estado_cliente == 'SP':
                        val_sp = produto.product_value_sp
                        val_es = None
                    elif estado_cliente == 'ES':
                        val_sp = None
                        val_es = produto.product_value_es
                    else:
                        messages.warning(request, f'Produto {produto.product_code} não pôde ser adicionado. Estado inválido.')
                        continue

                    itens_para_criar.append(ItemPedido(
                        pedido=pedido_criado,
                        produto=produto,
                        quantidade=quantidade,
                        valor_unitario_sp=val_sp,
                        valor_unitario_es=val_es
                    ))

                # --- OTIMIZAÇÃO APLICADA: 1 INSERT MÚLTIPLO ---
                if itens_para_criar:
                    ItemPedido.objects.bulk_create(itens_para_criar)

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
            messages.error(request, f'Dados inválidos. Erro: {e}')
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


''' Função original
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
        f"*Valor total:* R${pedido.valor_total:,.2f}\n"
        f"*OBS:* {pedido.observacao}\n\n"
        f"*Download da Planilha de Itens:*\n" 
        f"{link_download_excel}"  # <- MUDANÇA AQUI: usando o link direto
    )

    # Codifica a mensagem para a URL do WhatsApp (lógica inalterada)
    link_whatsapp = f"https://wa.me/5516991273974?text={quote(mensagem_final)}"

    return redirect(link_whatsapp)
'''


@staff_member_required
def enviar_whatsapp(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # 1. Link para a nova planilha simplificada (Cód, Qtd, Preço)
    link_download_excel = request.build_absolute_uri(
        reverse('exportar_detalhes_pedido_whatsapp_excel', args=[pedido.id])
    )

    # 2. Construção da mensagem formatada conforme seu exemplo
    mensagem_corpo = (
        f"*Dados do Pedido*\n\n"
        f"*Codigo Interno:* {pedido.id}\n"
        f"*Código do Cliente:* {pedido.cliente.client_code}\n"
        f"*Razão Social:* {pedido.cliente.client_name}\n"
        f"*Data da Expedição:* {pedido.data_envio_solicitada.strftime('%d/%m/%Y')}\n"
        f"*Opção de Frete:* {pedido.get_frete_option_display()}\n"
    )

    # 3. Lógica de Endereço (apenas se houver frete que exija entrega)
    fretes_com_endereco = ['SEDEX', 'CORREIOS', 'TRANSPORTADORA']
    if pedido.frete_option in fretes_com_endereco and pedido.endereco:
        end = pedido.endereco
        mensagem_corpo += (
            f"*Endereço de Entrega:* {end.logradouro}, {end.bairro}, {end.numero} "
            f"{end.cidade} - {end.estado} (CEP: {end.cep})\n"
        )

    # 4. Adicionando Nota Fiscal, Valor Total e OBS
    mensagem_final = (
        f"{mensagem_corpo}"
        f"*Opção de Nota Fiscal:* {pedido.get_nota_fiscal_display()}\n" # <-- AQUI A NOTA FISCAL
        f"*Valor total:* R$ {pedido.valor_total:,.2f}\n".replace(",", "X").replace(".", ",").replace("X", ".") +
        f"*OBS:* {pedido.observacao}\n\n"
        f"*Link para Digitação (Planilha):*\n"
        f"{link_download_excel}"
    )

    # 5. Codifica e Redireciona
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


@staff_member_required
def analise_dados_dashboard(request):
    # --- 1. Definição de Período ---
    periodo_geral_solicitado = 'periodo_geral' in request.GET
    data_fim_str = request.GET.get('data_fim')
    data_inicio_str = request.GET.get('data_inicio')
    
    def parse_date(date_str, default):
        if not date_str: return default
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try: return datetime.strptime(date_str, fmt).date()
            except ValueError: continue
        return default

    data_fim = timezone.localdate() if not data_fim_str or periodo_geral_solicitado else parse_date(data_fim_str, timezone.localdate())
    data_inicio = datetime(2000, 1, 1).date() if periodo_geral_solicitado else parse_date(data_inicio_str, data_fim - timedelta(days=90))

    # --- 2. FATURAMENTO REAL ERP (VendaReal) ---
    # Aqui corrigimos o erro dos 915k aplicando o exclude de segurança
    vendas_erp_qs = VendaReal.objects.exclude(Produto_Codigo__icontains='TOTAL')
    
    if not periodo_geral_solicitado:
        vendas_erp_qs = vendas_erp_qs.filter(Emissao__range=(data_inicio, data_fim))
    
    total_faturamento_erp = vendas_erp_qs.aggregate(total=Sum('Total'))['total'] or Decimal('0.00')

    # --- 3. Sugestões ERP para Cliente Específico ---
    cliente_id_analise = request.GET.get('cliente')
    sugestoes_erp = []
    lista_clientes_filtro = WfClient.objects.only('client_id', 'client_name').order_by('client_name')

    if cliente_id_analise:
        try:
            cliente_obj = WfClient.objects.get(pk=cliente_id_analise)
            sugestoes_erp = VendaReal.objects.filter(
                Codigo_Cliente=cliente_obj.client_code
            ).exclude(Produto_Codigo__icontains='TOTAL').values(
                'Produto_Codigo', 'Produto_Descricao'
            ).annotate(
                total_qtd=Sum('Quantidade'),
                vezes_faturado=Count('id')
            ).order_by('-total_qtd')[:10]
        except WfClient.DoesNotExist:
            pass

    # --- 4. QuerySet Base do SITE (ItemPedido) ---
    CAMPO_DATA_FILTRO = 'pedido__data_envio_solicitada'
    base_queryset = ItemPedido.objects.select_related(
        'pedido', 'pedido__cliente', 'produto', 'pedido__cliente__client_state'
    ).exclude(pedido__status='CANCELADO')

    if not periodo_geral_solicitado:
        itens_filtrados = base_queryset.filter(
            **{f"{CAMPO_DATA_FILTRO}__gte": data_inicio, f"{CAMPO_DATA_FILTRO}__lte": data_fim}
        ).exclude(**{f"{CAMPO_DATA_FILTRO}__isnull": True})
    else:
        itens_filtrados = base_queryset

    # Anotação de valores do site
    valor_unit_pref = Coalesce(F('valor_unitario_sp'), F('valor_unitario_es'), Value(0, output_field=DecimalField()))
    itens_filtrados = itens_filtrados.annotate(
        valor_total_item=ExpressionWrapper(F('quantidade') * valor_unit_pref, output_field=DecimalField())
    )

    # --- 5. Rankings e Agregações ---
    # Totais do Site
    totais_site = itens_filtrados.aggregate(
        total_periodo=Sum('valor_total_item'),
        total_sp=Sum('valor_total_item', filter=Q(pedido__cliente__client_state__uf_name='SP')),
        total_es=Sum('valor_total_item', filter=Q(pedido__cliente__client_state__uf_name='ES'))
    )

    # NOVO: Produtos Mais Vendidos (Recuperado)
    produtos_top = itens_filtrados.values(
        'produto__product_code', 'produto__product_description'
    ).annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido')[:10]

    def get_top_clients(uf):
        return list(itens_filtrados.filter(pedido__cliente__client_state__uf_name=uf)
            .values('pedido__cliente__client_id', 'pedido__cliente__client_name', 'pedido__cliente__client_code')
            .annotate(total_gasto=Sum('valor_total_item'), num_pedidos=Count('pedido__id', distinct=True))
            .order_by('-total_gasto')[:5])

    # --- 6. Vendas por Mês (Recuperado) ---
    vendas_por_mes = itens_filtrados.annotate(
        mes_ano=TruncMonth(CAMPO_DATA_FILTRO)
    ).values('mes_ano').annotate(total_vendas=Sum('valor_total_item')).order_by('mes_ano')

    contexto = {
        'titulo': 'Dashboard de Análise de Dados',
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'total_faturamento_erp': total_faturamento_erp,  # VALOR REAL ERP (914k corrigido)
        'total_vendas_periodo_calculado': totais_site['total_periodo'] or 0, # VALOR SITE
        'total_vendas_sp_clientes': totais_site['total_sp'] or 0,
        'total_vendas_es_clientes': totais_site['total_es'] or 0,
        'clientes_top_sp': get_top_clients('SP'),
        'clientes_top_es': get_top_clients('ES'),
        'produtos_top': produtos_top,  # Ranking de produtos recuperado
        'vendas_por_mes': vendas_por_mes,
        'sugestoes_erp': sugestoes_erp,
        'lista_clientes_filtro': lista_clientes_filtro,
        'cliente_selecionado_id': cliente_id_analise,
        'periodo_geral_ativo': periodo_geral_solicitado,
    }
    return render(request, 'analise/analise_dashboard.html', contexto)



@login_required
def upload_pedido_cliente(request):
    try:
        # Puxa o cliente vinculado ao usuário logado
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        messages.error(request, 'Seu usuário não possui um perfil de cliente vinculado.')
        return redirect('home')
    
    codigo_cliente_analise = request.GET.get('cliente_codigo') # Exemplo

    sugestoes_erp = []
    if codigo_cliente_analise:
        sugestoes_erp = VendaReal.objects.filter(
            Codigo_Cliente=codigo_cliente_analise
        ).values(
            'Produto_Codigo', 'Produto_Descricao'
        ).annotate(
            total_qtd=Sum('Quantidade'),
            vezes_faturado=Count('id')
        ).order_by('-total_qtd')[:10]

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



def exportar_detalhes_pedido_whatsapp_excel(request, pedido_id):
    """
    Exporta uma planilha simplificada (Código, Quantidade, Preço) 
    para facilitar a digitação via WhatsApp.
    """
    pedido = get_object_or_404(Pedido, id=pedido_id)
    itens_pedido = ItemPedido.objects.filter(pedido=pedido).select_related('produto')
    uf_cliente = pedido.cliente.client_state.uf_name

    # Define qual valor unitário usar com base no estado
    valor_key = 'valor_unitario_sp' if uf_cliente == 'SP' else 'valor_unitario_es'

    data = []
    for item in itens_pedido:
        valor_unitario = getattr(item, valor_key) or 0
        data.append({
            'Código': item.produto.product_code,
            'Quantidade': item.quantidade,
            'Preço Unitário': float(valor_unitario),
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resumo para Digitação')
        
        # Ajuste de largura básico
        worksheet = writer.sheets['Resumo para Digitação']
        worksheet.set_column('A:A', 15) # Código
        worksheet.set_column('B:C', 12) # Qtd e Preço

    output.seek(0)
    data_hoje = date.today().strftime('%d-%m-%Y')
    filename = f"pedido_{pedido.cliente.client_code}_{data_hoje}.xlsx"
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@login_required
def detalhes_produto(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    
    # Busca recomendações
    recomendacoes_raw = product.get_recommendations(limit=4)
    
    # Transforma em objetos Product para facilitar o uso no template (preços, etc)
    recomendacoes_ids = [item['produto_id'] for item in recomendacoes_raw]
    produtos_recomendados = Product.objects.filter(product_id__in=recomendacoes_ids)

    return render(request, 'detalhes_produto.html', {
        'product': product,
        'recomendacoes': produtos_recomendados
    })


@login_required
def sugestoes_compra(request):
    try:
        cliente_logado = request.user.wfclient
        # Busca os itens frequentes usando o método que criamos no Model
        itens_frequentes = cliente_logado.get_frequent_items(limit=24) # Aumentei o limite para uma página cheia
    except WfClient.DoesNotExist:
        return redirect('home')

    contexto = {
        'titulo': 'Sugestões de Reabastecimento',
        'itens_frequentes': itens_frequentes,
        'cliente_logado': cliente_logado,
    }
    return render(request, 'sugestoes.html', contexto)

# upload planilha do trs
@staff_member_required
def upload_vendas_reais(request):
    if request.method == 'POST' and request.FILES.get('planilha_vendas'):
        file = request.FILES['planilha_vendas']
        try:
            # Lemos a planilha garantindo que o pandas não crie linhas fantasmas
            df = pd.read_excel(file)
            df = df.dropna(how='all')  # Remove linhas completamente vazias

            # --- OTIMIZAÇÃO 1: CONVERSÃO DE DATA EM LOTE ---
            # Converte a coluna inteira de uma vez (muito mais rápido que fazer linha a linha)
            df['Emissão_dt'] = pd.to_datetime(df['Emissão'], dayfirst=True)
            
            # Descobre quais meses e anos únicos existem na planilha que você acabou de subir
            # Formato: ['2026-01', '2026-02', ...]
            meses_anos_na_planilha = df['Emissão_dt'].dt.strftime('%Y-%m').unique()

            # --- OTIMIZAÇÃO 2: LIMPEZA INTELIGENTE ---
            with transaction.atomic():
                # Apaga APENAS os dados dos meses que vieram na planilha. 
                # Preserva todo o restante do histórico no banco de dados.
                for mes_ano in meses_anos_na_planilha:
                    ano, mes = mes_ano.split('-')
                    VendaReal.objects.filter(Emissao__year=int(ano), Emissao__month=int(mes)).delete()

            # 2. CACHE DE CLIENTES (Performance mantida)
            clientes_dict = {
                str(c.client_code): c.client_name 
                for c in WfClient.objects.all().only('client_code', 'client_name')
            }

            novas_vendas = []
            
            # 3. PROCESSAMENTO
            for _, row in df.iterrows():
                # Validação básica para evitar erros de conversão em células vazias
                if pd.isna(row['Código_Cliente']) or pd.isna(row['Total']):
                    continue

                cod_cliente_str = str(int(row['Código_Cliente']))
                nome_cliente = clientes_dict.get(cod_cliente_str, f"Cod: {cod_cliente_str}")

                venda = VendaReal(
                    Emissao=row['Emissão_dt'].date(), # Usa a data já convertida e otimizada
                    Codigo_Cliente=int(row['Código_Cliente']),
                    Pedido=str(row['Pedido']),
                    Produto_Codigo=str(row['Produto_Código']),
                    cliente_nome=nome_cliente,
                    Produto_Descricao=str(row['Produto_Descrição']),
                    Quantidade=int(row['Quantidade']),
                    Unitario=Decimal(str(row['Unitário'])),
                    Total=Decimal(str(row['Total'])),
                )
                novas_vendas.append(venda)

            # 4. SALVAMENTO EM LOTE
            if novas_vendas:
                with transaction.atomic():
                    # Adicionado ignore_conflicts=True como blindagem extra contra duplicatas do ERP
                    VendaReal.objects.bulk_create(novas_vendas, batch_size=500, ignore_conflicts=True)
                
                # Mensagem de sucesso amigável mostrando os meses afetados
                meses_formatados = ", ".join(meses_anos_na_planilha)
                messages.success(request, f'Sucesso! {len(novas_vendas)} itens importados. Histórico atualizado para: {meses_formatados}.')
            else:
                messages.warning(request, 'Nenhum dado válido encontrado na planilha.')
            
        except Exception as e:
            messages.error(request, f'Erro crítico ao processar: {e}')
        
        return redirect('dashboard_admin')

    return render(request, 'analise/upload_vendas_reais.html')

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from .models import VendaReal
from django.contrib.admin.views.decorators import staff_member_required

from datetime import date # Certifique-se de que isso está nos seus imports no topo do arquivo

@staff_member_required
def listar_vendas_reais(request):
    # 1. Captura e limpa filtros
    filtro_pedido = request.GET.get('pedido', '').strip()
    filtro_produto = request.GET.get('produto', '').strip()
    filtro_cliente = request.GET.get('cliente', '').strip()
    
    # NOVOS FILTROS: Mês e Ano
    filtro_mes = request.GET.get('mes', '').strip()
    filtro_ano = request.GET.get('ano', '').strip()

    vendas_qs = VendaReal.objects.all().order_by('-Emissao', '-Pedido')

    # 2. Aplica Filtros Dinâmicos
    if filtro_pedido:
        vendas_qs = vendas_qs.filter(Pedido__icontains=filtro_pedido)
    if filtro_produto:
        vendas_qs = vendas_qs.filter(
            Q(Produto_Codigo__icontains=filtro_produto) | 
            Q(Produto_Descricao__icontains=filtro_produto)
        )
    if filtro_cliente:
        vendas_qs = vendas_qs.filter(
            Q(cliente_nome__icontains=filtro_cliente) | 
            Q(Codigo_Cliente__icontains=filtro_cliente)
        )
        
    # APLICAÇÃO DOS NOVOS FILTROS (com validação para evitar erros na URL)
    if filtro_mes and filtro_mes.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__month=int(filtro_mes))
    if filtro_ano and filtro_ano.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__year=int(filtro_ano))

    # 3. Paginação Robusta (50 itens)
    paginator = Paginator(vendas_qs, 50)
    page_number = request.GET.get('page', 1)
    vendas_paginadas = paginator.get_page(page_number)

    # 4. Formatação Blindada para o Template
    for v in vendas_paginadas:
        v.unit_str = "{:,.2f}".format(float(v.Unitario)).replace(",", "X").replace(".", ",").replace("X", ".")
        v.total_str = "{:,.2f}".format(float(v.Total)).replace(",", "X").replace(".", ",").replace("X", ".")

    # Otimização para o Template: Enviamos a lista de anos para o Select HTML
    hoje = date.today()
    lista_anos = range(hoje.year - 2, hoje.year + 1)

    contexto = {
        'titulo': 'Histórico Detalhado ERP',
        'vendas': vendas_paginadas,
        # Enviamos os filtros de volta para o template para manter os inputs preenchidos
        'filtro_pedido': filtro_pedido,
        'filtro_produto': filtro_produto,
        'filtro_cliente': filtro_cliente,
        'filtro_mes': filtro_mes,
        'filtro_ano': filtro_ano,
        'lista_anos': lista_anos,
    }
    return render(request, 'analise/listar_vendas_reais.html', contexto)

@staff_member_required
def exportar_vendas_reais_excel(request):
    # 1. Captura os mesmos filtros da tela de listagem
    filtro_pedido = request.GET.get('pedido', '').strip()
    filtro_produto = request.GET.get('produto', '').strip()
    filtro_cliente = request.GET.get('cliente', '').strip()
    
    # NOVOS FILTROS: Mês e Ano
    filtro_mes = request.GET.get('mes', '').strip()
    filtro_ano = request.GET.get('ano', '').strip()

    vendas_qs = VendaReal.objects.all().order_by('-Emissao')

    # 2. Aplica Filtros Dinâmicos
    if filtro_pedido:
        vendas_qs = vendas_qs.filter(Pedido__icontains=filtro_pedido)
    if filtro_produto:
        vendas_qs = vendas_qs.filter(
            Q(Produto_Codigo__icontains=filtro_produto) | 
            Q(Produto_Descricao__icontains=filtro_produto)
        )
    if filtro_cliente:
        vendas_qs = vendas_qs.filter(
            Q(cliente_nome__icontains=filtro_cliente) | 
            Q(Codigo_Cliente__icontains=filtro_cliente)
        )
        
    # APLICAÇÃO DOS NOVOS FILTROS
    if filtro_mes and filtro_mes.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__month=int(filtro_mes))
    if filtro_ano and filtro_ano.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__year=int(filtro_ano))

    # 3. Transforma o QuerySet em uma lista de dicionários para o Pandas
    data = []
    for v in vendas_qs:
        data.append({
            'Emissão': v.Emissao.strftime('%d/%m/%Y'),
            'Pedido': v.Pedido,
            'Cód. Cliente': v.Codigo_Cliente,
            'Cliente': v.cliente_nome,
            'Cód. Produto': v.Produto_Codigo,
            'Descrição': v.Produto_Descricao,
            'Quantidade': v.Quantidade,
            'Unitário': float(v.Unitario),
            'Total': float(v.Total),
        })

    # 4. Criação do Excel em memória
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Vendas Reais')
        
    output.seek(0)

    # 5. Resposta HTTP para download (Nome do arquivo dinâmico)
    # Se filtrou por ano e mês, coloca no nome do arquivo (ex: vendas_reais_2026_02.xlsx)
    periodo_str = f"_{filtro_ano}_{filtro_mes}" if filtro_ano and filtro_mes else ""
    filename = f"vendas_reais{periodo_str}_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@staff_member_required
def dashboard_analise(request):
    # --- FILTRO DE DATA ---
    hoje = date.today()
    mes_selecionado = int(request.GET.get('mes', hoje.month))
    ano_selecionado = int(request.GET.get('ano', hoje.year))
    
    # --- TRAVA DE PERÍODO ---
    vendas_qs = VendaReal.objects.filter(
        Emissao__month=mes_selecionado, 
        Emissao__year=ano_selecionado
    )

    # --- LÓGICA DE CALENDÁRIO ---
    primeiro_dia_mes = date(ano_selecionado, mes_selecionado, 1)
    ultimo_dia_valor = calendar.monthrange(ano_selecionado, mes_selecionado)[1]
    ultimo_dia_mes = date(ano_selecionado, mes_selecionado, ultimo_dia_valor)

    if mes_selecionado == hoje.month and ano_selecionado == hoje.year:
        data_fim_calculo = hoje
    else:
        data_fim_calculo = ultimo_dia_mes

    def contar_dias_uteis(data_inicio, data_fim):
        dias = 0
        atual = data_inicio
        while atual <= data_fim:
            if atual.weekday() < 5: dias += 1
            atual += timedelta(days=1)
        return dias

    # --- 1. MÉTRICAS BÁSICAS ---
    total_faturamento = vendas_qs.aggregate(total=Sum('Total'))['total'] or Decimal('0.00')
    total_itens = vendas_qs.aggregate(total=Sum('Quantidade'))['total'] or 0
    total_pedidos = vendas_qs.values('Pedido').distinct().count() or 1
    total_vendas_str = "{:,.2f}".format(float(total_faturamento)).replace(",", "X").replace(".", ",").replace("X", ".")
    ticket_valor = float(total_faturamento) / total_pedidos if total_pedidos > 0 else 0
    ticket_medio_formatado = "{:,.2f}".format(ticket_valor).replace(",", "X").replace(".", ",").replace("X", ".")

    # --- 2. PROJEÇÃO E MÉDIA ---
    dias_uteis_decorridos = contar_dias_uteis(primeiro_dia_mes, data_fim_calculo)
    total_dias_uteis_mes = contar_dias_uteis(primeiro_dia_mes, ultimo_dia_mes)
    divisor = max(dias_uteis_decorridos, 1)
    media_diaria_util = float(total_faturamento) / divisor
    projecao_valor = media_diaria_util * total_dias_uteis_mes
    progresso_percentual = int((dias_uteis_decorridos / total_dias_uteis_mes) * 100) if total_dias_uteis_mes > 0 else 0
    media_diaria_str = "{:,.2f}".format(media_diaria_util).replace(",", "X").replace(".", ",").replace("X", ".")
    projecao_final_str = "{:,.2f}".format(projecao_valor).replace(",", "X").replace(".", ",").replace("X", ".")

    # --- 3. RANKINGS COMERCIAL ---
    top_produtos_raw = vendas_qs.values('Produto_Codigo', 'Produto_Descricao').annotate(total_gerado=Sum('Total'), qtd_vendida=Sum('Quantidade')).order_by('-total_gerado')[:10]
    top_produtos_formatados = [{'codigo': p['Produto_Codigo'], 'descricao': p['Produto_Descricao'], 'qtd': p['qtd_vendida'], 'total_formatado': "{:,.2f}".format(float(p['total_gerado'])).replace(",", "X").replace(".", ",").replace("X", ".")} for p in top_produtos_raw]
    
    top_clientes_raw = vendas_qs.values('Codigo_Cliente', 'cliente_nome').annotate(total_gasto=Sum('Total')).order_by('-total_gasto')[:10]
    top_clientes_formatados = [{'codigo': c['Codigo_Cliente'], 'nome': c['cliente_nome'], 'total_formatado': "{:,.2f}".format(float(c['total_gasto'])).replace(",", "X").replace(".", ",").replace("X", ".")} for c in top_clientes_raw]

    # --- 4. RANKING ALERTA (< 50k) ---
    vendas_por_cliente_periodo = vendas_qs.values('Codigo_Cliente').annotate(total_periodo=Sum('Total'))
    mapa_vendas_periodo = {v['Codigo_Cliente']: v['total_periodo'] for v in vendas_por_cliente_periodo}
    todos_clientes_historico = VendaReal.objects.values('Codigo_Cliente', 'cliente_nome').annotate(total_historico=Sum('Total'), ultima_compra=Max('Emissao')).order_by('-total_historico')
    clientes_alerta = []
    for c in todos_clientes_historico:
        total_no_periodo = mapa_vendas_periodo.get(c['Codigo_Cliente'], Decimal('0.00'))
        if total_no_periodo < 50000:
            clientes_alerta.append({'codigo': c['Codigo_Cliente'], 'nome': c['cliente_nome'], 'total_formatado': "{:,.2f}".format(float(c['total_historico'])).replace(",", "X").replace(".", ",").replace("X", "."), 'mes_atual_formatado': "{:,.2f}".format(float(total_no_periodo)).replace(",", "X").replace(".", ",").replace("X", "."), 'ultima_data': c['ultima_compra'].strftime('%d/%m/%Y')})
            if len(clientes_alerta) >= 10: break

    # --- 5. ANÁLISE LOGÍSTICA (Ajustado para incluir o Código do Cliente) ---
    dias_nomes = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    vendas_por_dia = [0.0] * 7
    clientes_por_dia_acumulado = {i: {} for i in range(7)}
    
    for v in vendas_qs:
        dia_indice = v.Emissao.weekday()
        vendas_por_dia[dia_indice] += float(v.Total)
        
        cod_cli = v.Codigo_Cliente
        nome_cli = v.cliente_nome or "Desconhecido"
        
        # Cria ou atualiza o dicionário usando o CÓDIGO como chave principal
        if cod_cli not in clientes_por_dia_acumulado[dia_indice]:
            clientes_por_dia_acumulado[dia_indice][cod_cli] = {'nome': nome_cli, 'valor': 0.0}
        
        clientes_por_dia_acumulado[dia_indice][cod_cli]['valor'] += float(v.Total)
    
    ranking_logistica_dia = []
    for i in range(7):
        # Ordena os clientes pelo valor faturado no dia
        top_clientes_dia = sorted(
            clientes_por_dia_acumulado[i].items(), 
            key=lambda x: x[1]['valor'], 
            reverse=True
        )[:3]
        
        # Prepara os dados para o template
        ranking_logistica_dia.append({
            'dia': dias_nomes[i], 
            'clientes': [
                {
                    'codigo': cod, 
                    'nome': dados['nome'], 
                    'valor': "{:,.2f}".format(dados['valor']).replace(",", "X").replace(".", ",").replace("X", ".")
                } for cod, dados in top_clientes_dia
            ]
        })

    # --- 6. SAÚDE DA BASE ---
    historico_total = VendaReal.objects.values('Codigo_Cliente', 'Emissao', 'cliente_nome').order_by('Codigo_Cliente', 'Emissao')
    dados_habito = {}
    for h in historico_total:
        cod = h['Codigo_Cliente']
        if cod not in dados_habito: dados_habito[cod] = {'nome': h['cliente_nome'], 'datas': set()}
        dados_habito[cod]['datas'].add(h['Emissao'])

    saude_base = []
    for cod, info in dados_habito.items():
        datas = sorted(list(info['datas']))
        if len(datas) < 2: continue
        intervalos = [(datas[i] - datas[i-1]).days for i in range(1, len(datas))]
        media_habito = sum(intervalos) / len(intervalos)
        dias_sem_comprar = (hoje - datas[-1]).days
        if dias_sem_comprar > (media_habito * 1.2) and dias_sem_comprar > 7:
            saude_base.append({'codigo': cod, 'nome': info['nome'], 'media_habito': round(media_habito), 'dias_sem_comprar': dias_sem_comprar, 'atraso': round(dias_sem_comprar - media_habito), 'ultima_data': datas[-1].strftime('%d/%m/%Y')})
    saude_base = sorted(saude_base, key=lambda x: x['atraso'], reverse=True)[:15]

    # --- 7. GRÁFICOS ---
    dados_grafico = vendas_qs.values('Emissao').annotate(total_dia=Sum('Total')).order_by('Emissao')
    l_diario = [d['Emissao'].strftime('%d/%m') for d in dados_grafico]
    v_diario = [float(d['total_dia']) for d in dados_grafico]

    # =========================================================
    # --- 8. OPORTUNIDADES DE RETORNO (WISHLIST) ---
    # =========================================================
    itens_pendentes = ItemPedidoIgnorado.objects.filter(
        notificado=False, 
        motivo_erro__icontains="estoque"
    ).select_related('cliente', 'cliente__client_state')

    oportunidades_wishlist = {}
    
    codigos_pendentes = itens_pendentes.values_list('codigo_produto', flat=True).distinct()
    produtos_dict = {p.product_code: p for p in Product.objects.filter(product_code__in=codigos_pendentes)}

    for item in itens_pendentes:
        produto = produtos_dict.get(item.codigo_produto)
        if not produto or not item.cliente: # Segurança extra caso cliente tenha sido excluído
            continue
            
        estado = item.cliente.client_state.uf_name
        preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
        
        # O MATCH: Verifica se o produto agora tem preço válido
        if preco_atual and preco_atual > 0:
            c_id = item.cliente.client_id
            if c_id not in oportunidades_wishlist:
                oportunidades_wishlist[c_id] = {
                    'cliente': item.cliente,
                    'produtos': []
                }
            # Evita produtos duplicados para o mesmo cliente
            if produto.product_description not in [p['descricao'] for p in oportunidades_wishlist[c_id]['produtos']]:
                oportunidades_wishlist[c_id]['produtos'].append({
                    'codigo': produto.product_code,
                    'descricao': produto.product_description,
                    'preco': float(preco_atual)
                })

    # --- CONTEXTO ---
    contexto = {
        'total_vendas': total_vendas_str, 'ticket_medio': ticket_medio_formatado, 'total_itens_faturados': total_itens, 'total_pedidos_reais': total_pedidos,
        'media_diaria': media_diaria_str, 'projecao_final': projecao_final_str, 'progresso_mes': progresso_percentual,
        'top_produtos': top_produtos_formatados, 'top_clientes': top_clientes_formatados, 'clientes_inativos': clientes_alerta, 
        'labels_diario': json.dumps(l_diario), 'valores_diario': json.dumps(v_diario),
        'labels_semana': json.dumps(dias_nomes), 'valores_semana': json.dumps(vendas_por_dia),
        'ranking_logistica_dia': ranking_logistica_dia, 'saude_base': saude_base,
        'mes_atual': mes_selecionado, 'ano_atual': ano_selecionado, 'lista_anos': range(hoje.year - 2, hoje.year + 1),
        'oportunidades_wishlist': oportunidades_wishlist.values(), # INJETADO AQUI COM SUCESSO!
    }
    return render(request, 'analise/dashboard_analise.html', contexto)


@login_required
def meus_itens_comprados(request):
    try:
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        return redirect('home')

    # --- NOVO: CÁLCULO DO EFETIVO (MÊS VIGENTE) ---
    hoje = timezone.localdate()
    total_efetivo_mes = VendaReal.objects.filter(
        Codigo_Cliente=cliente.client_code,
        Emissao__year=hoje.year,
        Emissao__month=hoje.month
    ).aggregate(total=Sum('Total'))['total'] or Decimal('0.00')

    # Formatação do Efetivo para o padrão R$ 0.000,00
    efetivo_formatado = "{:,.2f}".format(float(total_efetivo_mes)).replace(",", "X").replace(".", ",").replace("X", ".")
    # ----------------------------------------------

    # Lógica de agrupamento compatível com MySQL (mantida)
    vendas_ids = VendaReal.objects.filter(
        Codigo_Cliente=cliente.client_code
    ).values('Produto_Codigo').annotate(
        ultima_venda=Max('id')
    ).values_list('ultima_venda', flat=True)

    vendas_qs = VendaReal.objects.filter(id__in=vendas_ids).order_by('Produto_Descricao')

    # Filtros de busca
    filtro_produto = request.GET.get('produto', '').strip()
    if filtro_produto:
        vendas_qs = vendas_qs.filter(
            Q(Produto_Codigo__icontains=filtro_produto) | 
            Q(Produto_Descricao__icontains=filtro_produto)
        )

    # Paginação
    paginator = Paginator(vendas_qs, 50)
    page_number = request.GET.get('page', 1)
    vendas_paginadas = paginator.get_page(page_number)

    # Formatação blindada de valores da tabela
    for v in vendas_paginadas:
        v.unit_str = "{:,.2f}".format(float(v.Unitario)).replace(",", "X").replace(".", ",").replace("X", ".")

    contexto = {
        'titulo': 'Meus Itens Comprados',
        'vendas': vendas_paginadas,
        'cliente_logado': cliente,
        'efetivo_mes': efetivo_formatado, # Novo dado no contexto
        'mes_nome': hoje.strftime('%B').capitalize() # Opcional: nome do mês
    }
    return render(request, 'meus_itens_comprados.html', contexto)

@login_required
def exportar_meus_itens_excel(request):
    try:
        cliente = request.user.wfclient
    except WfClient.DoesNotExist:
        return redirect('home')

    # 1. Filtra todas as vendas do cliente logado no ERP
    vendas_qs = VendaReal.objects.filter(
        Codigo_Cliente=cliente.client_code
    ).order_by('-Emissao', '-Pedido')

    # 2. Prepara os dados para o DataFrame (Pandas)
    data = []
    for v in vendas_qs:
        data.append({
            'Emissão': v.Emissao.strftime('%d/%m/%Y'),
            'Pedido ERP': v.Pedido,
            'Cód. Produto': v.Produto_Codigo,
            'Descrição': v.Produto_Descricao,
            'Quantidade': v.Quantidade,
            'Unitário': float(v.Unitario),
            'Total Item': float(v.Total),
        })

    # 3. Criação do Excel em memória (usando o padrão BytesIO que você já utiliza)
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Meu Histórico de Compras')
        
    output.seek(0)

    # 4. Resposta HTTP para download
    filename = f"historico_compras_{cliente.client_code}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@staff_member_required
def upload_status_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        pdf_file = request.FILES['pdf_file']
        novos_status_preparados = []
        
        # Mapeamento expandido para incluir o bloqueio de preço
        MAP_SINC_STATUS = {
            '4-Bloqueado Separação': 'SEPARACAO',
            '6-Pronto para Faturar': 'EXPEDICAO',
            '8-Faturado': 'FINALIZADO',
            '2-Bloqueado Crédito': 'FINANCEIRO',
            '1-Bloqueado Preço': 'PRECO',  # Adicionado para evitar 'não identificado' 
        }

        try:
            import pdfplumber
            from datetime import datetime
            from django.db import transaction
            import re

            with pdfplumber.open(pdf_file) as pdf:
                for pagina in pdf.pages:
                    tabela = pagina.extract_table({"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 4})
                    if not tabela: continue
                        
                    for linha in tabela:
                        l = [str(c).strip() for c in linha if c and str(c).strip() != ""]
                        
                        # Uma linha válida DEVE começar com a data (dd/mm/aaaa) [cite: 39, 40]
                        if len(l) >= 4 and re.match(r'\d{2}/\d{2}/\d{4}', l[0]) and l[1].isdigit():
                            
                            # Juntamos TUDO para garantir que palavras picadas sejam achadas [cite: 76, 77]
                            linha_texto = " ".join(l).upper()

                            # --- IDENTIFICAÇÃO DO STATUS (Hieraquia Corrigida) ---
                            # Crédito e Preço devem ser checados primeiro 
                            if any(x in linha_texto for x in ['CREAITA', 'CREDITO', 'CRÉDITO', 'BLOQUENDA']):
                                status_pdf = '2-Bloqueado Crédito'
                            elif 'PREÇO' in linha_texto or 'PRECO' in linha_texto:
                                status_pdf = '1-Bloqueado Preço'  # Correção aplicada 
                            elif 'EPARAÇ' in linha_texto:
                                status_pdf = '4-Bloqueado Separação'
                            elif 'PRONTO' in linha_texto:
                                status_pdf = '6-Pronto para Faturar'
                            elif any(x in linha_texto for x in ['FATURADO', '8=', '8-']):
                                status_pdf = '8-Faturado'
                            else:
                                status_pdf = "Status não identificado"

                            # --- EXTRAÇÃO DO CLIENTE (Pulando Charles/Vendedor) ---
                            miolo_cliente = " ".join(l[3:-1]) 
                            
                            match_cliente = re.search(r'(\d+)\s*[-–—]\s*([A-Z\s&]{3,})', miolo_cliente)
                            
                            if match_cliente:
                                cod_c = match_cliente.group(1)
                                nome_c = match_cliente.group(2).strip()
                            else:
                                match_fallback = re.search(r'(\d+)\s+([A-Z\s&]{4,})', miolo_cliente)
                                cod_c = match_fallback.group(1) if match_fallback else ""
                                nome_c = match_fallback.group(2).strip() if match_fallback else miolo_cliente

                            # Limpeza de nomes e ruídos (CPFs/Datas) [cite: 40, 41]
                            nome_c = nome_c.replace("  ", " ").replace("CARL OS", "CARLOS").replace("AL VES", "ALVES")
                            nome_c = re.sub(r'\s*\d{11}.*', '', nome_c) 
                            nome_c = re.sub(r'\d{2}/\d{2}/\d{4}.*', '', nome_c).strip()

                            novos_status_preparados.append({
                                'emissao': datetime.strptime(l[0], '%d/%m/%Y').date(),
                                'numero_pedido': l[1],
                                'cod_cliente': cod_c,
                                'nome_cliente': nome_c[:255],
                                'situacao': status_pdf,
                                'expedido': any(x in l[-1].upper() for x in ['SIM', 'SIRM', 'SI']) # [cite: 39]
                            })

            if novos_status_preparados:
                with transaction.atomic():
                    for data in novos_status_preparados:
                        # Limpa para evitar duplicados [cite: 40, 41]
                        StatusPedidoERP.objects.filter(numero_pedido=data['numero_pedido']).delete()
                        StatusPedidoERP.objects.create(**data)
                        
                        pedido_site = Pedido.objects.filter(id=data['numero_pedido']).first()
                        if pedido_site:
                            novo_status_interno = MAP_SINC_STATUS.get(data['situacao'])
                            if novo_status_interno:
                                pedido_site.status = novo_status_interno
                                pedido_site.save(update_fields=['status'])

                messages.success(request, f"Sucesso! {len(novos_status_preparados)} pedidos processados.")
            return redirect('dashboard_admin')

        except Exception as e:
            messages.error(request, f"Erro crítico: {str(e)}")
            return redirect('dashboard_admin')

    return render(request, 'analise/upload_status_pdf.html')


@staff_member_required
def listar_status_erp(request):
    # 1. Busca todos os registros
    status_qs = StatusPedidoERP.objects.all().order_by('-emissao', '-id')
    
    # 2. Filtro de busca por número do pedido
    numero_pedido = request.GET.get('numero_pedido')
    if numero_pedido:
        status_qs = status_qs.filter(numero_pedido__icontains=numero_pedido)

    # 3. CÁLCULO PARA OS CARDS DO TOPO
    # Conta quantos registros únicos estão marcados como expedidos
    total_expedidos = status_qs.filter(expedido=True).count()

    # 4. Paginação (50 por página)
    paginator = Paginator(status_qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'titulo': 'Monitoramento de Status ERP',
        'page_obj': page_obj,
        'numero_pedido': numero_pedido,
        'total_expedidos': total_expedidos, # Agora o template consegue ler este valor
    }
    return render(request, 'analise/listar_status_erp.html', contexto)

@staff_member_required
def exportar_status_erp_excel(request):
    # 1. Pega os dados base (respeitando filtros de busca se houver)
    status_qs = StatusPedidoERP.objects.all().order_by('-emissao', '-id')
    
    numero_pedido = request.GET.get('numero_pedido')
    if numero_pedido:
        status_qs = status_qs.filter(numero_pedido__icontains=numero_pedido)

    # 2. Prepara a lista de dicionários para o Pandas
    dados = []
    for item in status_qs:
        dados.append({
            'Emissão ERP': item.emissao,
            'Pedido': item.numero_pedido,
            'Cód. Cliente': item.cod_cliente,
            'Cliente': item.nome_cliente,
            'Situação': item.situacao,
            'Expedido': 'SIM' if item.expedido else 'NÃO'
        })

    # 3. Cria o DataFrame e o arquivo Excel
    df = pd.DataFrame(dados)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=Relatorio_Status_ERP.xlsx'
    
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Status')
    
    return response
@staff_member_required
def notificar_wishlist_whatsapp(request, cliente_id):
    cliente = get_object_or_404(WfClient, client_id=cliente_id)
    estado = cliente.client_state.uf_name
    
    # Filtra itens ignorados por estoque que ainda não foram notificados
    itens_pendentes = ItemPedidoIgnorado.objects.filter(
        cliente=cliente,
        notificado=False,
        motivo_erro__icontains="estoque"
    )
    
    produtos_recuperados = []
    ids_para_atualizar = []
    
    # Valida disponibilidade atual e monta a lista com quantidades
    for item in itens_pendentes:
        produto = Product.objects.filter(product_code=item.codigo_produto).first()
        if produto:
            preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
            if preco_atual and preco_atual > 0:
                # Inclui a quantidade tentada capturada no upload original
                qtd = item.quantidade_tentada if item.quantidade_tentada else 0
                produto_texto = f"- {produto.product_code}: {qtd} un. ({produto.product_description}) | R$ {preco_atual:.2f}".replace(".", ",")
                
                if produto_texto not in produtos_recuperados:
                    produtos_recuperados.append(produto_texto)
                ids_para_atualizar.append(item.id)
    
    if not produtos_recuperados:
        messages.warning(request, "Os produtos deste cliente ficaram sem estoque novamente.")
        return redirect('dashboard_admin')
        
    # Gera o link absoluto para a nova planilha de recuperação
    link_download = request.build_absolute_uri(
        reverse('exportar_itens_recuperados_excel', args=[cliente.client_id])
    )

    # 1. ATUALIZA O BANCO E CACHE
    ItemPedidoIgnorado.objects.filter(id__in=ids_para_atualizar).update(notificado=True)
    cache.delete('dashboard_wishlist')
    
    # 2. MONTA A MENSAGEM COM O LINK
    produtos_texto = "\n".join(produtos_recuperados)
    mensagem = (
        f"Olá, {cliente.client_name}! Tudo bem?\n\n"
        f"Temos uma ótima notícia! Aqueles itens que você tentou pedir recentemente e estavam em falta, *acabaram de chegar no nosso estoque*:\n\n"
        f"{produtos_texto}\n\n"
        f"*Baixe a planilha de reposição aqui:* \n{link_download}\n\n"
        f"Gostaria de aproveitar e incluir no seu próximo pedido?"
    )
    
    link_whatsapp = f"https://api.whatsapp.com/send?text={quote(mensagem)}"
    messages.success(request, f"Cliente {cliente.client_name} marcado como notificado!")
    return redirect(link_whatsapp)

@login_required
@require_POST
def adicionar_ao_carrinho_bd(request):
    product_id = request.POST.get('product_id')
    quantidade = int(request.POST.get('quantidade', 1))
    
    try:
        cliente_logado = request.user.wfclient
    except WfClient.DoesNotExist:
        return JsonResponse({'erro': 'Cliente não encontrado.'}, status=400)

    if quantidade <= 0:
        return JsonResponse({'erro': 'Quantidade inválida.'}, status=400)

    produto = get_object_or_404(Product, product_id=product_id)

    # 1. Pega o carrinho do cliente (ou cria um novo, vazio)
    carrinho, _ = Carrinho.objects.get_or_create(cliente=cliente_logado)

    # 2. Adiciona o item ao carrinho (ou soma a quantidade se já existir)
    item, created = ItemCarrinho.objects.get_or_create(
        carrinho=carrinho,
        produto=produto,
        defaults={'quantidade': quantidade}
    )
    
    if not created:
        item.quantidade += quantidade
        item.save()

    # =========================================================
    # --- NOVO: AUTO-LIMPEZA DA WISHLIST ---
    # Se o cliente adicionou ao carrinho, marcamos o erro como resolvido/notificado.
    # O produto nunca mais aparecerá no banner de "voltou ao estoque" para este cliente.
    # =========================================================
    from .models import ItemPedidoIgnorado # Importação caso não esteja no topo do arquivo
    ItemPedidoIgnorado.objects.filter(
        cliente=cliente_logado,
        codigo_produto=produto.product_code,
        notificado=False
    ).update(notificado=True)

    # 3. Retorna os valores em tempo real para o Frontend atualizar a tela
    return JsonResponse({
        'sucesso': True, 
        'item_quantidade': item.quantidade,
        'item_total': float(item.get_subtotal()),
        'pedido_total': float(carrinho.get_total_carrinho()),
        'codigo_produto': produto.product_code # INJETADO: Enviamos o código de volta para animar a tela
    })

def exportar_itens_recuperados_excel(request, cliente_id):
    cliente = get_object_or_404(WfClient, client_id=cliente_id)
    estado = cliente.client_state.uf_name
    
    # Busca itens que foram ignorados por falta de estoque
    itens = ItemPedidoIgnorado.objects.filter(
        cliente=cliente,
        motivo_erro__icontains="estoque"
    )

    data = []
    for item in itens:
        produto = Product.objects.filter(product_code=item.codigo_produto).first()
        if produto:
            preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
            # Só inclui na planilha se o produto realmente voltou ao estoque (preço > 0)
            if preco_atual and preco_atual > 0:
                data.append({
                    'Código': item.codigo_produto,
                    'Descrição': produto.product_description,
                    'Quantidade Solicitada': item.quantidade_tentada,
                    'Preço Unitário': float(preco_atual),
                    'Subtotal': float(preco_atual * item.quantidade_tentada)
                })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Itens Recuperados')
    
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=recuperacao_{cliente.client_code}.xlsx'
    return response

@staff_member_required
def historico_wishlist(request):
    """
    Exibe o histórico de todos os itens da Wishlist que já foram notificados aos clientes.
    """
    # Filtra apenas os que já foram notificados e que eram erro de estoque
    itens_arquivados = ItemPedidoIgnorado.objects.filter(
        notificado=True,
        motivo_erro__icontains="estoque"
    ).select_related('cliente', 'pedido').order_by('-data_tentativa')

    # Paginação (50 itens por página)
    paginator = Paginator(itens_arquivados, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'titulo': 'Histórico de Oportunidades Notificadas',
        'page_obj': page_obj,
    }
    
    # Você precisará criar este arquivo HTML simples na sua pasta de templates
    return render(request, 'analise/historico_wishlist.html', contexto)

@staff_member_required
def reenviar_notificacao_whatsapp(request, cliente_id):
    cliente = get_object_or_404(WfClient, client_id=cliente_id)
    estado = cliente.client_state.uf_name
    
    # Diferença aqui: busca os itens que JÁ FORAM notificados (notificado=True)
    itens_arquivados = ItemPedidoIgnorado.objects.filter(
        cliente=cliente,
        notificado=True,
        motivo_erro__icontains="estoque"
    )
    
    produtos_recuperados = []
    
    # Valida se os itens ainda estão com preço > 0 hoje
    for item in itens_arquivados:
        produto = Product.objects.filter(product_code=item.codigo_produto).first()
        if produto:
            preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
            if preco_atual and preco_atual > 0:
                qtd = item.quantidade_tentada if item.quantidade_tentada else 0
                produto_texto = f"- {produto.product_code}: {qtd} un. ({produto.product_description}) | R$ {preco_atual:.2f}".replace(".", ",")
                
                if produto_texto not in produtos_recuperados:
                    produtos_recuperados.append(produto_texto)
    
    if not produtos_recuperados:
        messages.warning(request, "Os produtos deste cliente não estão mais disponíveis no estoque para reenvio.")
        return redirect('historico_wishlist')

    # Gera o link da planilha
    link_download = request.build_absolute_uri(
        reverse('exportar_itens_recuperados_excel', args=[cliente.client_id])
    )
    
    # Monta a mensagem idêntica
    produtos_texto = "\n".join(produtos_recuperados)
    mensagem = (
        f"Olá, {cliente.client_name}! Tudo bem?\n\n"
        f"Temos uma ótima notícia! Aqueles itens que você tentou pedir recentemente e estavam em falta, *acabaram de chegar no nosso estoque*:\n\n"
        f"{produtos_texto}\n\n"
        f"*Baixe a planilha de reposição aqui:* \n{link_download}\n\n"
        f"Gostaria de aproveitar e incluir no seu próximo pedido?"
    )
    
    # Redireciona para o WhatsApp (recomendo usar target="_blank" no HTML)
    link_whatsapp = f"https://api.whatsapp.com/send?text={quote(mensagem)}"
    return redirect(link_whatsapp)