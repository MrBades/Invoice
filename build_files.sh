pip install -r requirements.txt --break-system-packages || pip install -r requirements.txt
python3 manage.py collectstatic --noinput
