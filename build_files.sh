#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing requirements..."
python3.12 -m pip install -r requirements.txt

echo "Collecting static files..."
python3.12 manage.py collectstatic --noinput --clear

# Note: Vercel static build expects files in staticfiles_build (configured in vercel.json)
# We move them there to be sure
mkdir -p staticfiles_build
cp -r staticfiles/* staticfiles_build/

echo "Build complete."
