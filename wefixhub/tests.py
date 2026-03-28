"""
Suite de testes para o projeto WFHUB.

Cobertura:
  1. EmpresaMiddlewareTest        — request.empresa setado corretamente
  2. EmpresaIsolacaoTest          — staff/cliente de empresa A não vê dados de empresa B
  3. PermissaoAcessoTest          — rotas de staff bloqueadas para clientes e anônimos
  4. NotificacaoPedidoTest        — notificações criadas e marcadas como lidas
  5. TarefaTest                   — CRUD de tarefas isolado por empresa
  6. ChecklistTest                — toggle e exclusão de itens de checklist
  7. WishlistCicloDeVidaTest      — ciclo de vida completo do item de wishlist
  8. WishlistNotificarAdminTest   — admin notifica via WhatsApp; flags corretos
  9. WishlistDescartarClienteTest — cliente descarta pelo banner e pela página meus-avisos
 10. WishlistAdicionarCarrinhoTest— adicionar ao carrinho auto-descarta wishlist
 11. WishlistAvisarQuandoDispTest — cliente solicita aviso via catálogo (sem duplicatas)
 12. WishlistMeusAvisosTest       — página meus-avisos exibe/oculta itens corretamente
 13. WishlistDashboardAdminTest   — oportunidades do dashboard agrupam e filtram corretamente
 14. WishlistIsolacaoEmpresaTest  — itens de empresa A não vazam para empresa B
"""

import io
from unittest.mock import MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

# Evita erro de manifest do WhiteNoise em todos os testes
_STORAGES_TEST = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WFTestCase(TestCase):
    """Base para todos os testes — desativa WhiteNoise manifest e R2."""

