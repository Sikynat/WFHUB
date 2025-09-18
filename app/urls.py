"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
    path('pedido-concluido/', views.pedido_concluido, name='pedido_concluido'),
    path('salvar-pedido/', views.salvar_pedido, name='salvar_pedido'),
    path('pedidos/', views.historico_pedidos, name='pedidos'),
    path('pedidos/<int:pedido_id>/', views.detalhes_pedido, name='detalhes_pedido'),
]



