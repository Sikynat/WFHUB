from django.contrib import admin
from django.urls import path, include
from wefixhub import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.home, name='home'),
    path('gerar-pedido/', views.gerar_pedido, name='gerar_pedido'),
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
]