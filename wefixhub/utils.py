import re
import json
import calendar
import statistics
import pandas as pd
import pdfplumber
from io import BytesIO
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Max, Q, Count

# Removi o 'messages' daqui, pois ele pertence às views
# Removi as duplicatas de Pedido e Product
from .models import (
    VendaReal, ItemPedidoIgnorado, Product,
    StatusPedidoERP, Pedido, WfClient, SugestaoCompraERP,
    ItemPedido, Endereco, SnapshotRFM,
)

# ====================================================================
# 1. FUNÇÃO DO DASHBOARD DE ANÁLISE
# ====================================================================
def gerar_dados_dashboard_analise(mes_selecionado, ano_selecionado, empresa=None):
    hoje = date.today()

    def _empresa(qs, campo='empresa'):
        return qs.filter(**{campo: empresa}) if empresa else qs

    vendas_qs = _empresa(VendaReal.objects.filter(Emissao__month=mes_selecionado, Emissao__year=ano_selecionado))

    primeiro_dia_mes = date(ano_selecionado, mes_selecionado, 1)
    ultimo_dia_valor = calendar.monthrange(ano_selecionado, mes_selecionado)[1]
    ultimo_dia_mes = date(ano_selecionado, mes_selecionado, ultimo_dia_valor)
    data_fim_calculo = hoje if (mes_selecionado == hoje.month and ano_selecionado == hoje.year) else ultimo_dia_mes

    def contar_dias_uteis(data_inicio, data_fim):
        dias = 0
        atual = data_inicio
        while atual <= data_fim:
            if atual.weekday() < 5: dias += 1
            atual += timedelta(days=1)
        return dias

    total_faturamento = vendas_qs.aggregate(total=Sum('Total'))['total'] or Decimal('0.00')
    total_itens = vendas_qs.aggregate(total=Sum('Quantidade'))['total'] or 0
    total_pedidos = vendas_qs.values('Pedido').distinct().count() or 1
    total_vendas_str = "{:,.2f}".format(float(total_faturamento)).replace(",", "X").replace(".", ",").replace("X", ".")
    ticket_valor = float(total_faturamento) / total_pedidos if total_pedidos > 0 else 0
    ticket_medio_formatado = "{:,.2f}".format(ticket_valor).replace(",", "X").replace(".", ",").replace("X", ".")

    dias_uteis_decorridos = contar_dias_uteis(primeiro_dia_mes, data_fim_calculo)
    total_dias_uteis_mes = contar_dias_uteis(primeiro_dia_mes, ultimo_dia_mes)
    divisor = max(dias_uteis_decorridos, 1)
    media_diaria_util = float(total_faturamento) / divisor
    projecao_valor = media_diaria_util * total_dias_uteis_mes
    progresso_percentual = int((dias_uteis_decorridos / total_dias_uteis_mes) * 100) if total_dias_uteis_mes > 0 else 0
    media_diaria_str = "{:,.2f}".format(media_diaria_util).replace(",", "X").replace(".", ",").replace("X", ".")
    projecao_final_str = "{:,.2f}".format(projecao_valor).replace(",", "X").replace(".", ",").replace("X", ".")

    # Comparativo mês anterior
    mes_ant = mes_selecionado - 1 if mes_selecionado > 1 else 12
    ano_ant = ano_selecionado if mes_selecionado > 1 else ano_selecionado - 1
    total_mes_anterior = _empresa(VendaReal.objects.filter(
        Emissao__month=mes_ant, Emissao__year=ano_ant
    )).aggregate(total=Sum('Total'))['total'] or Decimal('0.00')
    variacao_mes = round(
        ((float(total_faturamento) - float(total_mes_anterior)) / float(total_mes_anterior) * 100), 1
    ) if total_mes_anterior > 0 else 0

    top_produtos_raw = vendas_qs.values('Produto_Codigo', 'Produto_Descricao').annotate(total_gerado=Sum('Total'), qtd_vendida=Sum('Quantidade')).order_by('-total_gerado')[:10]
    top_produtos_formatados = [{'codigo': p['Produto_Codigo'], 'descricao': p['Produto_Descricao'], 'qtd': p['qtd_vendida'], 'total_formatado': "{:,.2f}".format(float(p['total_gerado'])).replace(",", "X").replace(".", ",").replace("X", ".")} for p in top_produtos_raw]

    top_clientes_raw = list(vendas_qs.values('Codigo_Cliente', 'cliente_nome').annotate(total_gasto=Sum('Total')).order_by('-total_gasto'))
    top_clientes_formatados = [{'codigo': c['Codigo_Cliente'], 'nome': c['cliente_nome'], 'total_formatado': "{:,.2f}".format(float(c['total_gasto'])).replace(",", "X").replace(".", ",").replace("X", ".")} for c in top_clientes_raw]

    # SP vs ES breakdown
    todos_codigos = [c['Codigo_Cliente'] for c in top_clientes_raw]
    wf_qs = WfClient.objects.filter(client_code__in=todos_codigos).select_related('client_state')
    if empresa:
        wf_qs = wf_qs.filter(empresa=empresa)
    mapa_estado = {str(wfc.client_code): wfc.client_state.uf_name for wfc in wf_qs if wfc.client_state}
    total_sp = Decimal('0.00')
    total_es = Decimal('0.00')
    for c in top_clientes_raw:
        estado = mapa_estado.get(str(c['Codigo_Cliente']))
        if estado == 'SP':
            total_sp += c['total_gasto']
        elif estado == 'ES':
            total_es += c['total_gasto']

    vendas_por_cliente_periodo = vendas_qs.values('Codigo_Cliente').annotate(total_periodo=Sum('Total'))
    mapa_vendas_periodo = {v['Codigo_Cliente']: v['total_periodo'] for v in vendas_por_cliente_periodo}
    todos_clientes_historico = _empresa(VendaReal.objects.all()).values('Codigo_Cliente', 'cliente_nome').annotate(total_historico=Sum('Total'), ultima_compra=Max('Emissao')).order_by('-total_historico')
    clientes_alerta = []
    for c in todos_clientes_historico:
        total_no_periodo = mapa_vendas_periodo.get(c['Codigo_Cliente'], Decimal('0.00'))
        if total_no_periodo < 50000:
            clientes_alerta.append({'codigo': c['Codigo_Cliente'], 'nome': c['cliente_nome'], 'total_formatado': "{:,.2f}".format(float(c['total_historico'])).replace(",", "X").replace(".", ",").replace("X", "."), 'mes_atual_formatado': "{:,.2f}".format(float(total_no_periodo)).replace(",", "X").replace(".", ",").replace("X", "."), 'ultima_data': c['ultima_compra'].strftime('%d/%m/%Y')})
            if len(clientes_alerta) >= 10: break

    dias_nomes = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    vendas_por_dia = [0.0] * 7
    clientes_por_dia_acumulado = {i: {} for i in range(7)}

    for v in vendas_qs:
        dia_indice = v.Emissao.weekday()
        vendas_por_dia[dia_indice] += float(v.Total)
        cod_cli = v.Codigo_Cliente
        nome_cli = v.cliente_nome or "Desconhecido"
        if cod_cli not in clientes_por_dia_acumulado[dia_indice]:
            clientes_por_dia_acumulado[dia_indice][cod_cli] = {'nome': nome_cli, 'valor': 0.0}
        clientes_por_dia_acumulado[dia_indice][cod_cli]['valor'] += float(v.Total)

    ranking_logistica_dia = []
    for i in range(7):
        top_clientes_dia = sorted(clientes_por_dia_acumulado[i].items(), key=lambda x: x[1]['valor'], reverse=True)[:3]
        ranking_logistica_dia.append({'dia': dias_nomes[i], 'clientes': [{'codigo': cod, 'nome': dados['nome'], 'valor': "{:,.2f}".format(dados['valor']).replace(",", "X").replace(".", ",").replace("X", ".")} for cod, dados in top_clientes_dia]})

    data_corte_habito = hoje - timedelta(days=548)  # ~18 meses
    historico_total = _empresa(VendaReal.objects.filter(Emissao__gte=data_corte_habito)).values('Codigo_Cliente', 'Emissao', 'cliente_nome').order_by('Codigo_Cliente', 'Emissao')
    dados_habito = {}
    for h in historico_total:
        cod = h['Codigo_Cliente']
        if cod not in dados_habito: dados_habito[cod] = {'nome': h['cliente_nome'], 'datas': set()}
        dados_habito[cod]['datas'].add(h['Emissao'])

    saude_base_todos = []
    for cod, info in dados_habito.items():
        datas = sorted(list(info['datas']))
        if len(datas) < 2: continue
        intervalos = [(datas[i] - datas[i-1]).days for i in range(1, len(datas))]
        media_habito = sum(intervalos) / len(intervalos)
        dias_sem_comprar = (hoje - datas[-1]).days
        if dias_sem_comprar > (media_habito * 1.2) and dias_sem_comprar > 7:
            saude_base_todos.append({'codigo': cod, 'nome': info['nome'], 'media_habito': round(media_habito), 'dias_sem_comprar': dias_sem_comprar, 'atraso': round(dias_sem_comprar - media_habito), 'ultima_data': datas[-1].strftime('%d/%m/%Y')})
    saude_base_todos = sorted(saude_base_todos, key=lambda x: x['atraso'], reverse=True)
    total_clientes_risco = len(saude_base_todos)
    total_clientes_analisados = len(dados_habito)
    saude_base = saude_base_todos[:15]

    dados_grafico = vendas_qs.values('Emissao').annotate(total_dia=Sum('Total')).order_by('Emissao')
    l_diario = [d['Emissao'].strftime('%d/%m') for d in dados_grafico]
    v_diario = [float(d['total_dia']) for d in dados_grafico]

    # Wishlist com isolamento por empresa e filtro correto
    itens_pendentes = ItemPedidoIgnorado.objects.filter(
        notificado=False,
        descartado_pelo_cliente=False,
        motivo_erro__icontains="estoque"
    ).select_related('cliente', 'cliente__client_state')
    if empresa:
        itens_pendentes = itens_pendentes.filter(cliente__empresa=empresa)

    oportunidades_wishlist = {}
    codigos_pendentes = itens_pendentes.values_list('codigo_produto', flat=True).distinct()
    produtos_qs = Product.objects.filter(product_code__in=codigos_pendentes)
    if empresa:
        produtos_qs = produtos_qs.filter(empresa=empresa)
    produtos_dict = {p.product_code: p for p in produtos_qs}

    for item in itens_pendentes:
        produto = produtos_dict.get(item.codigo_produto)
        if not produto or not item.cliente: continue
        estado = item.cliente.client_state.uf_name
        preco_atual = getattr(produto, 'product_value_sp' if estado == 'SP' else 'product_value_es')
        if preco_atual and preco_atual > 0:
            c_id = item.cliente.client_id
            if c_id not in oportunidades_wishlist:
                oportunidades_wishlist[c_id] = {'cliente': item.cliente, 'produtos': []}
            prods = oportunidades_wishlist[c_id]['produtos']
            existing = next((p for p in prods if p['codigo'] == produto.product_code), None)
            if existing:
                existing['quantidade'] += item.quantidade_tentada or 0
            else:
                prods.append({
                    'codigo': produto.product_code,
                    'descricao': produto.product_description,
                    'preco': float(preco_atual),
                    'quantidade': item.quantidade_tentada or 0,
                    'data': item.data_tentativa,
                })

    itens_notificados = ItemPedidoIgnorado.objects.filter(
        notificado=True,
        data_notificacao__year=ano_selecionado,
        data_notificacao__month=mes_selecionado
    ).select_related('cliente')
    if empresa:
        itens_notificados = itens_notificados.filter(cliente__empresa=empresa)

    total_recuperado_reais = Decimal('0.00')
    qtd_itens_recuperados = 0

    if itens_notificados.exists():
        data_inicio_busca = date(ano_selecionado, mes_selecionado, 1)
        data_fim_busca = data_inicio_busca + timedelta(days=45)
        vendas_base_cruzamento = _empresa(VendaReal.objects.filter(
            Emissao__range=(data_inicio_busca, data_fim_busca)
        )).values('Codigo_Cliente', 'Produto_Codigo', 'Emissao', 'Total')
        vendas_erp_memoria = {}
        for v in vendas_base_cruzamento:
            chave = (str(v['Codigo_Cliente']), str(v['Produto_Codigo']))
            if chave not in vendas_erp_memoria: vendas_erp_memoria[chave] = []
            vendas_erp_memoria[chave].append({'data': v['Emissao'], 'total': v['Total']})

        for item in itens_notificados:
            if item.cliente and item.data_notificacao:
                codigo_cli = str(item.cliente.client_code)
                codigo_prod = str(item.codigo_produto)
                data_aviso = item.data_notificacao.date()
                data_limite = data_aviso + timedelta(days=15)
                chave_busca = (codigo_cli, codigo_prod)
                if chave_busca in vendas_erp_memoria:
                    vendas_validas = [compra['total'] for compra in vendas_erp_memoria[chave_busca] if data_aviso <= compra['data'] <= data_limite]
                    if vendas_validas:
                        total_recuperado_reais += sum(vendas_validas)
                        qtd_itens_recuperados += 1

    recuperado_formatado = "{:,.2f}".format(float(total_recuperado_reais)).replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        'total_vendas': total_vendas_str, 'ticket_medio': ticket_medio_formatado,
        'total_itens_faturados': total_itens, 'total_pedidos_reais': total_pedidos,
        'media_diaria': media_diaria_str, 'projecao_final': projecao_final_str, 'progresso_mes': progresso_percentual,
        'variacao_mes': variacao_mes,
        'top_produtos': top_produtos_formatados, 'top_clientes': top_clientes_formatados, 'clientes_inativos': clientes_alerta,
        'labels_diario': json.dumps(l_diario), 'valores_diario': json.dumps(v_diario),
        'labels_semana': json.dumps(dias_nomes), 'valores_semana': json.dumps(vendas_por_dia),
        'ranking_logistica_dia': ranking_logistica_dia, 'saude_base': saude_base,
        'total_clientes_risco': total_clientes_risco, 'total_clientes_analisados': total_clientes_analisados,
        'mes_atual': mes_selecionado, 'ano_atual': ano_selecionado, 'lista_anos': range(hoje.year - 2, hoje.year + 1),
        'oportunidades_wishlist': list(oportunidades_wishlist.values()),
        'total_recuperado_reais': recuperado_formatado, 'qtd_itens_recuperados': qtd_itens_recuperados,
        'total_sp': float(total_sp), 'total_es': float(total_es),
        'total_sp_fmt': "{:,.2f}".format(float(total_sp)).replace(",", "X").replace(".", ",").replace("X", "."),
        'total_es_fmt': "{:,.2f}".format(float(total_es)).replace(",", "X").replace(".", ",").replace("X", "."),
        'valores_estados': json.dumps([float(total_sp), float(total_es)]),
        'rfm': calcular_rfm(empresa=empresa),
    }

