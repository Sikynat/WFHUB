from django.urls import path
from . import views


urlpatterns = [
    # URLs do Dashboard
    path('', views.dashboard_admin, name='dashboard_admin'),
    path('todos-os-pedidos/', views.todos_os_pedidos, name='todos_os_pedidos'),
    path('pedidos/hoje/', views.pedidos_para_hoje, name='pedidos_para_hoje'),
    path('exportar-pedidos/', views.exportar_pedidos_excel, name='exportar_pedidos_excel'),

    # URLs de detalhes de pedidos e exportação
    path('detalhes-admin/<int:pedido_id>/', views.detalhes_pedido_admin, name='detalhes_pedido_admin'),
    path('exportar-detalhes/<int:pedido_id>/', views.exportar_detalhes_pedido_admin_excel, name='exportar_detalhes_pedido_admin_excel'),

    # URLs de Pedido Manual e Upload
    path('gerar-pedido-manual/', views.gerar_pedido_manual, name='gerar_pedido_manual'),
    path('processar-pedido-manual/', views.processar_pedido_manual, name='processar_pedido_manual'),
    path('upload-pedido/', views.upload_pedido, name='upload_pedido'),
    path('processar_upload/', views.processar_upload, name='processar_upload'),
    path('pedidos/<int:pedido_id>/upload-orcamento/', views.upload_orcamento_pdf, name='upload_orcamento_pdf'),
    path('atualizar-status/<int:pedido_id>/', views.atualizar_status_pedido, name='atualizar_status_pedido'),
]