web: gunicorn Ecommerce.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 300
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput