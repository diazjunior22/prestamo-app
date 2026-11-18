"""
Local development settings for LoanManager.
"""
from .base import *
import urllib.parse

DEBUG = True

database_url = os.getenv('DATABASE_URL')

if database_url and database_url.startswith(('postgres://', 'postgresql://')):
    # Parse PostgreSQL connection
    url = urllib.parse.urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username or '',
            'PASSWORD': url.password or '',
            'HOST': url.hostname or 'localhost',
            'PORT': url.port or 5432,
            'OPTIONS': {
                'sslmode': 'require' if 'sslmode=require' in (url.query or '') else 'prefer',
            }
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Email backend for development (outputs to console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