# ====================================================================
# 2. ANÁLISE RFM (Recência, Frequência, Valor)
# ====================================================================

def calcular_rfm(empresa=None):
    """
    Calcula RFM dos últimos 12 meses e classifica cada cliente em um segmento.
    Retorna dict com a lista de clientes e os totais por segmento.
    """
    import bisect

    hoje = date.today()
    data_inicio = hoje - timedelta(days=365)

    vendas_qs = VendaReal.objects.filter(Emissao__gte=data_inicio)
    if empresa:
        vendas_qs = vendas_qs.filter(empresa=empresa)

    dados = list(
        vendas_qs
        .values('Codigo_Cliente', 'cliente_nome')
        .annotate(
            ultima_compra=Max('Emissao'),
            frequencia=Count('Pedido', distinct=True),
            monetario=Sum('Total'),
        )
    )

    if not dados:
        return {'clientes': [], 'segmentos': {}, 'segmentos_json': '{}', 'total': 0}

    # Calcula recência em dias
    for c in dados:
        c['recencia_dias'] = (hoje - c['ultima_compra']).days

    # Scoring por quintil (1-5) usando posição relativa
    def _scores(values, reverse=False):
        unique_sorted = sorted(set(values))
        n = len(unique_sorted)
        result = {}
        for v in unique_sorted:
            pos = bisect.bisect_left(unique_sorted, v)
            pct = pos / (n - 1) if n > 1 else 0.5
            score = round(pct * 4) + 1   # 1..5
            result[v] = (6 - score) if reverse else score
        return result

    r_map = _scores([c['recencia_dias'] for c in dados], reverse=True)  # menos dias = melhor
    f_map = _scores([c['frequencia']    for c in dados])
    m_map = _scores([float(c['monetario']) for c in dados])

    # Definição dos 5 segmentos — cada um com ação clara
    SEGMENTOS = {
        'Campeão':     {'cor': '#10b981', 'bg': '#d1fae5', 'acao': 'Fidelize e recompense'},
        'Fiel':        {'cor': '#3b82f6', 'bg': '#dbeafe', 'acao': 'Venda mais, cross-sell'},
        'Potencial':   {'cor': '#8b5cf6', 'bg': '#ede9fe', 'acao': 'Converta em recorrente'},
        'Em Risco':    {'cor': '#f59e0b', 'bg': '#fef3c7', 'acao': 'Ligar hoje — risco real de perda'},
        'Adormecido':  {'cor': '#6b7280', 'bg': '#f3f4f6', 'acao': 'Última tentativa de reativação'},
    }

    def _segmento(r, f, m):
        if r >= 4 and f >= 3 and m >= 3:
            return 'Campeão'
        if f >= 3 and m >= 2:
            return 'Fiel'
        if r >= 4 and f <= 2:
            return 'Potencial'
        if r <= 2 and f >= 3:
            return 'Em Risco'
        return 'Adormecido'

    _fmt = lambda v: "{:,.2f}".format(float(v)).replace(",", "X").replace(".", ",").replace("X", ".")

    clientes = []
    contagem_seg = {k: 0 for k in SEGMENTOS}

    for c in dados:
        r = r_map[c['recencia_dias']]
        f = f_map[c['frequencia']]
        m = m_map[float(c['monetario'])]
        seg = _segmento(r, f, m)
        contagem_seg[seg] += 1
        clientes.append({
            'codigo':        c['Codigo_Cliente'],
            'nome':          c['cliente_nome'] or 'Desconhecido',
            'recencia':      c['recencia_dias'],
            'frequencia':    c['frequencia'],
            'monetario':     float(c['monetario']),
            'monetario_fmt': _fmt(c['monetario']),
            'ultima_compra': c['ultima_compra'].strftime('%d/%m/%Y'),
            'r_score':       r,
            'f_score':       f,
            'm_score':       m,
            'rfm_score':     r + f + m,
            'segmento':      seg,
            'cor':           SEGMENTOS[seg]['cor'],
            'bg':            SEGMENTOS[seg]['bg'],
            'acao':          SEGMENTOS[seg]['acao'],
        })

    clientes.sort(key=lambda x: x['rfm_score'], reverse=True)

    segmentos_completos = {
        k: {'count': contagem_seg[k], **v}
        for k, v in SEGMENTOS.items()
    }

    return {
        'clientes':       clientes,
        'segmentos':      segmentos_completos,
        'segmentos_json': json.dumps({k: v['count'] for k, v in segmentos_completos.items()}),
        'total':          len(clientes),
    }


