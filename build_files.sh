#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
python3.12 -m pip install -r requirements.txt

echo "Running database migrations..."
# This will build the core_invoice table in your Vercel Postgres DB
python3.12 manage.py migrate --noinput

echo "Collecting static files..."
python3.12 manage.py collectstatic --noinput --clear

# Vercel static build expects files in staticfiles_build (configured in vercel.json)
mkdir -p staticfiles_build
cp -r staticfiles/* staticfiles_build/

echo "Build complete."
