import os
import logging
from django.core.wsgi import get_wsgi_application

# Set up simple fallback logs for Vercel
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yeedembooks.settings')

# Initialize standard application layout
application = get_wsgi_application()
app = application 

# Safe Execution: Force database schema migrations on a cold container boot
try:
    from django.core.management import call_command
    print("Migrating fresh Vercel Postgres tables to cloud server instance...")
    call_command('migrate', interactive=False)
    print("Database structure successfully applied!")
except Exception as e:
    logger.error(f"Critical Error: Serverless DB Auto-migration failed: {e}")
