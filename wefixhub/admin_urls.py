# wefixhub/admin_urls.py

from django.urls import path
from . import views # Importação relativa correta

urlpatterns = [
    path('', views.dashboard_admin, name='dashboard_admin'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido_admin, name='detalhes_pedido_admin'),
    path('exportar-pedidos/', views.exportar_pedidos_excel, name='exportar_pedidos_excel'),
]