# ====================================================================
# 3. HISTÓRICO RFM — leitura de snapshots mensais
# ====================================================================

ORDEM_SEGMENTO = {
    'Campeão': 5, 'Fiel': 4, 'Potencial': 3, 'Em Risco': 2, 'Adormecido': 1,
}
COR_SEGMENTO = {
    'Campeão':    {'cor': '#10b981', 'bg': '#d1fae5'},
    'Fiel':       {'cor': '#3b82f6', 'bg': '#dbeafe'},
    'Potencial':  {'cor': '#8b5cf6', 'bg': '#ede9fe'},
    'Em Risco':   {'cor': '#f59e0b', 'bg': '#fef3c7'},
    'Adormecido': {'cor': '#6b7280', 'bg': '#f3f4f6'},
}


def calcular_historico_rfm(empresa=None, meses=6):
    """
    Lê os snapshots mensais e retorna:
      - datas: lista de date (1º de cada mês), mais recente à direita
      - clientes: lista de dicts com histórico de segmentos
      - migracao: contagem de clientes que melhoraram / pioraram / estáveis
      - total_por_mes: count de clientes por mês
      - tem_dados: bool
    """
    hoje = date.today()

    # Datas de referência desejadas (últimos N meses fechados)
    datas = []
    for i in range(meses - 1, -1, -1):
        ano  = (hoje.replace(day=1) - timedelta(days=i * 28)).year
        mes  = (hoje.replace(day=1) - timedelta(days=i * 28)).month
        datas.append(date(ano, mes, 1))
    # Garante datas únicas e ordenadas
    datas = sorted(set(datas))[-meses:]

    qs = SnapshotRFM.objects.filter(data_ref__in=datas)
    if empresa:
        qs = qs.filter(empresa=empresa)
    qs = qs.order_by('cod_cliente', 'data_ref')

    if not qs.exists():
        return {'tem_dados': False, 'datas': datas, 'clientes': [], 'migracao': {}, 'total_por_mes': {}}

    # Agrupa por cliente
    por_cliente = {}
    for snap in qs:
        cod = snap.cod_cliente
        if cod not in por_cliente:
            por_cliente[cod] = {'codigo': cod, 'nome': snap.nome_cliente, 'meses': {}}
        por_cliente[cod]['meses'][snap.data_ref] = {
            'segmento':  snap.segmento,
            'rfm_score': snap.rfm_score,
            'cor':       COR_SEGMENTO.get(snap.segmento, {}).get('cor', '#9ca3af'),
            'bg':        COR_SEGMENTO.get(snap.segmento, {}).get('bg', '#f3f4f6'),
        }

    # Calcula tendência comparando primeiro vs último mês disponível
    melhoraram = pioraram = estaveis = 0
    clientes = []
    for c in por_cliente.values():
        meses_presentes = [d for d in datas if d in c['meses']]
        if len(meses_presentes) >= 2:
            seg_ini  = ORDEM_SEGMENTO.get(c['meses'][meses_presentes[0]]['segmento'], 0)
            seg_fim  = ORDEM_SEGMENTO.get(c['meses'][meses_presentes[-1]]['segmento'], 0)
            delta = seg_fim - seg_ini
            if delta > 0:
                tendencia = 'melhorou'
                melhoraram += 1
            elif delta < 0:
                tendencia = 'piorou'
                pioraram += 1
            else:
                tendencia = 'estavel'
                estaveis += 1
        else:
            tendencia = 'novo'

        # Segmento atual (último mês disponível)
        ultimo = c['meses'].get(meses_presentes[-1]) if meses_presentes else None
        c['tendencia']       = tendencia
        c['segmento_atual']  = ultimo['segmento'] if ultimo else '—'
        c['cor_atual']       = ultimo['cor']       if ultimo else '#9ca3af'
        c['bg_atual']        = ultimo['bg']        if ultimo else '#f3f4f6'
        clientes.append(c)

    # Ordena: piorou primeiro (mais urgente), depois por segmento atual
    _ordem_tend = {'piorou': 0, 'estavel': 1, 'melhorou': 2, 'novo': 3}
    clientes.sort(key=lambda c: (
        _ordem_tend.get(c['tendencia'], 9),
        -ORDEM_SEGMENTO.get(c['segmento_atual'], 0),
    ))

    total_por_mes = {}
    for d in datas:
        total_por_mes[d] = sum(1 for c in clientes if d in c['meses'])

    return {
        'tem_dados':    True,
        'datas':        datas,
        'clientes':     clientes,
        'migracao':     {'melhoraram': melhoraram, 'pioraram': pioraram, 'estaveis': estaveis},
        'total_por_mes': total_por_mes,
        'segmentos_disponiveis': list(COR_SEGMENTO.keys()),
    }


