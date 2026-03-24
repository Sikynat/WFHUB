from datetime import date
from django.contrib.auth import logout
from django.shortcuts import redirect
from .models import PerfilUsuario

ROTAS_LIVRES = {'/accounts/login/', '/accounts/logout/', '/saas/acesso-bloqueado/'}


class EmpresaMiddleware:
    """
    Identifica a empresa do usuário logado e anexa ao request.
    - Superuser: request.empresa = None (acesso global)
    - Staff com PerfilUsuario: request.empresa = empresa do perfil
    - Cliente (WfClient): request.empresa = empresa do cliente
    - Não autenticado: request.empresa = None
    Bloqueia clientes com client_is_active=False.
    Bloqueia empresas expiradas ou inativas (salvo acesso_permanente).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa = None

        if request.user.is_authenticated and not request.user.is_superuser:
            # Tenta via PerfilUsuario (representante da empresa)
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

            # Bloqueia empresa inativa ou expirada (para staff e clientes)
            if request.empresa is not None and request.path not in ROTAS_LIVRES:
                empresa = request.empresa
                if not empresa.acesso_permanente:
                    bloqueada = not empresa.ativo
                    if not bloqueada and empresa.expira_em:
                        bloqueada = empresa.expira_em < date.today()
                    if bloqueada:
                        return redirect('/saas/acesso-bloqueado/')

        request.is_impersonando = bool(request.session.get('impersonando_su_id'))

        response = self.get_response(request)
        return response
