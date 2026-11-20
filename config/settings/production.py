"""
Production settings for LoanManager (Neon PostgreSQL, Render, WhiteNoise).
"""
from .base import *
import urllib.parse

DEBUG = False

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-production-fallback-key-replace-in-env')

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '*').split(',') if host.strip()]
for domain in ['.railway.app', '.up.railway.app', '.pythonanywhere.com']:
    if domain not in ALLOWED_HOSTS and '*' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(domain)

# CSRF Trusted Origins (required for form submissions on Railway and PythonAnywhere HTTPS)
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
    'https://*.pythonanywhere.com',
]
for host in ALLOWED_HOSTS:
    if host not in ('*', 'localhost', '127.0.0.1', '.pythonanywhere.com', '.railway.app', '.up.railway.app'):
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

# Database (PostgreSQL if DATABASE_URL or Railway PG variables provided, SQLite fallback)
database_url = os.environ.get('DATABASE_PUBLIC_URL') or os.environ.get('DATABASE_URL')
pghost = os.environ.get('PGHOST') or os.environ.get('DB_HOST')

if database_url and database_url.startswith(('postgres://', 'postgresql://')):
    url = urllib.parse.urlparse(database_url)
    ssl_mode = 'require' if ('sslmode=require' in (url.query or '') or 'rlwy.net' in (url.hostname or '')) else ('disable' if 'railway.internal' in (url.hostname or '') else 'prefer')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': urllib.parse.unquote(url.path[1:]),
            'USER': urllib.parse.unquote(url.username or ''),
            'PASSWORD': urllib.parse.unquote(url.password or ''),
            'HOST': url.hostname or '',
            'PORT': url.port or 5432,
            'OPTIONS': {
                'sslmode': ssl_mode,
            },
            'CONN_MAX_AGE': 600,
        }
    }
elif pghost:
    ssl_mode = 'disable' if 'railway.internal' in pghost else ('require' if 'rlwy.net' in pghost else 'prefer')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('PGDATABASE') or os.environ.get('DB_NAME', 'railway'),
            'USER': os.environ.get('PGUSER') or os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('PGPASSWORD') or os.environ.get('DB_PASSWORD', ''),
            'HOST': pghost,
            'PORT': int(os.environ.get('PGPORT') or os.environ.get('DB_PORT', 5432)),
            'OPTIONS': {
                'sslmode': ssl_mode,
            },
            'CONN_MAX_AGE': 600,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# WhiteNoise production storage (safe for all static assets)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Security settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

