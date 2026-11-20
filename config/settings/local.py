"""
Local development settings for LoanManager.
"""
from .base import *
import urllib.parse

DEBUG = True

database_url = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')
pghost = os.getenv('PGHOST') or os.getenv('DB_HOST')

if database_url and database_url.startswith(('postgres://', 'postgresql://')):
    # Parse PostgreSQL connection URL
    url = urllib.parse.urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': urllib.parse.unquote(url.path[1:]),
            'USER': urllib.parse.unquote(url.username or ''),
            'PASSWORD': urllib.parse.unquote(url.password or ''),
            'HOST': url.hostname or 'localhost',
            'PORT': url.port or 5432,
            'OPTIONS': {
                'sslmode': 'require' if 'sslmode=require' in (url.query or '') or 'rlwy.net' in (url.hostname or '') else 'prefer',
            }
        }
    }
elif pghost:
    # Support individual Railway PostgreSQL variables
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('PGDATABASE') or os.getenv('DB_NAME', 'railway'),
            'USER': os.getenv('PGUSER') or os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD', ''),
            'HOST': pghost,
            'PORT': int(os.getenv('PGPORT') or os.getenv('DB_PORT', 5432)),
            'OPTIONS': {
                'sslmode': 'require' if 'rlwy.net' in pghost else 'prefer',
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

# Email backend: uses SMTP if Gmail credentials are provided in .env, otherwise console for development
if not (os.getenv('EMAIL_HOST_USER') and os.getenv('EMAIL_HOST_PASSWORD')):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

