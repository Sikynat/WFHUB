from django.contrib import admin
from django.urls import path, include
from wefixhub import views
from django.conf.urls.static import static
from django.conf import settings  # Importe settings



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
    path('analise/upload-status-pdf/', views.upload_status_pdf, name='upload_status_pdf'),
    path('analise/monitoramento-erp/', views.listar_status_erp, name='listar_status_erp'),
    path('analise/exportar-erp-excel/', views.exportar_status_erp_excel, name='exportar_status_erp_excel'),
    path('notificar-wishlist/<int:cliente_id>/', views.notificar_wishlist_whatsapp, name='notificar_wishlist_whatsapp'),
    path('avisar-quando-disponivel/', views.avisar_quando_disponivel, name='avisar_quando_disponivel'),
    path('meus-avisos/', views.meus_avisos, name='meus_avisos'),
    path('dashboard/historico-wishlist/', views.historico_wishlist, name='historico_wishlist'),
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
    path('pedido-concluido/', views.pedido_concluido, name='pedido_concluido'),
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
    path('atualizar-rascunho/', views.atualizar_rascunho, name='atualizar_rascunho')
 
]





if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)