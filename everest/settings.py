import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Базовый URL для тестирования
BASE_URL = 'http://172.20.10.4:8000'

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me')
DEBUG = True
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,172.20.10.4,0.0.0.0,testserver').split(',')
APPEND_SLASH = True 

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'storages',
    'django_prometheus',
    'django_celery_results',
    'partners.apps.PartnersConfig',
    'memorials.apps.MemorialsConfig',
    'assets.apps.AssetsConfig',
    'tributes',
    'shortlinks.apps.ShortlinksConfig',
    'audits.apps.AuditsConfig',
    
]

#Стандартный порядок middleware для Django i18n
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'audits.middleware.AuditMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware', 
    'django_prometheus.middleware.PrometheusAfterMiddleware',
    'everest.middleware.DisableCSRFMiddleware',
]

ROOT_URLCONF = 'everest.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'everest.wsgi.application'
ASGI_APPLICATION = 'everest.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Временное отключение Redis, так как он не работает
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache', 
        'LOCATION': 'unique-snowflake',
    }
}

# Или для Redis (рекомендуется для продакшена):
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#     }
# }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]




LANGUAGE_CODE = 'en'  
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Cookie settings
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60
LANGUAGE_COOKIE_PATH = '/'
LANGUAGE_COOKIE_DOMAIN = None
LANGUAGE_COOKIE_SECURE = False
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = 'Lax'

LANGUAGES = [
    ('de', 'Deutsch'),
    ('fr', 'Français'),
    ('it', 'Italiano'),
    ('en', 'English'),
]


LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_FILE_STORAGE = os.getenv('FILE_STORAGE_BACKEND', 'storages.backends.s3boto3.S3Boto3Storage')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'eu-central-1')
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
AWS_S3_ADDRESSING_STYLE = 'virtual'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_QUERYSTRING_AUTH = True
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'no-referrer'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
        'ai_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'ai_moderation.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'audits.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'tributes': {  
            'handlers': ['ai_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },    
        'tributes.tasks': {
            'handlers': ['ai_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'audits': {
            'handlers': ['audit_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000', 'http://172.20.10.4:8000']
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False 

# === EMAIL SETTINGS ===
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'localhost'  # или другой SMTP сервер
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
#EMAIL_HOST_USER = 'your-email@gmail.com'
#EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@everest-dev.local'

LOGIN_URL = '/admin/login/'

# НАСТРОЙКИ ДЛЯ ИИ-МОДЕРАЦИИ 
# Настройки Ollama (для локальной модели)
OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2:latest')

# Настройки Celery для фоновых задач
CELERY_BROKER_URL = 'redis://localhost:6379/0'  
CELERY_RESULT_BACKEND = 'django-db'  # Используем базу данных Django для хранения результатов
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TASK_ALWAYS_EAGER = False  
CELERY_TASK_EAGER_PROPAGATES = True

AI_MODERATION_SETTINGS = {
    'auto_moderate_new': True,
    'max_retries': 3,
    'timeout_seconds': 60,
    'languages': ['de', 'fr', 'it', 'en'],
    
    # Пороги уверенности для авто-действий
    'confidence_thresholds': {
        'auto_approve': 0.80,    
        'auto_reject': 0.70,     
        'flag': 0.40,            
    },
    
    # Настройки проверки имён - МЯГКИЕ
    'name_verification_strictness': 'strict',
    'name_check': {
        'require_last_name_match': True,      
        'auto_reject_on_wrong_last_name': True,
        'auto_flag_on_partial_name': False,
        'allow_no_name_mention': True,
        'min_name_length': 2,
        'check_for_test_names': True,
    },
    
    
}


# Настройки кэширования и сжатия статики
if not DEBUG:
    # Кэширование статики
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
    
    # Сжатие статики
    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'compressor.finders.CompressorFinder',  
    ]
    
    # В продакшене включаем Redis и нормальный Celery
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        }
    }
    
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_TASK_ALWAYS_EAGER = False  # Отключаем синхронное выполнение


