# Install dependencies in a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Collect static files
python3 manage.py collectstatic --noinput

# Cleanup (optional, but good for reducing build size if possible, though Vercel might need it for static build step)
# rm -rf venv
