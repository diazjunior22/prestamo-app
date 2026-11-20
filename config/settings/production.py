"""
Production settings for LoanManager (Neon PostgreSQL, Render, WhiteNoise).
"""
from .base import *
import urllib.parse

DEBUG = False

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-production-fallback-key-replace-in-env')

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '*').split(',') if host.strip()]
if '.pythonanywhere.com' not in ALLOWED_HOSTS and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.pythonanywhere.com')

# CSRF Trusted Origins (required for form submissions on PythonAnywhere HTTPS)
CSRF_TRUSTED_ORIGINS = ['https://*.pythonanywhere.com']
for host in ALLOWED_HOSTS:
    if host not in ('*', 'localhost', '127.0.0.1', '.pythonanywhere.com'):
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

# Database (PostgreSQL if DATABASE_URL provided, SQLite fallback for PythonAnywhere)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith(('postgres://', 'postgresql://')):
    url = urllib.parse.urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username or '',
            'PASSWORD': url.password or '',
            'HOST': url.hostname or '',
            'PORT': url.port or 5432,
            'OPTIONS': {
                'sslmode': 'require' if 'sslmode=require' in (url.query or '') else 'prefer',
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

# WhiteNoise production storage
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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

