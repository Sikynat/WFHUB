from django.contrib import admin
from django.urls import path, include
from wefixhub import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.home, name='home'),
    path('carrinho/', views.carrinho, name='carrinho'),
    path('remover-item/<int:product_id>/', views.remover_item_carrinho, name='remover_item'),
    path('atualizar-carrinho/', views.atualizar_carrinho, name='atualizar_carrinho'),
    path('limpar-carrinho/', views.limpar_carrinho, name='limpar_carrinho'),
    path('checkout/', views.checkout, name='checkout'),
    path('pedidos/', views.historico_pedidos, name='pedidos'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido, name='detalhes_pedido'),
    path('pedidos/exportar/<int:pedido_id>/', views.exportar_detalhes_pedido_excel, name='exportar_detalhes_pedido_excel'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('dashboard/', include('wefixhub.admin_urls')),
    path('gerenciar-enderecos/', views.gerenciar_enderecos, name='gerenciar_enderecos'),
    path('editar-endereco/<int:endereco_id>/', views.editar_endereco, name='editar_endereco'), 
    path('salvar-pedido/', views.salvar_pedido, name='salvar_pedido'),
    path('pedido-concluido/', views.pedido_concluido, name='pedido_concluido'),
    path('upload/', views.pagina_upload, name='pagina_upload'),
    path('processar_upload/', views.processar_upload, name='processar_upload'),
    path('pedidos/exportar/<int:pedido_id>/', views.exportar_detalhes_pedido_cliente_excel, name='exportar_pedido_cliente_excel'),
    path('gerar-pedido/', views.gerar_pedido, name='gerar_pedido'),
    path('dashboard/detalhes-admin/<int:pedido_id>/', views.detalhes_pedido_admin, name='detalhes_pedido_admin'),
    path('pedidos/hoje/', views.pedidos_para_hoje, name='pedidos_para_hoje'),
    path('gerar-pedido-manual/', views.gerar_pedido_manual, name='gerar_pedido_manual'),
    path('processar-pedido-manual/', views.processar_pedido_manual, name='processar_pedido_manual'),
]