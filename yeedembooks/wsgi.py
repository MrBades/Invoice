import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yeedembooks.settings")

try:
    application = get_wsgi_application()
    app = application
except Exception as e:
    import traceback
    error_msg = f"Error during WSGI application initialization:\n{traceback.format_exc()}"
    print(error_msg, file=sys.stderr)

    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [error_msg.encode('utf-8')]
