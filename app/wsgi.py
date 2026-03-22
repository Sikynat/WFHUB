import os
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

_startup_error = None
_real_application = None

try:
    from django.core.wsgi import get_wsgi_application
    _real_application = get_wsgi_application()
except Exception:
    _startup_error = traceback.format_exc()


def application(environ, start_response):
    if _startup_error:
        body = f"=== DJANGO STARTUP ERROR ===\n\n{_startup_error}".encode("utf-8")
        start_response("500 Internal Server Error", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
    return _real_application(environ, start_response)
