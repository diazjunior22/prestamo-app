"""
WSGI config for LoanManager project.
"""
import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Automatically load environment variables from .env file (for PythonAnywhere and production)
try:
    import dotenv
    base_dir = Path(__file__).resolve().parent.parent
    dotenv.load_dotenv(base_dir / '.env')
except Exception:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_wsgi_application()

