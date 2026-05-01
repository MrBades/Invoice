export PIP_BREAK_SYSTEM_PACKAGES=1
python3 -m pip install -r requirements.txt --break-system-packages
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput
