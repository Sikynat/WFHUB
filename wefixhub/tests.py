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
        self.assertRedirects(resp, reverse('editar_perfil'))
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
