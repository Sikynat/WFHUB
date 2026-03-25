web: python manage.py migrate --noinput && gunicorn app.wsgi --bind 0.0.0.0:$PORT --timeout 120 --workers 2
