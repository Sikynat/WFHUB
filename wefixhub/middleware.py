from django.contrib.auth import logout
from django.shortcuts import redirect
from .models import PerfilUsuario

ROTAS_LIVRES = {'/accounts/login/', '/accounts/logout/'}


class EmpresaMiddleware:
    """
    Identifica a empresa do usuário logado e anexa ao request.
    - Superuser: request.empresa = None (acesso global)
    - Staff com PerfilUsuario: request.empresa = empresa do perfil
    - Cliente (WfClient): request.empresa = empresa do cliente
    - Não autenticado: request.empresa = None
    Bloqueia clientes com client_is_active=False.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa = None

        if request.user.is_authenticated and not request.user.is_superuser:
            # Tenta via PerfilUsuario (admin/staff da empresa)
            try:
                request.empresa = request.user.perfil.empresa
            except PerfilUsuario.DoesNotExist:
                pass

            # Se não achou, tenta via WfClient (cliente da empresa)
            if request.empresa is None:
                try:
                    wfclient = request.user.wfclient
                    request.empresa = wfclient.empresa

                    # Bloqueia clientes inativos
                    if not wfclient.client_is_active and request.path not in ROTAS_LIVRES:
                        logout(request)
                        return redirect('/accounts/login/?inativo=1')
                except Exception:
                    pass

        request.is_impersonando = bool(request.session.get('impersonando_su_id'))

        response = self.get_response(request)
        return response
