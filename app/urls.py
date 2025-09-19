"""
URL configuration for app project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from wefixhub import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('gerar-pedido/', views.gerar_pedido, name='gerar_pedido'),
    path('carrinho/', views.carrinho, name='carrinho'),
    path('remover-item/<int:product_id>/', views.remover_item_carrinho, name='remover_item'),
    path('atualizar-carrinho/', views.atualizar_carrinho, name='atualizar_carrinho'),
    path('limpar-carrinho/', views.limpar_carrinho, name='limpar_carrinho'),
    path('checkout/', views.checkout, name='checkout'),
    path('admin-dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido, name='detalhes_pedido'),
    path('salvar-pedido/', views.salvar_pedido, name='salvar_pedido'),
    path('pedido-concluido/', views.pedido_concluido, name='pedido_concluido'),
    path('pedidos/', views.historico_pedidos, name='pedidos'),
]