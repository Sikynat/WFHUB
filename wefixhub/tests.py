"""
Suite de testes para o projeto WFHUB.

Cobertura:
  1. EmpresaMiddlewareTest   — request.empresa setado corretamente
  2. EmpresaIsolacaoTest     — staff/cliente de empresa A não vê dados de empresa B
  3. PermissaoAcessoTest     — rotas de staff bloqueadas para clientes e anônimos
  4. NotificacaoPedidoTest   — notificações criadas e marcadas como lidas
  5. TarefaTest              — CRUD de tarefas isolado por empresa
  6. ChecklistTest           — toggle e exclusão de itens de checklist
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import (
    Empresa, PerfilUsuario, WfClient, wefixhub_uf,
    Endereco, Pedido, Product,
    Tarefa, ChecklistItem, NotificacaoTarefa,
    NotificacaoPedido,
)


# ===========================================================================
# HELPERS DE FIXTURE
# ===========================================================================

def make_uf(nome='SP'):
    return wefixhub_uf.objects.get_or_create(uf_name=nome)[0]


def make_empresa(slug, nome=None):
    return Empresa.objects.create(
        nome=nome or slug,
        slug=slug,
        plano='PRO',
        ativo=True,
        acesso_permanente=True,
    )


def make_staff(username, empresa, password='senha123'):
    user = User.objects.create_user(username=username, password=password, is_staff=True)
    PerfilUsuario.objects.create(user=user, empresa=empresa, papel='ADMIN')
    return user


def make_cliente(username, empresa, uf, code=1, password='senha123'):
    user = User.objects.create_user(username=username, password=password, is_staff=False)
    client = WfClient.objects.create(
        user=user,
        empresa=empresa,
        client_code=code,
        client_name=username,
        client_cnpj='00000000000000',
        client_adress='Rua Teste',
        client_city='Cidade',
        client_state=uf,
        client_is_active=True,
    )
    return user, client


def make_endereco(wfclient, uf):
    return Endereco.objects.create(
        cliente=wfclient,
        logradouro='Rua Teste',
        numero='1',
        bairro='Centro',
        cidade='Cidade',
        estado=uf,
        cep='00000-000',
        is_default=True,
    )


def make_tarefa(empresa, criado_por, titulo='Tarefa Teste', status='A_FAZER'):
    return Tarefa.objects.create(
        empresa=empresa,
        titulo=titulo,
        status=status,
        prioridade='MEDIA',
        criado_por=criado_por,
    )


def make_pedido(cliente, empresa, endereco, status='PENDENTE'):
    return Pedido.objects.create(
        cliente=cliente,
        empresa=empresa,
        endereco=endereco,
        status=status,
        frete_option='CORREIOS',
        nota_fiscal='SEM',
        criado_por=None,
    )


# ===========================================================================
# 1. MIDDLEWARE — request.empresa
# ===========================================================================

class EmpresaMiddlewareTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa = make_empresa('emp-middleware')
        self.staff = make_staff('staff_mw', self.empresa)
        self.user_cliente, self.wfclient = make_cliente('cli_mw', self.empresa, self.uf, code=10)
        self.c = Client()

    def test_staff_tem_empresa_no_request(self):
        self.c.login(username='staff_mw', password='senha123')
        # Acessa qualquer página autenticada — o middleware roda em todo request
        response = self.c.get(reverse('home'), follow=True)
        # Se chegou sem erro e não redirecionou para login, o middleware funcionou
        self.assertNotEqual(response.status_code, 302)

    def test_superuser_empresa_none(self):
        superuser = User.objects.create_superuser('super_mw', password='senha123')
        self.c.login(username='super_mw', password='senha123')
        # Superuser não fica preso em empresa
        response = self.c.get(reverse('home'), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_nao_autenticado_redireciona_login(self):
        response = self.c.get(reverse('tarefas_board'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


# ===========================================================================
# 2. ISOLAMENTO POR EMPRESA
# ===========================================================================

class EmpresaIsolacaoTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa_a = make_empresa('emp-a', 'Empresa A')
        self.empresa_b = make_empresa('emp-b', 'Empresa B')

        self.staff_a = make_staff('staff_a', self.empresa_a)
        self.staff_b = make_staff('staff_b', self.empresa_b)

        self.user_cli_a, self.wfclient_a = make_cliente('cli_a', self.empresa_a, self.uf, code=1)
        self.user_cli_b, self.wfclient_b = make_cliente('cli_b', self.empresa_b, self.uf, code=2)

        self.tarefa_a = make_tarefa(self.empresa_a, self.staff_a, titulo='Tarefa da A')
        self.tarefa_b = make_tarefa(self.empresa_b, self.staff_b, titulo='Tarefa da B')

        self.c = Client()

    # --- Tarefas ---

    def test_staff_a_ve_apenas_tarefas_da_empresa_a(self):
        self.c.login(username='staff_a', password='senha123')
        response = self.c.get(reverse('tarefas_lista'))
        self.assertEqual(response.status_code, 200)
        titulos = [t.titulo for t in response.context['tarefas']]
        self.assertIn('Tarefa da A', titulos)
        self.assertNotIn('Tarefa da B', titulos)

    def test_staff_b_nao_acessa_tarefa_da_empresa_a(self):
        self.c.login(username='staff_b', password='senha123')
        response = self.c.get(reverse('detalhe_tarefa', args=[self.tarefa_a.id]))
        self.assertEqual(response.status_code, 404)

    def test_staff_a_nao_acessa_tarefa_da_empresa_b(self):
        self.c.login(username='staff_a', password='senha123')
        response = self.c.get(reverse('detalhe_tarefa', args=[self.tarefa_b.id]))
        self.assertEqual(response.status_code, 404)

    # --- Pedidos ---

    def test_staff_a_nao_ve_pedidos_da_empresa_b(self):
        end_a = make_endereco(self.wfclient_a, self.uf)
        end_b = make_endereco(self.wfclient_b, self.uf)
        pedido_a = make_pedido(self.wfclient_a, self.empresa_a, end_a)
        pedido_b = make_pedido(self.wfclient_b, self.empresa_b, end_b)

        self.c.login(username='staff_a', password='senha123')
        response = self.c.get(reverse('todos_os_pedidos'))
        self.assertEqual(response.status_code, 200)

        pedido_ids = [p.id for p in response.context.get('pedidos', [])]
        self.assertIn(pedido_a.id, pedido_ids)
        self.assertNotIn(pedido_b.id, pedido_ids)

    def test_staff_a_nao_acessa_detalhe_pedido_da_empresa_b(self):
        end_b = make_endereco(self.wfclient_b, self.uf)
        pedido_b = make_pedido(self.wfclient_b, self.empresa_b, end_b)

        self.c.login(username='staff_a', password='senha123')
        response = self.c.get(reverse('detalhes_pedido_admin', args=[pedido_b.id]))
        self.assertEqual(response.status_code, 404)

    # --- Clientes ---

    def test_staff_a_nao_ve_clientes_da_empresa_b(self):
        self.c.login(username='staff_a', password='senha123')
        response = self.c.get(reverse('listar_clientes'))
        self.assertEqual(response.status_code, 200)
        # listar_clientes usa page_obj (paginado)
        page_obj = response.context['page_obj']
        client_ids = [c.client_id for c in page_obj]
        self.assertIn(self.wfclient_a.client_id, client_ids)
        self.assertNotIn(self.wfclient_b.client_id, client_ids)


# ===========================================================================
# 3. PERMISSÕES DE ACESSO
# ===========================================================================

class PermissaoAcessoTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa = make_empresa('emp-perm')
        self.staff = make_staff('staff_perm', self.empresa)
        self.user_cli, self.wfclient = make_cliente('cli_perm', self.empresa, self.uf, code=20)
        self.c = Client()

    def test_anonimo_nao_acessa_board_tarefas(self):
        response = self.c.get(reverse('tarefas_board'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_anonimo_nao_acessa_lista_clientes(self):
        response = self.c.get(reverse('listar_clientes'))
        self.assertEqual(response.status_code, 302)

    def test_cliente_nao_acessa_board_tarefas(self):
        self.c.login(username='cli_perm', password='senha123')
        response = self.c.get(reverse('tarefas_board'))
        # staff_member_required redireciona não-staff
        self.assertNotEqual(response.status_code, 200)

    def test_cliente_nao_acessa_lista_clientes(self):
        self.c.login(username='cli_perm', password='senha123')
        response = self.c.get(reverse('listar_clientes'))
        self.assertNotEqual(response.status_code, 200)

    def test_staff_acessa_board_tarefas(self):
        self.c.login(username='staff_perm', password='senha123')
        response = self.c.get(reverse('tarefas_board'))
        self.assertEqual(response.status_code, 200)


# ===========================================================================
# 4. NOTIFICAÇÕES DE PEDIDOS
# ===========================================================================

class NotificacaoPedidoTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa = make_empresa('emp-notif')
        self.staff1 = make_staff('staff_notif1', self.empresa)
        self.staff2 = make_staff('staff_notif2', self.empresa)
        self.user_cli, self.wfclient = make_cliente('cli_notif', self.empresa, self.uf, code=30)
        self.end = make_endereco(self.wfclient, self.uf)
        self.c = Client()

    def test_notificacao_criada_ao_criar_pedido(self):
        pedido = make_pedido(self.wfclient, self.empresa, self.end)

        from .views import _notificar_novo_pedido
        _notificar_novo_pedido(pedido)

        # Os dois membros staff devem ter recebido notificação
        self.assertEqual(NotificacaoPedido.objects.filter(pedido=pedido).count(), 2)

    def test_notificacao_contem_nome_do_cliente(self):
        pedido = make_pedido(self.wfclient, self.empresa, self.end)

        from .views import _notificar_novo_pedido
        _notificar_novo_pedido(pedido)

        notif = NotificacaoPedido.objects.filter(usuario=self.staff1).first()
        self.assertIn(self.wfclient.client_name, notif.mensagem)

    def test_notificacao_inicia_nao_lida(self):
        pedido = make_pedido(self.wfclient, self.empresa, self.end)

        from .views import _notificar_novo_pedido
        _notificar_novo_pedido(pedido)

        lidas = NotificacaoPedido.objects.filter(pedido=pedido, lida=True).count()
        self.assertEqual(lidas, 0)

    def test_marcar_como_lida_via_post(self):
        pedido = make_pedido(self.wfclient, self.empresa, self.end)
        notif = NotificacaoPedido.objects.create(
            empresa=self.empresa,
            usuario=self.staff1,
            pedido=pedido,
            mensagem='Teste',
        )

        self.c.login(username='staff_notif1', password='senha123')
        self.c.post(reverse('notificacoes_pedidos'), {'marcar_lida': notif.id})

        notif.refresh_from_db()
        self.assertTrue(notif.lida)

    def test_marcar_todas_como_lidas(self):
        pedido = make_pedido(self.wfclient, self.empresa, self.end)
        for i in range(3):
            NotificacaoPedido.objects.create(
                empresa=self.empresa,
                usuario=self.staff1,
                pedido=pedido,
                mensagem=f'Notif {i}',
            )

        self.c.login(username='staff_notif1', password='senha123')
        self.c.post(reverse('notificacoes_pedidos'), {'marcar_todas': '1'})

        nao_lidas = NotificacaoPedido.objects.filter(usuario=self.staff1, lida=False).count()
        self.assertEqual(nao_lidas, 0)

    def test_pedido_sem_empresa_nao_cria_notificacao(self):
        """Pedido antigo sem empresa não deve quebrar nem criar notificação."""
        pedido = make_pedido(self.wfclient, self.empresa, self.end)
        pedido.empresa = None
        pedido.save()
        # Força cliente sem empresa também
        self.wfclient.empresa = None
        self.wfclient.save()

        from .views import _notificar_novo_pedido
        _notificar_novo_pedido(pedido)  # não deve levantar exceção

        self.assertEqual(NotificacaoPedido.objects.count(), 0)

    def test_staff_nao_ve_notificacoes_de_outra_empresa(self):
        outra_empresa = make_empresa('emp-outra-notif')
        outro_staff = make_staff('staff_outra', outra_empresa)
        uf2 = make_uf('ES')
        _, wfc2 = make_cliente('cli_outra', outra_empresa, uf2, code=99)
        end2 = make_endereco(wfc2, uf2)
        pedido2 = make_pedido(wfc2, outra_empresa, end2)

        NotificacaoPedido.objects.create(
            empresa=outra_empresa,
            usuario=outro_staff,
            pedido=pedido2,
            mensagem='Outro',
        )

        self.c.login(username='staff_notif1', password='senha123')
        response = self.c.get(reverse('notificacoes_pedidos'))
        self.assertEqual(response.status_code, 200)
        ids = [n.id for n in response.context['page_obj']]
        self.assertEqual(len(ids), 0)


# ===========================================================================
# 5. TAREFAS
# ===========================================================================

class TarefaTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa = make_empresa('emp-tarefa')
        self.staff = make_staff('staff_tarefa', self.empresa)
        self.c = Client()
        self.c.login(username='staff_tarefa', password='senha123')

    def test_criar_tarefa_via_post(self):
        response = self.c.post(reverse('criar_tarefa'), {
            'titulo': 'Nova Tarefa',
            'descricao': 'Descrição da tarefa',
            'prioridade': 'ALTA',
            'status': 'A_FAZER',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Tarefa.objects.filter(titulo='Nova Tarefa', empresa=self.empresa).exists())

    def test_tarefa_criada_pertence_a_empresa_correta(self):
        self.c.post(reverse('criar_tarefa'), {'titulo': 'Tarefa X', 'prioridade': 'MEDIA', 'status': 'A_FAZER'})
        tarefa = Tarefa.objects.get(titulo='Tarefa X')
        self.assertEqual(tarefa.empresa, self.empresa)

    def test_board_exibe_apenas_tarefas_da_empresa(self):
        empresa2 = make_empresa('emp-tarefa-2')
        staff2 = make_staff('staff_tarefa2', empresa2)
        make_tarefa(self.empresa, self.staff, 'Minha Tarefa')
        make_tarefa(empresa2, staff2, 'Tarefa Alheia')

        response = self.c.get(reverse('tarefas_board'))
        tarefas_visiveis = [
            t.titulo
            for col in response.context['colunas']
            for t in col['tarefas']
        ]
        self.assertIn('Minha Tarefa', tarefas_visiveis)
        self.assertNotIn('Tarefa Alheia', tarefas_visiveis)

    def test_atualizar_status_tarefa(self):
        tarefa = make_tarefa(self.empresa, self.staff, status='A_FAZER')
        self.c.post(
            reverse('atualizar_status_tarefa', args=[tarefa.id]),
            {'status': 'CONCLUIDO', 'next': '/tarefas/'},
        )
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, 'CONCLUIDO')

    def test_excluir_tarefa(self):
        tarefa = make_tarefa(self.empresa, self.staff)
        self.c.post(reverse('excluir_tarefa', args=[tarefa.id]))
        self.assertFalse(Tarefa.objects.filter(id=tarefa.id).exists())

    def test_staff_nao_exclui_tarefa_de_outra_empresa(self):
        empresa2 = make_empresa('emp-tarefa-exc')
        staff2 = make_staff('staff_tarefa_exc', empresa2)
        tarefa_alheia = make_tarefa(empresa2, staff2)

        self.c.post(reverse('excluir_tarefa', args=[tarefa_alheia.id]))
        # Tarefa deve continuar existindo
        self.assertTrue(Tarefa.objects.filter(id=tarefa_alheia.id).exists())

    def test_tarefa_atrasada_property(self):
        from datetime import date, timedelta
        tarefa = make_tarefa(self.empresa, self.staff, status='A_FAZER')
        tarefa.prazo = date.today() - timedelta(days=1)
        tarefa.save()
        self.assertTrue(tarefa.atrasada)

    def test_tarefa_concluida_nao_e_atrasada(self):
        from datetime import date, timedelta
        tarefa = make_tarefa(self.empresa, self.staff, status='CONCLUIDO')
        tarefa.prazo = date.today() - timedelta(days=1)
        tarefa.save()
        self.assertFalse(tarefa.atrasada)


# ===========================================================================
# 6. CHECKLIST
# ===========================================================================

class ChecklistTest(TestCase):
    def setUp(self):
        self.uf = make_uf('SP')
        self.empresa = make_empresa('emp-check')
        self.staff = make_staff('staff_check', self.empresa)
        self.tarefa = make_tarefa(self.empresa, self.staff)
        self.c = Client()
        self.c.login(username='staff_check', password='senha123')

    def test_adicionar_item_checklist(self):
        self.c.post(
            reverse('adicionar_checklist_item', args=[self.tarefa.id]),
            {'texto': 'Item de teste'},
        )
        self.assertTrue(ChecklistItem.objects.filter(tarefa=self.tarefa, texto='Item de teste').exists())

    def test_toggle_item_checklist(self):
        item = ChecklistItem.objects.create(tarefa=self.tarefa, texto='Item', concluido=False)
        self.c.post(reverse('toggle_checklist_item', args=[item.id]))
        item.refresh_from_db()
        self.assertTrue(item.concluido)

    def test_toggle_duas_vezes_volta_ao_original(self):
        item = ChecklistItem.objects.create(tarefa=self.tarefa, texto='Item', concluido=False)
        self.c.post(reverse('toggle_checklist_item', args=[item.id]))
        self.c.post(reverse('toggle_checklist_item', args=[item.id]))
        item.refresh_from_db()
        self.assertFalse(item.concluido)

    def test_excluir_item_checklist(self):
        item = ChecklistItem.objects.create(tarefa=self.tarefa, texto='Remover', concluido=False)
        self.c.post(reverse('excluir_checklist_item', args=[item.id]))
        self.assertFalse(ChecklistItem.objects.filter(id=item.id).exists())
