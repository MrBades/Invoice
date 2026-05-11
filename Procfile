web: gunicorn yeedembooks.wsgi
release: python manage.py migrate --noinput; python manage.py collectstatic --noinput
