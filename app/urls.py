from django.contrib import admin
from django.urls import path, include
from wefixhub import views
from django.conf.urls.static import static
from django.conf import settings



urlpatterns = [
    # Rotas de administração
    path('admin/', admin.site.urls),
    path('dashboard/', include('wefixhub.admin_urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('pedido/<int:pedido_id>/whatsapp-excel/', views.exportar_detalhes_pedido_whatsapp_excel, name='exportar_detalhes_pedido_whatsapp_excel'),
    path('analise/vendas-detalhadas/', views.listar_vendas_reais, name='listar_vendas_reais'),
    path('analise/vendas-detalhadas/exportar/', views.exportar_vendas_reais_excel, name='exportar_vendas_reais_excel'),
    path('analise/upload-vendas/', views.upload_vendas_reais, name='upload_vendas_reais'),
    path('analise/graficos/', views.dashboard_analise, name='dashboard_analise'),
    path('analise/sugestoes-admin/', views.sugestoes_admin, name='sugestoes_admin'),
    path('analise/upload-status-pdf/', views.upload_status_pdf, name='upload_status_pdf'),
    path('analise/monitoramento-erp/', views.listar_status_erp, name='listar_status_erp'),
    path('analise/exportar-erp-excel/', views.exportar_status_erp_excel, name='exportar_status_erp_excel'),
    path('analise/pedidos-nao-expedidos/', views.pedidos_nao_expedidos, name='pedidos_nao_expedidos'),
    path('clientes/', views.listar_clientes, name='listar_clientes'),
    path('clientes/novo/', views.cadastrar_cliente, name='cadastrar_cliente'),
    path('clientes/<int:client_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('saas/', views.saas_dashboard, name='saas_dashboard'),
    path('saas/empresas/', views.listar_empresas, name='listar_empresas'),
    path('saas/empresas/nova/', views.cadastrar_empresa, name='cadastrar_empresa'),
    path('saas/empresas/<int:empresa_id>/', views.detalhe_empresa, name='detalhe_empresa'),
    path('saas/empresas/<int:empresa_id>/toggle-ativo/', views.toggle_empresa_ativo, name='toggle_empresa_ativo'),
    path('saas/empresas/<int:empresa_id>/adicionar-membro/', views.adicionar_membro_empresa, name='adicionar_membro_empresa'),
    path('saas/empresas/<int:empresa_id>/remover-membro/<int:membro_id>/', views.remover_membro_empresa, name='remover_membro_empresa'),
    path('saas/empresas/<int:empresa_id>/impersonar/<int:membro_id>/', views.impersonar_membro, name='impersonar_membro'),
    path('saas/empresas/<int:empresa_id>/impersonar-cliente/<int:client_id>/', views.impersonar_cliente, name='impersonar_cliente'),
    path('saas/empresas/<int:empresa_id>/atualizar-plano/', views.atualizar_plano_empresa, name='atualizar_plano_empresa'),
    path('saas/sair-impersonacao/', views.sair_impersonacao, name='sair_impersonacao'),
    path('saas/meu-perfil/', views.perfil_representante, name='perfil_representante'),
    path('saas/acesso-bloqueado/', views.acesso_bloqueado, name='acesso_bloqueado'),
    path('saas/empresas/<int:empresa_id>/toggle-permanente/', views.toggle_acesso_permanente, name='toggle_acesso_permanente'),
    path('saas/empresas/<int:empresa_id>/checkout/', views.criar_checkout_stripe, name='criar_checkout_stripe'),
    path('saas/stripe/sucesso/', views.stripe_sucesso, name='stripe_sucesso'),
    path('saas/stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('notificar-wishlist/<int:cliente_id>/', views.notificar_wishlist_whatsapp, name='notificar_wishlist_whatsapp'),
    path('avisar-quando-disponivel/', views.avisar_quando_disponivel, name='avisar_quando_disponivel'),
    path('novidades/', views.novidades, name='novidades'),
    path('meus-avisos/', views.meus_avisos, name='meus_avisos'),
    path('meus-avisos/cancelar/<int:item_id>/', views.cancelar_aviso, name='cancelar_aviso'),
    path('dashboard/historico-wishlist/', views.historico_wishlist, name='historico_wishlist'),
    path('dashboard/historico-precos/', views.historico_precos, name='historico_precos'),
    path('dashboard/reenviar-whatsapp/<int:cliente_id>/', views.reenviar_notificacao_whatsapp, name='reenviar_notificacao_whatsapp'),
 
    # Rotas do cliente
   path('sugestoes-inteligentes/adicionar-ao-carrinho/', views.adicionar_sugestoes_ao_carrinho, name='adicionar_sugestoes_ao_carrinho'),
   
    path('sugestoes-inteligentes/', views.sugestoes_inteligentes_erp, name='sugestoes_inteligentes_erp'),
    path('adicionar-ao-carrinho-bd/', views.adicionar_ao_carrinho_bd, name='adicionar_ao_carrinho_bd'),
    path('meu-historico/exportar/', views.exportar_meus_itens_excel, name='exportar_meus_itens_excel'),
    path('meu-historico-compras/', views.meus_itens_comprados, name='meus_itens_comprados'),
    path('sugestoes/', views.sugestoes_compra, name='sugestoes_compra'),
    path('', views.home, name='home'),
    path('carrinho/', views.carrinho, name='carrinho'),
    path('remover-item/<int:product_id>/', views.remover_item, name='remover_item'),
    path('atualizar-carrinho/', views.atualizar_carrinho, name='atualizar_carrinho'),
    path('limpar-carrinho/', views.limpar_carrinho, name='limpar_carrinho'),
    path('salvar-pedido/', views.salvar_pedido, name='salvar_pedido'),
    path('pedido-concluido/<int:pedido_id>/', views.pedido_concluido, name='pedido_concluido'),
    path('pedidos/', views.historico_pedidos, name='pedidos'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido, name='detalhes_pedido'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('gerenciar-enderecos/', views.gerenciar_enderecos, name='gerenciar_enderecos'),
    path('editar-endereco/<int:endereco_id>/', views.editar_endereco, name='editar_endereco'),
    path('exportar_detalhes_pedido_cliente_excel/<int:pedido_id>/', views.exportar_detalhes_pedido_cliente_excel, name='exportar_pedido_cliente_excel'),
    path('exportar_publico/excel/<int:pedido_id>/', views.exportar_detalhes_pedido_publico_excel, name='exportar_detalhes_pedido_publico_excel'),
    path('pedido/upload-planilha/', views.upload_pedido_cliente, name='upload_pedido_cliente'),
    path('exportar-recuperados/<int:cliente_id>/', views.exportar_itens_recuperados_excel, name='exportar_itens_recuperados_excel'),
    # Rotas do administrador
    path('dashboard/analise/', views.analise_dados_dashboard, name='analise_dados_dashboard'),
    path('dashboard/pedidos/hoje/', views.pedidos_para_hoje, name='pedidos_para_hoje'),
    path('dashboard/pedidos/rascunhos/', views.pedidos_em_andamento, name='pedidos_em_andamento'),
    path('dashboard/detalhes/<int:pedido_id>/', views.detalhes_pedido_admin, name='detalhes_pedido_admin'),
    path('dashboard/detalhes/<int:pedido_id>/marcar-finalizado/', views.marcar_pedido_finalizado, name='marcar_pedido_finalizado'),
    path('dashboard/detalhes/<int:pedido_id>/whatsapp/', views.enviar_whatsapp, name='enviar_whatsapp'),
    path('dashboard/exportar_detalhes_pedido_admin_excel/<int:pedido_id>/', views.exportar_detalhes_pedido_admin_excel, name='exportar_detalhes_pedido_admin_excel'),

    # Rotas para funcionalidades de upload e geração de pedidos
    path('gerar-pedido-manual/', views.gerar_pedido_manual, name='gerar_pedido_manual'),
    path('processar-pedido-manual/', views.processar_pedido_manual, name='processar_pedido_manual'),
    path('upload-pedido/', views.upload_pedido, name='upload_pedido'),
    path('upload-produtos/', views.pagina_upload, name='pagina_upload'),
    path('processar-upload-produtos/', views.processar_upload, name='processar_upload'),
    path('gerar-pedido/', views.gerar_pedido, name='gerar_pedido'),

    # Rotas de checkout ajustadas para lidar com o rascunho
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/<int:pedido_id_rascunho>/', views.checkout, name='checkout_rascunho'),
    path('continuar-pedido/<int:pedido_id>/', views.continuar_pedido, name='continuar_pedido'),
    path('atualizar-rascunho/', views.atualizar_rascunho, name='atualizar_rascunho'),

    # Tarefas e Colaboração
    path('tarefas/', views.tarefas_board, name='tarefas_board'),
    path('tarefas/produtividade/', views.dashboard_produtividade, name='dashboard_produtividade'),
    path('tarefas/lista/', views.tarefas_lista, name='tarefas_lista'),
    path('tarefas/nova/', views.criar_tarefa, name='criar_tarefa'),
    path('tarefas/<int:tarefa_id>/', views.detalhe_tarefa, name='detalhe_tarefa'),
    path('tarefas/<int:tarefa_id>/editar/', views.editar_tarefa, name='editar_tarefa'),
    path('tarefas/<int:tarefa_id>/status/', views.atualizar_status_tarefa, name='atualizar_status_tarefa'),
    path('tarefas/<int:tarefa_id>/excluir/', views.excluir_tarefa, name='excluir_tarefa'),
    path('tarefas/notificacoes/', views.notificacoes_tarefas, name='notificacoes_tarefas'),
    path('tarefas/tags/', views.gerenciar_tags_tarefa, name='gerenciar_tags_tarefa'),
    path('tarefas/<int:tarefa_id>/checklist/adicionar/', views.adicionar_checklist_item, name='adicionar_checklist_item'),
    path('tarefas/checklist/<int:item_id>/toggle/', views.toggle_checklist_item, name='toggle_checklist_item'),
    path('tarefas/checklist/<int:item_id>/excluir/', views.excluir_checklist_item, name='excluir_checklist_item'),
    path('notificacoes/pedidos/', views.notificacoes_pedidos, name='notificacoes_pedidos'),
    path('tarefas/rapida/', views.criar_tarefa_rapida, name='criar_tarefa_rapida'),
    path('pedidos/<int:pedido_id>/comentar/', views.comentar_pedido, name='comentar_pedido'),
    path('tarefas/<int:tarefa_id>/anexo/', views.upload_anexo_tarefa, name='upload_anexo_tarefa'),
    path('tarefas/anexo/<int:anexo_id>/excluir/', views.excluir_anexo_tarefa, name='excluir_anexo_tarefa'),
    path('auditoria/', views.logs_auditoria, name='logs_auditoria'),
]





if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)