# ====================================================================
# 4. EVOLUÇÃO DE CLIENTES (com suporte a períodos customizados)
# ====================================================================

PERIODOS_EVOLUCAO = {
    'ytd':  'Início do Ano',
    '3m':   'Últimos 3 meses',
    '6m':   'Últimos 6 meses',
    '12m':  'Últimos 12 meses',
}


def _intervalo_periodo(periodo, ano=None):
    """Retorna (data_inicio, data_fim) para o período selecionado."""
    hoje = date.today()
    if ano is not None:
        # Ano específico: Jan 1 → Dez 31 (ou hoje se for o ano atual)
        fim = hoje if ano == hoje.year else date(ano, 12, 31)
        return date(ano, 1, 1), fim
    if periodo == 'ytd':
        # Início do ano até hoje — comparação com mesmo período do ano anterior
        return date(hoje.year, 1, 1), hoje
    if periodo == '3m':
        return (hoje.replace(day=1) - timedelta(days=2 * 28)).replace(day=1), hoje
    if periodo == '6m':
        return (hoje.replace(day=1) - timedelta(days=5 * 28)).replace(day=1), hoje
    # default: 12m
    return (hoje.replace(day=1) - timedelta(days=11 * 28)).replace(day=1), hoje


def calcular_evolucao_clientes(empresa=None, ano=None, periodo='ytd'):
    """
    Retorna a evolução mensal de compras por cliente.

    Modos:
      - ano=YYYY          → ano completo (mantém compatibilidade)
      - periodo='ytd'     → 1/Jan do ano atual até hoje
      - periodo='3m'/'6m'/'12m' → janela deslizante

    Comparação: mesmo intervalo de datas, deslocado 1 ano atrás.
    """
    from django.db.models.functions import ExtractMonth

    data_ini, data_fim = _intervalo_periodo(periodo, ano)
    # Período de comparação: 1 ano atrás
    from dateutil.relativedelta import relativedelta
    data_ini_ant = data_ini - relativedelta(years=1)
    data_fim_ant = data_fim - relativedelta(years=1)

    qs_base = VendaReal.objects.all()
    if empresa:
        qs_base = qs_base.filter(empresa=empresa)

    # Meses do período selecionado
    meses_periodo = set()
    cur = data_ini.replace(day=1)
    while cur <= data_fim:
        meses_periodo.add(cur.month)
        cur = (cur + timedelta(days=32)).replace(day=1)
    meses_periodo = sorted(meses_periodo)

    # Vendas do período atual — agrega por cliente + mês
    vendas_atual = (
        qs_base
        .filter(Emissao__gte=data_ini, Emissao__lte=data_fim)
        .values('Codigo_Cliente', 'cliente_nome')
        .annotate(mes=ExtractMonth('Emissao'), total_mes=Sum('Total'))
        .order_by('Codigo_Cliente', 'mes')
    )

    # Vendas do período de comparação — total por cliente
    vendas_ant = (
        qs_base
        .filter(Emissao__gte=data_ini_ant, Emissao__lte=data_fim_ant)
        .values('Codigo_Cliente')
        .annotate(total_ant=Sum('Total'))
    )
    total_ant_por_cliente = {v['Codigo_Cliente']: v['total_ant'] for v in vendas_ant}

    # Monta estrutura por cliente
    clientes_dict = {}
    for row in vendas_atual:
        cod = row['Codigo_Cliente']
        if cod not in clientes_dict:
            clientes_dict[cod] = {
                'codigo': cod,
                'nome': row['cliente_nome'] or f'Cliente {cod}',
                'meses': {m: Decimal('0') for m in range(1, 13)},
            }
        clientes_dict[cod]['meses'][row['mes']] += row['total_mes'] or Decimal('0')

    meses_com_dados = set()
    totais_mensais = {m: Decimal('0') for m in range(1, 13)}

    clientes = []
    for cod, c in clientes_dict.items():
        meses_ativos = [m for m in meses_periodo if c['meses'][m] > 0]
        total_periodo = sum(c['meses'][m] for m in meses_periodo)
        total_ant = total_ant_por_cliente.get(cod, Decimal('0')) or Decimal('0')

        # Variação vs ano anterior
        if total_ant > 0:
            variacao_ext = float((total_periodo - total_ant) / total_ant * 100)
        elif total_periodo > 0:
            variacao_ext = 100.0
        else:
            variacao_ext = 0.0

        # Crescimento interno: primeiro mês ativo → último mês ativo no período
        if len(meses_ativos) >= 2:
            val_primeiro = c['meses'][meses_ativos[0]]
            val_ultimo   = c['meses'][meses_ativos[-1]]
            if val_primeiro > 0:
                variacao_int = float((val_ultimo - val_primeiro) / val_primeiro * 100)
            else:
                variacao_int = 0.0
        elif len(meses_ativos) == 1:
            variacao_int = 0.0  # só um mês, sem tendência interna
        else:
            variacao_int = 0.0

        tendencia_ext = ('crescendo' if variacao_ext >= 10
                         else 'caindo' if variacao_ext <= -10
                         else 'estavel')
        tendencia_int = ('crescendo' if variacao_int >= 10
                         else 'caindo' if variacao_int <= -10
                         else 'estavel')

        for m, v in c['meses'].items():
            if v > 0:
                meses_com_dados.add(m)
                totais_mensais[m] += v

        clientes.append({
            'codigo':       cod,
            'nome':         c['nome'],
            'meses':        c['meses'],
            'total_ano':    total_periodo,
            'total_ant':    total_ant,
            'variacao_pct': variacao_ext,   # vs ano anterior
            'variacao_int': variacao_int,   # crescimento interno no período
            'tendencia':    tendencia_ext,
            'tendencia_int': tendencia_int,
            'tem_historico': total_ant > 0,
        })

    clientes.sort(key=lambda x: x['total_ano'], reverse=True)

    # Mostrar apenas meses que pertencem ao período E têm dados
    meses_exibir = sorted(meses_com_dados & set(meses_periodo)) if meses_com_dados else meses_periodo

    label_periodo = (
        f'{data_ini.year}' if ano is not None
        else PERIODOS_EVOLUCAO.get(periodo, periodo)
    )
    label_comparacao = (
        f'{data_ini_ant.strftime("%b/%y")} – {data_fim_ant.strftime("%b/%y")}'
    )

    return {
        'clientes':         clientes,
        'meses_com_dados':  meses_exibir,
        'totais_mensais':   totais_mensais,
        'ano':              data_ini.year,
        'ano_anterior':     data_ini_ant.year,
        'total_geral':      sum(totais_mensais[m] for m in meses_exibir),
        'label_periodo':    label_periodo,
        'label_comparacao': label_comparacao,
        'data_ini':         data_ini,
        'data_fim':         data_fim,
    }


