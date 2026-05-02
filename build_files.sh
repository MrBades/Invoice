#!/bin/bash
set -e

echo "Starting build_files.sh..."

# Create virtual environment for build process
python3 -m venv .venv
source .venv/bin/activate

echo "Installing build dependencies..."
# Use the venv's pip to avoid system restrictions
.venv/bin/pip install --upgrade pip
.venv/bin/pip install django whitenoise dj-database-url django-htmx python-dotenv Pillow

# Try to install everything else
.venv/bin/pip install -r requirements.txt || echo "Warning: Full requirements installation failed. Continuing with core dependencies."

echo "Collecting static files..."
# Use the venv's python to ensure django is found
.venv/bin/python3 manage.py collectstatic --noinput

echo "Build finished successfully."
