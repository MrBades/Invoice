import os
from django.core.wsgi import get_wsgi_application

# Set the default settings module for the project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yeedembooks.settings')

# Initialize the WSGI application
application = get_wsgi_application()
app = application  # Crucial: Vercel needs this 'app' variable to find your project!

# Serverless Database Auto-Migration Hook
try:
    from django.core.management import call_command
    print("Initializing serverless database build synchronization...")
    
    # This automatically runs 'python manage.py migrate' every time Vercel deploys
    call_command('migrate', interactive=False)
    
    print("Serverless database tables synced successfully!")
except Exception as e:
    print(f"Automatic migration hook failed: {e}")
