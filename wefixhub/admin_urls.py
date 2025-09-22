from django.urls import path
from . import views
urlpatterns = [
    path('', views.dashboard_admin, name='dashboard_admin'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido_admin, name='detalhes_pedido_admin'),
    path('pedidos/exportar/<int:pedido_id>/', views.exportar_detalhes_pedido_admin_excel, name='exportar_detalhes_pedido_admin_excel'),
    path('exportar/', views.exportar_pedidos_excel, name='exportar_pedidos_excel'),
    path('todos-pedidos/', views.todos_os_pedidos, name='todos_os_pedidos'),
    path('atualizar-status-pedido/<int:pedido_id>/', views.atualizar_status_pedido, name='atualizar_status_pedido'),
]