#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
# Added --break-system-packages to bypass Vercel's uv environment block
python3.12 -m pip install -r requirements.txt --break-system-packages

echo "Running database migrations..."
python3.12 manage.py migrate --noinput

echo "Collecting static files..."
python3.12 manage.py collectstatic --noinput --clear

# Vercel static build expects files in staticfiles_build (configured in vercel.json)
mkdir -p staticfiles_build
cp -r staticfiles/* staticfiles_build/

echo "Build complete."