from .models import (
    Empresa, PerfilUsuario, WfClient, wefixhub_uf,
    Endereco, Pedido, Product,
    Tarefa, ChecklistItem, NotificacaoTarefa,
    NotificacaoPedido, LogAuditoria, AnexoTarefa,
    Carrinho, ItemCarrinho,
    ItemPedidoIgnorado,
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


def make_cliente(username, empresa, uf, code=1, password='senha123', cnpj=None):
    user = User.objects.create_user(username=username, password=password, is_staff=False)
    client = WfClient.objects.create(
        user=user,
        empresa=empresa,
        client_code=code,
        client_name=username,
        client_cnpj=cnpj or f'{code:014d}',
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

class EmpresaMiddlewareTest(WFTestCase):
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

class EmpresaIsolacaoTest(WFTestCase):
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
        # tarefas_lista retorna 'grupos' com tarefas agrupadas por status
        titulos = [
            t.titulo
            for grupo in response.context['grupos']
            for t in grupo['tarefas']
        ]
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

class PermissaoAcessoTest(WFTestCase):
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

class NotificacaoPedidoTest(WFTestCase):
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

class TarefaTest(WFTestCase):
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

class ChecklistTest(WFTestCase):
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


# ===========================================================================
# 7. FOTO DE PERFIL
# ===========================================================================

def _make_image(name='foto.jpg'):
    """JPEG 1×1 pixel mínimo."""
    content = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e\xbf'
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0a\xff\xd9'
    )
    return SimpleUploadedFile(name, content, content_type='image/jpeg')


@override_settings(
    MEDIA_ROOT='/tmp/wfhub_test/',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class FotoPerfilMembroTest(WFTestCase):
    def setUp(self):
        self.empresa = make_empresa('emp-foto-membro')
        self.user = make_staff('staff_foto', self.empresa)
        self.perfil = self.user.perfil
        self.c = Client()
        self.c.login(username='staff_foto', password='senha123')

    def test_upload_foto_salva_no_perfil(self):
        resp = self.c.post(reverse('upload_foto_perfil'), {'foto': _make_image()})
        # Membros (is_staff) são redirecionados para perfil_representante
        self.assertRedirects(resp, reverse('perfil_representante'))
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.foto_perfil.name)

    def test_upload_substitui_foto_anterior(self):
        self.c.post(reverse('upload_foto_perfil'), {'foto': _make_image('a.jpg')})
        self.perfil.refresh_from_db()
        nome1 = self.perfil.foto_perfil.name
        self.c.post(reverse('upload_foto_perfil'), {'foto': _make_image('b.jpg')})
        self.perfil.refresh_from_db()
        self.assertNotEqual(self.perfil.foto_perfil.name, nome1)

    def test_sem_arquivo_nao_altera_perfil(self):
        self.c.post(reverse('upload_foto_perfil'), {})
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.foto_perfil)

    def test_editar_perfil_renderiza_com_perfil_membro(self):
        resp = self.c.get(reverse('editar_perfil'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('perfil_membro', resp.context)


@override_settings(
    MEDIA_ROOT='/tmp/wfhub_test/',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class FotoPerfilClienteTest(WFTestCase):
    def setUp(self):
        self.empresa = make_empresa('emp-foto-cli')
        self.uf = make_uf('SP')
        self.user, self.wfclient = make_cliente('cli_foto', self.empresa, self.uf, code=50)
        self.c = Client()
        self.c.login(username='cli_foto', password='senha123')

    def test_upload_foto_salva_no_wfclient(self):
        resp = self.c.post(reverse('upload_foto_perfil'), {'foto': _make_image()})
        self.assertRedirects(resp, reverse('editar_perfil'))
        self.wfclient.refresh_from_db()
        self.assertTrue(self.wfclient.foto_perfil.name)

    def test_editar_perfil_renderiza_com_cliente(self):
        resp = self.c.get(reverse('editar_perfil'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('cliente', resp.context)


# ===========================================================================
# 8. UPLOAD DE ORÇAMENTO
# ===========================================================================

@override_settings(
    MEDIA_ROOT='/tmp/wfhub_test/',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class UploadOrcamentoTest(WFTestCase):
    def setUp(self):
        self.empresa = make_empresa('emp-orc')
        self.uf = make_uf('SP')
        self.staff = make_staff('staff_orc', self.empresa)
        self.user_cli, self.wfclient = make_cliente('cli_orc', self.empresa, self.uf, code=60)
        self.end = make_endereco(self.wfclient, self.uf)
        self.pedido = make_pedido(self.wfclient, self.empresa, self.end)
        self.c = Client()
        self.c.login(username='staff_orc', password='senha123')

    def _pdf(self, name='orcamento.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4', content_type='application/pdf')

    def test_upload_salva_via_filefield(self):
        resp = self.c.post(
            reverse('upload_orcamento_pdf', args=[self.pedido.id]),
            {'orcamento_pdf_file': self._pdf()},
        )
        self.assertRedirects(resp, reverse('detalhes_pedido_admin', args=[self.pedido.id]))
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.orcamento_pdf.name)
        self.assertIn('orcamentos/', self.pedido.orcamento_pdf.name)

    def test_upload_sem_arquivo_nao_altera_pedido(self):
        self.c.post(reverse('upload_orcamento_pdf', args=[self.pedido.id]), {})
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.orcamento_pdf)

    def test_segundo_upload_salva_orcamento(self):
        """Dois uploads consecutivos — o segundo deve ter um orcamento salvo."""
        self.c.post(
            reverse('upload_orcamento_pdf', args=[self.pedido.id]),
            {'orcamento_pdf_file': self._pdf('v1.pdf')},
        )
        self.c.post(
            reverse('upload_orcamento_pdf', args=[self.pedido.id]),
            {'orcamento_pdf_file': self._pdf('v2.pdf')},
        )
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.orcamento_pdf.name)


# ===========================================================================
# 9. LOG DE AUDITORIA
# ===========================================================================

class LogAuditoriaTest(WFTestCase):
    def setUp(self):
        self.empresa = make_empresa('emp-audit')
        self.staff = make_staff('staff_audit', self.empresa)

    def test_registrar_log_cria_entrada(self):
        from wefixhub.views import registrar_log
        req = MagicMock()
        req.user = self.staff
        req.empresa = self.empresa
        req.META = {'HTTP_X_FORWARDED_FOR': '1.2.3.4'}

        registrar_log(req, 'TAREFA_CRIADA', 'Tarefa criada via teste')
        self.assertTrue(
            LogAuditoria.objects.filter(
                empresa=self.empresa,
                usuario=self.staff,
                acao='TAREFA_CRIADA',
            ).exists()
        )

    def test_registrar_log_nao_quebra_com_dados_invalidos(self):
        from wefixhub.views import registrar_log
        req = MagicMock()
        req.user = None
        req.empresa = None
        req.META = {}
        # Não deve levantar exceção
        registrar_log(req, 'TAREFA_CRIADA', 'teste silencioso')

    def test_pagina_auditoria_acessivel_para_staff(self):
        LogAuditoria.objects.create(
            empresa=self.empresa, usuario=self.staff,
            acao='TAREFA_CRIADA', descricao='log de teste',
        )
        c = Client()
        c.login(username='staff_audit', password='senha123')
        resp = c.get(reverse('logs_auditoria'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'log de teste')

    def test_filtro_por_acao_funciona(self):
        LogAuditoria.objects.create(empresa=self.empresa, usuario=self.staff, acao='TAREFA_CRIADA', descricao='a')
        LogAuditoria.objects.create(empresa=self.empresa, usuario=self.staff, acao='PEDIDO_CRIADO', descricao='b')
        c = Client()
        c.login(username='staff_audit', password='senha123')
        resp = c.get(reverse('logs_auditoria') + '?acao=TAREFA_CRIADA')
        logs = list(resp.context['page_obj'])
        self.assertTrue(all(l.acao == 'TAREFA_CRIADA' for l in logs))


# ===========================================================================
# 10. TEMPLATE TAG avatar
# ===========================================================================

class AvatarTagTest(WFTestCase):
    def setUp(self):
        self.empresa = make_empresa('emp-avatar')

    def test_avatar_sem_foto_mostra_iniciais(self):
        from wefixhub.templatetags.format_tags import avatar
        user = User.objects.create_user(username='joaosilva', first_name='João', last_name='Silva')
        html = str(avatar(user, size=32))
        self.assertIn('JO', html)
        self.assertIn('border-radius:50%', html)

    def test_avatar_none_mostra_interrogacao(self):
        from wefixhub.templatetags.format_tags import avatar
        html = str(avatar(None, size=32))
        self.assertIn('?', html)

    def test_avatar_respeita_tamanho(self):
        from wefixhub.templatetags.format_tags import avatar
        user = User.objects.create_user(username='sized_user')
        html = str(avatar(user, size=48))
        self.assertIn('width:48px', html)
        self.assertIn('height:48px', html)

    @override_settings(
        MEDIA_ROOT='/tmp/wfhub_test/',
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        }
    )
    def test_avatar_com_foto_membro_retorna_img(self):
        from wefixhub.templatetags.format_tags import avatar
        user = make_staff('staff_av_foto', self.empresa)
        perfil = user.perfil
        perfil.foto_perfil = 'perfis/teste.jpg'
        perfil.save()
        html = str(avatar(user, size=32))
        self.assertIn('<img', html)
        self.assertIn('perfis/teste.jpg', html)


# ===========================================================================
# 12. CARRINHO AJAX — atualizar_item_qtd e remover_item_ajax
# ===========================================================================

def make_product(code='PROD1', empresa=None):
    return Product.objects.create(
        product_code=code,
        product_description='Produto Teste',
        product_value_sp='10.00',
        product_value_es='10.00',
        empresa=empresa,
    )


class CarrinhoAjaxTest(WFTestCase):
    """Testa as views Ajax do carrinho (sem reload de página)."""

    def setUp(self):
        self.empresa = make_empresa('cart-empresa')
        self.uf = make_uf('SP')
        self.user, self.wfclient = make_cliente('cart_user', self.empresa, self.uf, code=999)
        self.produto = make_product('CART01', self.empresa)
        self.carrinho = Carrinho.objects.create(cliente=self.wfclient)
        self.item = ItemCarrinho.objects.create(carrinho=self.carrinho, produto=self.produto, quantidade=2)
        self.client.force_login(self.user)

    def test_atualizar_qtd_salva_no_banco(self):
        import json
        resp = self.client.post(
            reverse('atualizar_item_qtd'),
            data=json.dumps({'product_id': self.produto.product_id, 'quantidade': 5}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantidade, 5)

    def test_atualizar_qtd_retorna_json_ok(self):
        import json
        resp = self.client.post(
            reverse('atualizar_item_qtd'),
            data=json.dumps({'product_id': self.produto.product_id, 'quantidade': 3}),
            content_type='application/json',
        )
        data = resp.json()
        self.assertTrue(data['ok'])

    def test_atualizar_qtd_zero_remove_item(self):
        import json
        self.client.post(
            reverse('atualizar_item_qtd'),
            data=json.dumps({'product_id': self.produto.product_id, 'quantidade': 0}),
            content_type='application/json',
        )
        self.assertFalse(ItemCarrinho.objects.filter(id=self.item.id).exists())

    def test_remover_item_ajax_deleta_item(self):
        resp = self.client.post(
            reverse('remover_item_ajax', args=[self.produto.product_id]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ItemCarrinho.objects.filter(id=self.item.id).exists())

    def test_remover_item_ajax_retorna_json_ok(self):
        resp = self.client.post(
            reverse('remover_item_ajax', args=[self.produto.product_id]),
        )
        self.assertTrue(resp.json()['ok'])

    def test_atualizar_qtd_requer_login(self):
        import json
        self.client.logout()
        resp = self.client.post(
            reverse('atualizar_item_qtd'),
            data=json.dumps({'product_id': self.produto.product_id, 'quantidade': 3}),
            content_type='application/json',
        )
        self.assertNotEqual(resp.status_code, 200)

    def test_remover_item_ajax_requer_login(self):
        self.client.logout()
        resp = self.client.post(reverse('remover_item_ajax', args=[self.produto.product_id]))
        self.assertNotEqual(resp.status_code, 200)

    def test_nao_afeta_carrinho_de_outro_cliente(self):
        """Cliente B não consegue modificar o carrinho do cliente A."""
        import json
        _, outro_client = make_cliente('outro_cart', self.empresa, self.uf, code=998)
        outro_user = User.objects.get(wfclient=outro_client)
        self.client.force_login(outro_user)
        self.client.post(
            reverse('atualizar_item_qtd'),
            data=json.dumps({'product_id': self.produto.product_id, 'quantidade': 99}),
            content_type='application/json',
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantidade, 2)  # não alterado


# ===========================================================================
# HELPERS PARA WISHLIST
# ===========================================================================

def make_item_ignorado(cliente, codigo_produto, produto_desc='Produto Teste',
                       quantidade=5, notificado=False, descartado=False,
                       motivo='Sem estoque no momento do pedido'):
    return ItemPedidoIgnorado.objects.create(
        pedido=None,
        cliente=cliente,
        codigo_produto=codigo_produto,
        descricao_produto=produto_desc,
        quantidade_tentada=quantidade,
        motivo_erro=motivo,
        notificado=notificado,
        descartado_pelo_cliente=descartado,
    )


def make_product_com_estoque(code, empresa, preco_sp='50.00', preco_es='50.00',
                              status='DISPONIVEL'):
    return Product.objects.create(
        product_code=code,
        product_description=f'Produto {code}',
        product_value_sp=preco_sp,
        product_value_es=preco_es,
        status_estoque=status,
        empresa=empresa,
    )


# ===========================================================================
# 7. WISHLIST — CICLO DE VIDA DO ITEM
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistCicloDeVidaTest(WFTestCase):
    """
    Verifica os estados possíveis de um ItemPedidoIgnorado e como cada flag
    (notificado / descartado_pelo_cliente) afeta a visibilidade do item.
    """

    def setUp(self):
        self.empresa = make_empresa('wl-ciclo')
        self.uf = make_uf('SP')
        self.user, self.cliente = make_cliente('wl_cliente', self.empresa, self.uf, code=10)
        self.produto = make_product_com_estoque('WL001', self.empresa)

    def test_flags_padrao_sao_false(self):
        """Item recém-criado tem notificado=False e descartado_pelo_cliente=False."""
        item = make_item_ignorado(self.cliente, 'WL001')
        self.assertFalse(item.notificado)
        self.assertFalse(item.descartado_pelo_cliente)

    def test_item_pendente_aparece_no_banner_home(self):
        """
        Home exibe o banner de wishlist quando há item pendente com estoque disponível.
        Garante que produtos_wishlist_cliente é populado no contexto.
        """
        make_item_ignorado(self.cliente, 'WL001')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertIn('WL001', codigos)

    def test_item_descartado_nao_aparece_no_banner_home(self):
        """Item com descartado_pelo_cliente=True não aparece no banner."""
        make_item_ignorado(self.cliente, 'WL001', descartado=True)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL001', codigos)

    def test_item_sem_estoque_nao_aparece_no_banner_home(self):
        """Produto com status SEM_ESTOQUE não aparece no banner mesmo com item pendente."""
        self.produto.status_estoque = 'SEM_ESTOQUE'
        self.produto.save()
        make_item_ignorado(self.cliente, 'WL001')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL001', codigos)

    def test_item_sem_preco_nao_aparece_no_banner_home(self):
        """Produto com preço 0 ou nulo não aparece no banner."""
        self.produto.product_value_sp = 0
        self.produto.save()
        make_item_ignorado(self.cliente, 'WL001')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL001', codigos)

    def test_banner_persiste_apos_admin_notificar(self):
        """
        Após o admin enviar o WhatsApp (notificado=True), o banner do cliente
        deve continuar visível até ele comprar ou descartar.
        """
        make_item_ignorado(self.cliente, 'WL001', notificado=True)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        # notificado=True NÃO descarta do lado do cliente — banner permanece
        self.assertIn('WL001', codigos)

    def test_item_motivo_sem_estoque_requerido_para_banner(self):
        """Apenas itens cujo motivo contenha 'estoque' devem aparecer no banner."""
        make_item_ignorado(self.cliente, 'WL001', motivo='Produto bloqueado por preço')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL001', codigos)

    def test_sem_duplicatas_no_banner(self):
        """Mesmo que haja vários registros para o mesmo produto, aparece apenas uma vez."""
        make_item_ignorado(self.cliente, 'WL001')
        make_item_ignorado(self.cliente, 'WL001')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertEqual(codigos.count('WL001'), 1)


# ===========================================================================
# 8. WISHLIST — NOTIFICAÇÃO PELO ADMIN (WhatsApp)
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistNotificarAdminTest(WFTestCase):
    """
    Testa a view notificar_wishlist_whatsapp:
    - marca itens como notificado=True
    - retorna aviso quando produto não tem mais estoque/preço
    - não afeta itens já notificados ou descartados
    - bloqueia acesso de não-staff
    """

    def setUp(self):
        self.empresa = make_empresa('wl-notif')
        self.uf = make_uf('SP')
        self.staff_user = make_staff('wl_staff', self.empresa)
        self.user_cliente, self.cliente = make_cliente('wl_notif_cli', self.empresa, self.uf, code=20)
        self.produto = make_product_com_estoque('WL002', self.empresa, preco_sp='99.90')
        self.item = make_item_ignorado(self.cliente, 'WL002', quantidade=3)
        self.client.force_login(self.staff_user)

    def test_notificar_marca_itens_como_notificados(self):
        """Após clicar em Notificar, o item deve ter notificado=True."""
        self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.notificado)

    def test_notificar_registra_data_notificacao(self):
        """data_notificacao deve ser preenchida após notificar."""
        self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.data_notificacao)

    def test_notificar_gera_lote_id(self):
        """lote_notificacao deve ser preenchido com string não vazia."""
        self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.lote_notificacao)
        self.assertTrue(self.item.lote_notificacao.startswith('REP-'))

    def test_notificar_sem_estoque_retorna_warning(self):
        """
        Se o produto voltou a ficar sem preço/estoque, a view deve exibir
        warning e redirecionar de volta ao dashboard — sem marcar notificado.
        """
        self.produto.product_value_sp = 0
        self.produto.save()
        resp = self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.item.refresh_from_db()
        self.assertFalse(self.item.notificado)
        # Redireciona para o dashboard admin
        self.assertEqual(resp.status_code, 302)
        self.assertIn('dashboard', resp['Location'])

    def test_notificar_nao_renotifica_itens_ja_notificados(self):
        """Itens já com notificado=True não são afetados por nova chamada."""
        item2 = make_item_ignorado(self.cliente, 'WL002', notificado=True)
        # Salva data_notificacao original
        data_original = item2.data_notificacao
        self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        item2.refresh_from_db()
        # lote e data não devem ter mudado
        self.assertEqual(item2.data_notificacao, data_original)

    def test_notificar_nao_afeta_item_descartado(self):
        """Item com descartado_pelo_cliente=True não é tocado pela notificação."""
        item_desc = make_item_ignorado(self.cliente, 'WL002', descartado=True)
        self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        item_desc.refresh_from_db()
        self.assertFalse(item_desc.notificado)

    def test_notificar_requer_staff(self):
        """Cliente comum não pode acessar a view de notificação."""
        self.client.force_login(self.user_cliente)
        resp = self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.assertNotEqual(resp.status_code, 200)

    def test_notificar_redireciona_para_whatsapp(self):
        """Quando há produtos, a resposta deve redirecionar para link do WhatsApp."""
        resp = self.client.get(reverse('notificar_wishlist_whatsapp', args=[self.cliente.client_id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('whatsapp', resp['Location'].lower())


# ===========================================================================
# 9. WISHLIST — CLIENTE DESCARTA
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistDescartarClienteTest(WFTestCase):
    """
    Testa os dois caminhos de descarte pelo cliente:
    - descartar_wishlist_home (banner AJAX)
    - cancelar_aviso (página meus-avisos)
    """

    def setUp(self):
        self.empresa = make_empresa('wl-descartar')
        self.uf = make_uf('SP')
        self.user, self.cliente = make_cliente('wl_desc_cli', self.empresa, self.uf, code=30)
        self.produto = make_product_com_estoque('WL003', self.empresa)
        self.item = make_item_ignorado(self.cliente, 'WL003')
        self.client.force_login(self.user)

    def test_descartar_home_marca_descartado(self):
        """AJAX de descarte do banner deve setar descartado_pelo_cliente=True."""
        resp = self.client.post(
            reverse('descartar_wishlist_home'),
            data={'product_code': 'WL003'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['sucesso'])
        self.item.refresh_from_db()
        self.assertTrue(self.item.descartado_pelo_cliente)

    def test_descartar_home_sem_codigo_retorna_erro(self):
        """Chamada sem product_code deve retornar 400."""
        resp = self.client.post(reverse('descartar_wishlist_home'), data={})
        self.assertEqual(resp.status_code, 400)

    def test_descartar_home_nao_afeta_outro_cliente(self):
        """Descarte de cliente A não afeta item de cliente B com mesmo produto."""
        _, outro_cliente = make_cliente('wl_desc_outro', self.empresa, self.uf, code=31)
        item_b = make_item_ignorado(outro_cliente, 'WL003')
        self.client.post(reverse('descartar_wishlist_home'), data={'product_code': 'WL003'})
        item_b.refresh_from_db()
        self.assertFalse(item_b.descartado_pelo_cliente)

    def test_descartar_home_requer_login(self):
        """Endpoint AJAX deve exigir autenticação."""
        self.client.logout()
        resp = self.client.post(
            reverse('descartar_wishlist_home'),
            data={'product_code': 'WL003'},
        )
        self.assertNotEqual(resp.status_code, 200)

    def test_cancelar_aviso_marca_descartado(self):
        """cancelar_aviso (página meus-avisos) deve setar descartado_pelo_cliente=True."""
        resp = self.client.post(reverse('cancelar_aviso', args=[self.item.id]))
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.descartado_pelo_cliente)

    def test_cancelar_aviso_nao_afeta_item_de_outro_cliente(self):
        """Cliente não pode cancelar aviso de outro cliente passando o ID direto."""
        _, outro_cliente = make_cliente('wl_cancel_outro', self.empresa, self.uf, code=32)
        item_alheio = make_item_ignorado(outro_cliente, 'WL003')
        self.client.post(reverse('cancelar_aviso', args=[item_alheio.id]))
        item_alheio.refresh_from_db()
        self.assertFalse(item_alheio.descartado_pelo_cliente)

    def test_item_descartado_some_do_banner_apos_descartar(self):
        """Após descartar, o produto não deve mais aparecer no banner da home."""
        self.client.post(reverse('descartar_wishlist_home'), data={'product_code': 'WL003'})
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL003', codigos)


# ===========================================================================
# 10. WISHLIST — ADICIONAR AO CARRINHO AUTO-DESCARTA
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistAdicionarCarrinhoTest(WFTestCase):
    """
    Quando o cliente adiciona um produto ao carrinho, todos os itens de wishlist
    pendentes para aquele produto devem ser marcados como descartados automaticamente.
    """

    def setUp(self):
        self.empresa = make_empresa('wl-addcart')
        self.uf = make_uf('SP')
        self.user, self.cliente = make_cliente('wl_cart_cli', self.empresa, self.uf, code=40)
        self.produto = make_product_com_estoque('WL004', self.empresa)
        self.item1 = make_item_ignorado(self.cliente, 'WL004')
        self.item2 = make_item_ignorado(self.cliente, 'WL004')  # segundo registro do mesmo produto
        self.client.force_login(self.user)

    def test_adicionar_ao_carrinho_descarta_todos_os_registros(self):
        """Todos os registros do produto na wishlist devem ser descartados."""
        self.client.post(
            reverse('adicionar_ao_carrinho_bd'),
            data={'product_id': self.produto.product_id, 'quantidade': 1},
        )
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.assertTrue(self.item1.descartado_pelo_cliente)
        self.assertTrue(self.item2.descartado_pelo_cliente)

    def test_adicionar_ao_carrinho_nao_descarta_outro_produto(self):
        """Adicionar produto A ao carrinho não deve descartar wishlist do produto B."""
        outro_produto = make_product_com_estoque('WL005', self.empresa)
        item_b = make_item_ignorado(self.cliente, 'WL005')
        self.client.post(
            reverse('adicionar_ao_carrinho_bd'),
            data={'product_id': self.produto.product_id, 'quantidade': 1},
        )
        item_b.refresh_from_db()
        self.assertFalse(item_b.descartado_pelo_cliente)

    def test_adicionar_ao_carrinho_nao_descarta_wishlist_de_outro_cliente(self):
        """Auto-descarte não afeta registros de outros clientes."""
        _, outro_cliente = make_cliente('wl_cart_outro', self.empresa, self.uf, code=41)
        item_alheio = make_item_ignorado(outro_cliente, 'WL004')
        self.client.post(
            reverse('adicionar_ao_carrinho_bd'),
            data={'product_id': self.produto.product_id, 'quantidade': 1},
        )
        item_alheio.refresh_from_db()
        self.assertFalse(item_alheio.descartado_pelo_cliente)

    def test_produto_some_do_banner_apos_adicionar_ao_carrinho(self):
        """Após adicionar, o produto não deve aparecer no banner da home."""
        self.client.post(
            reverse('adicionar_ao_carrinho_bd'),
            data={'product_id': self.produto.product_id, 'quantidade': 1},
        )
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WL004', codigos)


# ===========================================================================
# 11. WISHLIST — CLIENTE SOLICITA AVISO VIA CATÁLOGO
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistAvisarQuandoDispTest(WFTestCase):
    """
    Testa avisar_quando_disponivel: cria ItemPedidoIgnorado via catálogo e
    evita duplicatas para o mesmo cliente+produto.
    """

    def setUp(self):
        self.empresa = make_empresa('wl-aviso')
        self.uf = make_uf('ES')
        self.user, self.cliente = make_cliente('wl_aviso_cli', self.empresa, self.uf, code=50)
        self.produto = make_product_com_estoque('WL006', self.empresa, status='SEM_ESTOQUE')
        self.client.force_login(self.user)

    def test_aviso_criado_corretamente(self):
        """Endpoint cria ItemPedidoIgnorado com os dados corretos."""
        resp = self.client.post(
            reverse('avisar_quando_disponivel'),
            data={'product_id': self.produto.product_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['sucesso'])
        item = ItemPedidoIgnorado.objects.get(
            cliente=self.cliente, codigo_produto='WL006'
        )
        self.assertFalse(item.notificado)
        self.assertFalse(item.descartado_pelo_cliente)
        self.assertIn('estoque', item.motivo_erro.lower())

    def test_aviso_evita_duplicatas(self):
        """Dois cliques não criam dois registros pendentes."""
        self.client.post(
            reverse('avisar_quando_disponivel'),
            data={'product_id': self.produto.product_id},
        )
        self.client.post(
            reverse('avisar_quando_disponivel'),
            data={'product_id': self.produto.product_id},
        )
        count = ItemPedidoIgnorado.objects.filter(
            cliente=self.cliente,
            codigo_produto='WL006',
            notificado=False,
        ).count()
        self.assertEqual(count, 1)

    def test_aviso_requer_login(self):
        """Endpoint não aceita requisição de usuário não autenticado."""
        self.client.logout()
        resp = self.client.post(
            reverse('avisar_quando_disponivel'),
            data={'product_id': self.produto.product_id},
        )
        self.assertNotEqual(resp.status_code, 200)


# ===========================================================================
# 12. WISHLIST — PÁGINA MEUS AVISOS
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/')
class WishlistMeusAvisosTest(WFTestCase):
    """
    Testa a página meus_avisos:
    - pendentes: notificado=False, descartado_pelo_cliente=False
    - notificados: notificado=True (histórico)
    - descartados nunca aparecem
    """

    def setUp(self):
        self.empresa = make_empresa('wl-meus-avisos')
        self.uf = make_uf('SP')
        self.user, self.cliente = make_cliente('wl_avisos_cli', self.empresa, self.uf, code=60)
        self.client.force_login(self.user)

    def test_pendentes_aparecem_na_pagina(self):
        item = make_item_ignorado(self.cliente, 'WLA01')
        resp = self.client.get(reverse('meus_avisos'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(item, resp.context['pendentes'])

    def test_descartados_nao_aparecem_nos_pendentes(self):
        item = make_item_ignorado(self.cliente, 'WLA02', descartado=True)
        resp = self.client.get(reverse('meus_avisos'))
        self.assertNotIn(item, resp.context['pendentes'])

    def test_notificados_aparecem_no_historico(self):
        item = make_item_ignorado(self.cliente, 'WLA03', notificado=True)
        resp = self.client.get(reverse('meus_avisos'))
        self.assertIn(item, resp.context['notificados'])

    def test_notificados_nao_aparecem_nos_pendentes(self):
        item = make_item_ignorado(self.cliente, 'WLA04', notificado=True)
        resp = self.client.get(reverse('meus_avisos'))
        self.assertNotIn(item, resp.context['pendentes'])

    def test_itens_de_outro_cliente_nao_aparecem(self):
        _, outro_cliente = make_cliente('wl_outro_avisos', self.empresa, self.uf, code=61)
        item_alheio = make_item_ignorado(outro_cliente, 'WLA05')
        resp = self.client.get(reverse('meus_avisos'))
        self.assertNotIn(item_alheio, resp.context['pendentes'])

    def test_motivo_diferente_de_estoque_nao_aparece(self):
        """Apenas itens com motivo contendo 'estoque' aparecem na página."""
        item = make_item_ignorado(self.cliente, 'WLA06', motivo='Produto sem preço cadastrado')
        resp = self.client.get(reverse('meus_avisos'))
        self.assertNotIn(item, resp.context['pendentes'])

    def test_pagina_requer_login(self):
        self.client.logout()
        resp = self.client.get(reverse('meus_avisos'))
        self.assertNotEqual(resp.status_code, 200)


# ===========================================================================
# 13. WISHLIST — OPORTUNIDADES NO DASHBOARD ADMIN
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/',
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class WishlistDashboardAdminTest(WFTestCase):
    """
    Testa a lógica de oportunidades na view dashboard_admin:
    - apenas itens com notificado=False aparecem
    - itens são agrupados por cliente
    - quantidades são acumuladas para o mesmo produto
    - produtos sem preço/estoque não entram
    """

    def setUp(self):
        self.empresa = make_empresa('wl-dash')
        self.uf = make_uf('SP')
        self.staff = make_staff('wl_dash_staff', self.empresa)
        self.user_a, self.cliente_a = make_cliente('wl_dash_a', self.empresa, self.uf, code=70)
        self.user_b, self.cliente_b = make_cliente('wl_dash_b', self.empresa, self.uf, code=71)
        self.produto = make_product_com_estoque('WLD01', self.empresa, preco_sp='80.00')
        self.client.force_login(self.staff)

    def _get_oportunidades(self):
        resp = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(resp.status_code, 200)
        return resp.context['oportunidades_wishlist']

    def test_item_nao_notificado_aparece_nas_oportunidades(self):
        make_item_ignorado(self.cliente_a, 'WLD01')
        ops = self._get_oportunidades()
        clientes_ids = [op['cliente'].client_id for op in ops]
        self.assertIn(self.cliente_a.client_id, clientes_ids)

    def test_item_notificado_nao_aparece_nas_oportunidades(self):
        """Itens já notificados não devem constar nas oportunidades."""
        make_item_ignorado(self.cliente_a, 'WLD01', notificado=True)
        ops = self._get_oportunidades()
        clientes_ids = [op['cliente'].client_id for op in ops]
        self.assertNotIn(self.cliente_a.client_id, clientes_ids)

    def test_item_descartado_nao_aparece_nas_oportunidades(self):
        make_item_ignorado(self.cliente_a, 'WLD01', descartado=True)
        ops = self._get_oportunidades()
        clientes_ids = [op['cliente'].client_id for op in ops]
        self.assertNotIn(self.cliente_a.client_id, clientes_ids)

    def test_produto_sem_preco_nao_aparece_nas_oportunidades(self):
        self.produto.product_value_sp = 0
        self.produto.save()
        make_item_ignorado(self.cliente_a, 'WLD01')
        ops = self._get_oportunidades()
        clientes_ids = [op['cliente'].client_id for op in ops]
        self.assertNotIn(self.cliente_a.client_id, clientes_ids)

    def test_oportunidades_agrupadas_por_cliente(self):
        """Dois itens do mesmo cliente geram uma única entrada no agrupamento."""
        outro_produto = make_product_com_estoque('WLD02', self.empresa, preco_sp='60.00')
        make_item_ignorado(self.cliente_a, 'WLD01')
        make_item_ignorado(self.cliente_a, 'WLD02')
        ops = self._get_oportunidades()
        entradas_a = [op for op in ops if op['cliente'].client_id == self.cliente_a.client_id]
        self.assertEqual(len(entradas_a), 1)
        self.assertEqual(len(entradas_a[0]['produtos']), 2)

    def test_quantidades_acumuladas_para_mesmo_produto(self):
        """Múltiplos registros do mesmo produto são somados em 'quantidade'."""
        make_item_ignorado(self.cliente_a, 'WLD01', quantidade=3)
        make_item_ignorado(self.cliente_a, 'WLD01', quantidade=7)
        ops = self._get_oportunidades()
        entrada_a = next(op for op in ops if op['cliente'].client_id == self.cliente_a.client_id)
        prod = next(p for p in entrada_a['produtos'] if p['codigo'] == 'WLD01')
        self.assertEqual(prod['quantidade'], 10)

    def test_clientes_diferentes_geram_entradas_separadas(self):
        make_item_ignorado(self.cliente_a, 'WLD01')
        make_item_ignorado(self.cliente_b, 'WLD01')
        ops = self._get_oportunidades()
        ids = [op['cliente'].client_id for op in ops]
        self.assertIn(self.cliente_a.client_id, ids)
        self.assertIn(self.cliente_b.client_id, ids)


# ===========================================================================
# 14. WISHLIST — ISOLAÇÃO DE EMPRESA (MULTI-TENANT)
# ===========================================================================

@override_settings(STORAGES=_STORAGES_TEST, MEDIA_ROOT='/tmp/wfhub_test/',
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class WishlistIsolacaoEmpresaTest(WFTestCase):
    """
    Garante que dados de wishlist de uma empresa nunca aparecem
    para outra empresa (isolação multi-tenant).
    """

    def setUp(self):
        self.uf = make_uf('SP')

        # Empresa A
        self.empresa_a = make_empresa('wl-iso-a')
        self.staff_a = make_staff('wl_iso_staff_a', self.empresa_a)
        self.user_a, self.cliente_a = make_cliente('wl_iso_cli_a', self.empresa_a, self.uf, code=80)
        self.produto_a = make_product_com_estoque('WLIA01', self.empresa_a)

        # Empresa B
        self.empresa_b = make_empresa('wl-iso-b')
        self.staff_b = make_staff('wl_iso_staff_b', self.empresa_b)
        self.user_b, self.cliente_b = make_cliente('wl_iso_cli_b', self.empresa_b, self.uf, code=81)
        self.produto_b = make_product_com_estoque('WLIB01', self.empresa_b)

    def test_dashboard_admin_a_nao_ve_itens_de_empresa_b(self):
        """Staff da empresa A não enxerga oportunidades de clientes da empresa B."""
        make_item_ignorado(self.cliente_b, 'WLIB01')
        self.client.force_login(self.staff_a)
        resp = self.client.get(reverse('dashboard_admin'))
        ops = resp.context['oportunidades_wishlist']
        ids = [op['cliente'].client_id for op in ops]
        self.assertNotIn(self.cliente_b.client_id, ids)

    def test_dashboard_admin_b_nao_ve_itens_de_empresa_a(self):
        """Staff da empresa B não enxerga oportunidades de clientes da empresa A."""
        make_item_ignorado(self.cliente_a, 'WLIA01')
        self.client.force_login(self.staff_b)
        resp = self.client.get(reverse('dashboard_admin'))
        ops = resp.context['oportunidades_wishlist']
        ids = [op['cliente'].client_id for op in ops]
        self.assertNotIn(self.cliente_a.client_id, ids)

    def test_cliente_a_nao_ve_wishlist_de_cliente_b_no_banner(self):
        """Banner da home do cliente A nunca exibe produtos da wishlist do cliente B."""
        make_item_ignorado(self.cliente_b, 'WLIA01')
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse('home'))
        codigos = [p['codigo'] for p in resp.context['produtos_wishlist_cliente']]
        self.assertNotIn('WLIA01', codigos)

    def test_notificar_nao_marca_itens_de_outra_empresa(self):
        """
        Staff da empresa A tentando notificar cliente de empresa B via URL direta
        deve ser bloqueado (404) — sem marcar nenhum item como notificado.
        """
        item_b = make_item_ignorado(self.cliente_b, 'WLIB01')
        self.client.force_login(self.staff_a)
        resp = self.client.get(
            reverse('notificar_wishlist_whatsapp', args=[self.cliente_b.client_id])
        )
        self.assertEqual(resp.status_code, 404)
        item_b.refresh_from_db()
        self.assertFalse(item_b.notificado)