# ====================================================================
# 4. FUNÇÃO DE EXPORTAÇÃO EXCEL DE VENDAS REAIS
# ====================================================================
def gerar_excel_vendas_reais(filtro_pedido, filtro_produto, filtro_cliente, filtro_mes, filtro_ano):
    vendas_qs = VendaReal.objects.all().order_by('-Emissao')

    if filtro_pedido:
        vendas_qs = vendas_qs.filter(Pedido__icontains=filtro_pedido)
    if filtro_produto:
        vendas_qs = vendas_qs.filter(Q(Produto_Codigo__icontains=filtro_produto) | Q(Produto_Descricao__icontains=filtro_produto))
    if filtro_cliente:
        vendas_qs = vendas_qs.filter(Q(cliente_nome__icontains=filtro_cliente) | Q(Codigo_Cliente__icontains=filtro_cliente))
    if filtro_mes and filtro_mes.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__month=int(filtro_mes))
    if filtro_ano and filtro_ano.isdigit():
        vendas_qs = vendas_qs.filter(Emissao__year=int(filtro_ano))

    data = []
    for v in vendas_qs:
        data.append({
            'Emissão': v.Emissao.strftime('%d/%m/%Y'),
            'Pedido ERP': v.Pedido,
            'Cód. Cliente': v.Codigo_Cliente,
            'Cliente': v.cliente_nome,
            'Cód. Produto': v.Produto_Codigo,
            'Descrição': v.Produto_Descricao,
            'Quantidade': v.Quantidade,
            'Unitário': float(v.Unitario),
            'Total': float(v.Total),
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Vendas Reais')
    output.seek(0)

    periodo_str = f"_{filtro_ano}_{filtro_mes}" if filtro_ano and filtro_mes else ""
    filename = f"vendas_reais{periodo_str}_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return output, filename

# ====================================================================
# 3. FUNÇÃO DE PROCESSAMENTO DE STATUS PDF
# ====================================================================

def processar_status_pdf(pdf_file, empresa=None):
    import re
    from datetime import datetime
    import pdfplumber
    from django.db import transaction
    from .models import StatusPedidoERP, Pedido

    MAP_SINC_STATUS = {
        '4-BLOQUEADO SEPARAÇÃO': 'SEPARACAO',
        '6-PRONTO PARA FATURAR': 'EXPEDICAO',
        '8-FATURADO': 'FINALIZADO',
        '2-BLOQUEADO CRÉDITO': 'FINANCEIRO',
        '1-BLOQUEADO PREÇO': 'PRECO',
    }

    pedidos_unicos = {}

    with pdfplumber.open(pdf_file) as pdf:
        
        # Limite 220 isola o Vendedor perfeitamente
        limite_cliente_x = 220
        
        primeira_pagina = pdf.pages[0]
        for w in primeira_pagina.extract_words():
            if w['text'].upper().startswith('CLIENTE'):
                limite_cliente_x = w['x0'] - 5
                break

        for pagina in pdf.pages:
            palavras = pagina.extract_words()
            if not palavras: continue

            # Descobre onde cada pedido começa pelo eixo Y
            y_inicios = []
            for w in palavras:
                if re.match(r'^\d{2}/\d{2}/\d{4}$', w['text']) and w['x0'] < 100:
                    y_inicios.append(w['top'])

            if not y_inicios: continue
            
            y_inicios = sorted(list(set([round(y / 4) * 4 for y in y_inicios])))

            for i in range(len(y_inicios)):
                y_start = y_inicios[i] - 4
                y_end = y_inicios[i+1] - 4 if i < len(y_inicios) - 1 else y_start + 100

                palavras_pedido = [w for w in palavras if y_start <= w['top'] < y_end]
                if not palavras_pedido: continue

                # A CAIXA MÁGICA: Esquerda (Data/Num) e Direita (Todo o resto sem Vendedor)
                esquerda = [w for w in palavras_pedido if w['x0'] < 120]
                direita = [w for w in palavras_pedido if w['x0'] >= limite_cliente_x]

                def extrair(coluna_words):
                    cw_sorted = sorted(coluna_words, key=lambda w: (round(w['top']/4)*4, w['x0']))
                    return " ".join([w['text'] for w in cw_sorted]).upper()

                str_esq = extrair(esquerda)
                str_dir = extrair(direita)

                # --- 1. EXTRAI DATA E NÚMERO ---
                match_esq = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{4,6})', str_esq)
                if not match_esq: continue
                    
                data_str = match_esq.group(1)
                numero_pedido = match_esq.group(2)
                
                if numero_pedido in pedidos_unicos: continue

                # --- 2. LIMPEZA DE CABEÇALHOS VAZADOS ---
                for lixo in ['CLIENTE', 'ÚLTIMA ATUALIZAÇÃO', 'ULTIMA ATUALIZACAO', 'SITUAÇÃO', 'SITUACAO', 'EXPEDIDO?', 'PÁGINA']:
                    str_dir = str_dir.replace(lixo, '')

                # --- 3. DETECTOR DE STATUS BLINDADO (Agora pega os sinais de "=" e "-") ---
                status_pdf = "Status não identificado"
                if re.search(r'8\s*[-=]|FATUR|FALUR', str_dir): status_pdf = '8-Faturado'
                elif re.search(r'6\s*[-=]|PRONTO', str_dir): status_pdf = '6-Pronto para Faturar'
                elif re.search(r'4\s*[-=]|SEPARA|EPARA', str_dir): status_pdf = '4-Bloqueado Separação'
                elif re.search(r'1\s*[-=]|PREÇO|PRECO', str_dir): status_pdf = '1-Bloqueado Preço'
                elif re.search(r'2\s*[-=]|CRÉD|CRED|CREA', str_dir): status_pdf = '2-Bloqueado Crédito'

                # --- 4. IDENTIFICA EXPEDIDO ---
                expedido = False
                if re.search(r'\b(SIM|SIRM|SI)\b', str_dir):
                    expedido = True

                # --- 5. APAGA O RELÓGIO (Data de Atualização) ---
                str_dir = re.sub(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', '', str_dir)

                # --- 6. EXTRAI CÓDIGO E NOME ---
                str_cli = " ".join(str_dir.split()) 
                matches = re.match(r'^(\d{1,6})\s*[-–—=]\s*(.*)', str_cli)
                if matches:
                    cod_c = matches.group(1).strip()
                    nome_c = matches.group(2).strip()
                else:
                    cod_c = ""
                    nome_c = str_cli.strip()

                # --- 7. A GUILHOTINA ABSOLUTA (Limpeza Perfeita) ---
                # Remove "SIM" ou "NÃO" isolado no fim da linha
                nome_c = re.sub(r'\s*\b(SIM|NAO|NÃO|SIRM|SI)\b\s*$', '', nome_c).strip()
                
                # Deleta da string tudo o que estiver do Código de Status para a direita!
                padrao_guilhotina = r'\s*(?:[12468]\s*[-=]\s*(?:FATUR|FALUR|PRONT|BLOQU|SEPAR|CR[EÉ]D|PRE[CÇ])|FATURADO|FALURADO|PRONTO PARA|BLOQUEADO SEPARA|BLOQUEADO PRE|BLOQUEADO CR[EÉ]D|EPARA[CÇ]).*$'
                nome_c = re.sub(padrao_guilhotina, '', nome_c).strip()

                # Mais um passe rápido pra garantir que o "NÃO" não ficou sozinho
                nome_c = re.sub(r'\s*\b(SIM|NAO|NÃO|SIRM|SI)\b\s*$', '', nome_c).strip()

                pedidos_unicos[numero_pedido] = {
                    'emissao': datetime.strptime(data_str, '%d/%m/%Y').date(),
                    'numero_pedido': numero_pedido,
                    'cod_cliente': cod_c,
                    'nome_cliente': nome_c[:255],
                    'situacao': status_pdf,
                    'expedido': expedido
                }

    novos_status_preparados = list(pedidos_unicos.values())

    if novos_status_preparados:
        with transaction.atomic():
            for data in novos_status_preparados:
                StatusPedidoERP.objects.filter(numero_pedido=data['numero_pedido']).delete()
                StatusPedidoERP.objects.create(**data, empresa=empresa)

                pedido_site = Pedido.objects.filter(id=data['numero_pedido']).first()
                if pedido_site:
                    novo_status_interno = MAP_SINC_STATUS.get(data['situacao'])
                    if novo_status_interno:
                        pedido_site.status = novo_status_interno
                        pedido_site.save(update_fields=['status'])

    return len(novos_status_preparados)



def processar_giro_cliente(cliente_code):
    """
    Calcula sugestões de compra para um cliente com base no histórico ERP (VendaReal).
    v2 — Melhorias:
      - Mínimo de 3 compras distintas para gerar sugestão
      - Score de consistência via coeficiente de variação dos intervalos
      - Threshold dinâmico: produtos consistentes disparam mais tarde (90%), irregulares mais cedo (70%)
      - Tendência de consumo: compara últimos 3 meses vs 3 meses anteriores
      - Sazonalidade: bônus de 20% se o cliente comprou muito esse produto nesse mesmo mês no ano passado
    """
    hoje = date.today()
    data_corte = hoje - timedelta(days=180)   # janela de 6 meses
    data_meio = hoje - timedelta(days=90)     # marco para cálculo de tendência

    # 1. Busca o cliente
    cliente = WfClient.objects.filter(client_code=cliente_code).select_related('client_state').first()
    if not cliente:
        return []

    estado_cliente = cliente.client_state.uf_name if cliente.client_state else 'SP'

    # 2. Uma única query com todos os registros individuais do cliente nos últimos 6 meses
    vendas_individuais = VendaReal.objects.filter(
        Codigo_Cliente=cliente_code,
        Emissao__gte=data_corte
    ).values('Produto_Codigo', 'Quantidade', 'Emissao').order_by('Produto_Codigo', 'Emissao')

    # 3. Sazonalidade: mesmo mês do ano passado
    vendas_mesmo_mes = VendaReal.objects.filter(
        Codigo_Cliente=cliente_code,
        Emissao__month=hoje.month,
        Emissao__year=hoje.year - 1
    ).values('Produto_Codigo').annotate(qtd_mesmo_mes=Sum('Quantidade'))
    mapa_sazonalidade = {v['Produto_Codigo']: v['qtd_mesmo_mes'] for v in vendas_mesmo_mes}

    # 4. Agrupa em Python por produto
    dados_por_produto = {}
    for v in vendas_individuais:
        cod = v['Produto_Codigo']
        if cod not in dados_por_produto:
            dados_por_produto[cod] = {'datas': [], 'qtd_total': 0, 'qtd_recente': 0, 'qtd_antiga': 0}
        dados_por_produto[cod]['datas'].append(v['Emissao'])
        dados_por_produto[cod]['qtd_total'] += v['Quantidade']
        if v['Emissao'] >= data_meio:
            dados_por_produto[cod]['qtd_recente'] += v['Quantidade']
        else:
            dados_por_produto[cod]['qtd_antiga'] += v['Quantidade']

    # 5. Busca catálogo de uma vez
    produtos_catalogo = Product.objects.filter(
        product_code__in=list(dados_por_produto.keys())
    ).in_bulk(field_name='product_code')

    novas_sugestoes = []

    for codigo, dados in dados_por_produto.items():
        # Datas únicas e ordenadas (uma por dia de compra)
        datas = sorted(set(dados['datas']))
        qtd_pedidos = len(datas)

        # Mínimo de 3 compras distintas
        if qtd_pedidos < 3:
            continue

        # Validação catálogo e estoque
        produto_obj = produtos_catalogo.get(codigo)
        if not produto_obj:
            continue

        preco = produto_obj.product_value_sp if estado_cliente == 'SP' else produto_obj.product_value_es
        if not preco or preco <= 0:
            continue

        # Intervalos entre compras consecutivas
        intervalos = [(datas[i] - datas[i - 1]).days for i in range(1, len(datas))]
        intervalo_medio = sum(intervalos) / len(intervalos)
        if intervalo_medio <= 0:
            continue

        # Score de consistência via coeficiente de variação (CV = desvio/média)
        # CV baixo = padrão regular; CV alto = padrão caótico
        if len(intervalos) >= 2:
            desvio = statistics.stdev(intervalos)
            cv = desvio / intervalo_medio
        else:
            cv = 0.5  # moderado quando só há 2 intervalos
        consistencia = max(0.0, 1.0 - cv)  # 1.0 = perfeito, 0.0 = caótico

        # Threshold dinâmico: produto consistente espera mais para sugerir
        if consistencia > 0.7:
            threshold = 0.90
        elif consistencia > 0.4:
            threshold = 0.80
        else:
            threshold = 0.70

        dias_sem_comprar = (hoje - datas[-1]).days
        if dias_sem_comprar < (intervalo_medio * threshold):
            continue

        # Tendência de consumo: compara recente vs antigo
        if dados['qtd_antiga'] > 0:
            fator_tendencia = dados['qtd_recente'] / dados['qtd_antiga']
            fator_tendencia = max(0.5, min(2.0, fator_tendencia))  # limita entre 50% e 200%
        else:
            fator_tendencia = 1.0  # sem histórico antigo, neutro

        # Quantidade base: giro diário × intervalo médio
        intervalo_total_dias = (datas[-1] - datas[0]).days
        giro_diario = Decimal(str(dados['qtd_total'])) / Decimal(str(max(intervalo_total_dias, 1)))
        qtd_base = float(giro_diario) * float(intervalo_medio)

        # Aplica tendência + margem de segurança de 10%
        qtd_sugerida = int(qtd_base * fator_tendencia * 1.10)

        # Bônus de sazonalidade: se comprou muito nesse mês no ano passado, +20%
        qtd_sazonalidade = mapa_sazonalidade.get(codigo)
        if qtd_sazonalidade and qtd_sazonalidade > (qtd_base * 1.5):
            qtd_sugerida = int(qtd_sugerida * 1.20)

        # Score de relevância (0-100):
        # Urgência (50 pts): quanto mais atrasado, maior a urgência
        urgency_ratio = dias_sem_comprar / intervalo_medio
        urgency_score = min(50, int(urgency_ratio * 40))
        # Consistência (30 pts): padrão regular = sugestão mais confiável
        consistency_score = int(consistencia * 30)
        # Tendência (20 pts): consumo crescente = maior relevância
        trend_score = int(min(20, max(0, (fator_tendencia - 0.5) * 20)))
        score_relevancia = min(100, urgency_score + consistency_score + trend_score)

        novas_sugestoes.append(
            SugestaoCompraERP(
                cliente=cliente,
                produto_codigo=codigo,
                produto_descricao=produto_obj.product_description,
                giro_diario=giro_diario,
                intervalo_medio_dias=int(intervalo_medio),
                ultima_compra=datas[-1],
                quantidade_sugerida=max(qtd_sugerida, 1),
                score_relevancia=score_relevancia,
            )
        )

    # Salva atomicamente: apaga sugestões antigas e insere as novas
    with transaction.atomic():
        SugestaoCompraERP.objects.filter(cliente=cliente).delete()
        if novas_sugestoes:
            SugestaoCompraERP.objects.bulk_create(novas_sugestoes, batch_size=500)

    return novas_sugestoes





'''def processar_status_pdf(pdf_file):
    import re
    from datetime import datetime
    import pdfplumber
    from django.db import transaction
    from .models import StatusPedidoERP, Pedido

    MAP_SINC_STATUS = {
        '4-BLOQUEADO SEPARAÇÃO': 'SEPARACAO',
        '6-PRONTO PARA FATURAR': 'EXPEDICAO',
        '8-FATURADO': 'FINALIZADO',
        '2-BLOQUEADO CRÉDITO': 'FINANCEIRO',
        '1-BLOQUEADO PREÇO': 'PRECO',
    }

    pedidos_unicos = {}

    with pdfplumber.open(pdf_file) as pdf:
        # Limites X baseados no layout padrão da folha A4 em paisagem
        # [Emissão, Número, Vendedor, Cliente, Última Atu., Situação, Expedido, Fim]
        limites = [0, 60, 120, 220, 500, 620, 720, 9999]
        
        # Tenta descobrir os limites dinamicamente lendo o cabeçalho
        primeira_pagina = pdf.pages[0]
        palavras_header = primeira_pagina.extract_words()
        headers = {}
        for w in palavras_header:
            t = w['text'].upper()
            if t.startswith('EMISS'): headers['emissao'] = w['x0'] - 5
            elif t.startswith('NÚMER') or t.startswith('NUMER'): headers['numero'] = w['x0'] - 5
            elif t.startswith('VENDEDOR'): headers['vendedor'] = w['x0'] - 5
            elif t.startswith('CLIENTE'): headers['cliente'] = w['x0'] - 5
            elif t.startswith('ÚLTIMA') or t.startswith('ULTIMA'): headers['ultima'] = w['x0'] - 5
            elif t.startswith('SITUAÇ') or t.startswith('SITUAC'): headers['situacao'] = w['x0'] - 5
            elif t.startswith('EXPEDIDO'): headers['expedido'] = w['x0'] - 5
        
        if len(headers) >= 5:
            limites = [
                headers.get('emissao', 0),
                headers.get('numero', 60),
                headers.get('vendedor', 120),
                headers.get('cliente', 220), # Corta o Vendedor fora perfeitamente
                headers.get('ultima', 500),
                headers.get('situacao', 620),
                headers.get('expedido', 720),
                9999
            ]

        for pagina in pdf.pages:
            palavras = pagina.extract_words()
            if not palavras: continue

            # Descobre onde cada pedido começa pelo eixo Y da Data na Coluna 1
            y_inicios = []
            for w in palavras:
                if re.match(r'^\d{2}/\d{2}/\d{4}$', w['text']) and w['x0'] < limites[1] + 10:
                    y_inicios.append(w['top'])

            if not y_inicios: continue
            # Agrupa linhas para evitar falhas de milímetros na impressão
            y_inicios = sorted(list(set([round(y / 4) * 4 for y in y_inicios])))

            for i in range(len(y_inicios)):
                y_start = y_inicios[i] - 4
                # A linha vai até o começo do próximo pedido, ou 100px para baixo se for o último
                y_end = y_inicios[i+1] - 4 if i < len(y_inicios) - 1 else y_start + 100

                # Pega todas as palavras deste pedido específico
                palavras_pedido = [w for w in palavras if y_start <= w['top'] < y_end]
                if not palavras_pedido: continue

                # Divide as palavras em caixas (Colunas) usando o eixo X da palavra
                cols = {1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[]}
                for w in palavras_pedido:
                    x = w['x0']
                    if x < limites[1]: cols[1].append(w)
                    elif x < limites[2]: cols[2].append(w)
                    elif x < limites[3]: cols[3].append(w)
                    elif x < limites[4]: cols[4].append(w)
                    elif x < limites[5]: cols[5].append(w)
                    elif x < limites[6]: cols[6].append(w)
                    else: cols[7].append(w)

                # Reconstrutor de texto: Ordena as palavras dentro da caixa
                def extrair(coluna_words):
                    cw_sorted = sorted(coluna_words, key=lambda w: (round(w['top']/4)*4, w['x0']))
                    return " ".join([w['text'] for w in cw_sorted]).upper()

                str_data = extrair(cols[1])
                str_num = extrair(cols[2])
                str_cli = extrair(cols[4])   # <-- MAGIA: Apenas palavras que caíram na coluna do Cliente
                str_sit = extrair(cols[6])
                str_exp = extrair(cols[7])

                match_data = re.search(r'(\d{2}/\d{2}/\d{4})', str_data)
                match_num = re.search(r'(\d{4,6})', str_num)
                
                if not match_data or not match_num: continue
                    
                data_str = match_data.group(1)
                numero_pedido = match_num.group(1)
                
                if numero_pedido in pedidos_unicos: continue

                # Como pegamos apenas a Coluna 4, o Vendedor (Charles) nem existe mais nesta string!
                # O Regex agora pega tudo o que vier depois do traço (.*) sem restrições.
                matches = re.findall(r'(\d{1,6})\s*[-–—=]\s*(.*)', str_cli)
                if matches:
                    cod_c = matches[-1][0]
                    nome_c = matches[-1][1].strip()
                else:
                    cod_c = ""
                    nome_c = str_cli.strip()

                # Limpeza de segurança caso a coluna da direita invada um pouco
                nome_c = re.sub(r'\b(SIM|NAO|NÃO|SIRM|SI)\b.*$', '', nome_c).strip()

                # Identificação de Status (pela Coluna 6)
                status_pdf = "Status não identificado"
                if '8' in str_sit or 'FATURADO' in str_sit: status_pdf = '8-Faturado'
                elif '6' in str_sit or 'PRONTO' in str_sit: status_pdf = '6-Pronto para Faturar'
                elif '4' in str_sit or 'EPARA' in str_sit: status_pdf = '4-Bloqueado Separação'
                elif '1' in str_sit or 'PRE' in str_sit: status_pdf = '1-Bloqueado Preço'
                elif '2' in str_sit or 'CRE' in str_sit or 'CRÉ' in str_sit: status_pdf = '2-Bloqueado Crédito'

                # Expedido (pela Coluna 7)
                expedido = 'SIM' in str_exp or 'SIRM' in str_exp or 'SI' in str_exp

                pedidos_unicos[numero_pedido] = {
                    'emissao': datetime.strptime(data_str, '%d/%m/%Y').date(),
                    'numero_pedido': numero_pedido,
                    'cod_cliente': cod_c,
                    'nome_cliente': nome_c[:255],
                    'situacao': status_pdf,
                    'expedido': expedido
                }

    novos_status_preparados = list(pedidos_unicos.values())

    if novos_status_preparados:
        with transaction.atomic():
            for data in novos_status_preparados:
                StatusPedidoERP.objects.filter(numero_pedido=data['numero_pedido']).delete()
                StatusPedidoERP.objects.create(**data)
                
                pedido_site = Pedido.objects.filter(id=data['numero_pedido']).first()
                if pedido_site:
                    novo_status_interno = MAP_SINC_STATUS.get(data['situacao'])
                    if novo_status_interno:
                        pedido_site.status = novo_status_interno
                        pedido_site.save(update_fields=['status'])
                        
    return len(novos_status_preparados)'''