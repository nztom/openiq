from pathlib import Path
import os
import secrets
from config.database import database_configuration
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DEBUG', '1') == '1'
ALLOW_LOCAL_LOGIN = os.getenv('ALLOW_LOCAL_LOGIN', '0') == '1'
OPENIQ_VERSION = os.getenv('OPENIQ_VERSION','development')
REQUIRED_PROCESSES = [x for x in os.getenv('REQUIRED_PROCESSES','').split(',') if x in ('bot','scheduler')]
REQUEST_LIMITS_ENABLED = os.getenv('REQUEST_LIMITS_ENABLED','1') == '1'
REQUEST_LIMITS = {name:int(os.getenv('RATE_LIMIT_'+name.upper(),str(value))) for name,value in {'oauth':20,'admin_login':5,'recovery':5,'ocr':10,'mutation':240}.items()}
TRUST_PROXY_HEADERS = os.getenv('TRUST_PROXY','0') == '1'
DATA_DIR = Path(os.getenv('OPENIQ_DATA_DIR',str(BASE_DIR)))
DATA_DIR.mkdir(parents=True,exist_ok=True)
key_file = DATA_DIR / '.secret-key'
if not os.getenv('SECRET_KEY') and not key_file.exists():
    key_file.write_text(secrets.token_urlsafe(64)); key_file.chmod(0o600)
SECRET_KEY = os.getenv('SECRET_KEY') or key_file.read_text()
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if host.strip()]
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','guilds']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','guilds.rate_limits.RequestBudgets','guilds.discord_auth.RefreshDiscordRoles','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASE_BACKEND = os.getenv('DATABASE_BACKEND', '')
DATABASES = {'default': database_configuration(DATA_DIR, os.environ)}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'}]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Pacific/Auckland'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR/'static']
STATIC_ROOT = BASE_DIR/'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = int(os.getenv('SESSION_MAX_AGE','28800'))
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_SAMESITE = 'Lax'
HTTPS = os.getenv('HTTPS','0') == '1'
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SECURE_SSL_REDIRECT = HTTPS
SECURE_HSTS_SECONDS = int(os.getenv('HSTS_SECONDS','3600' if HTTPS else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('HSTS_INCLUDE_SUBDOMAINS','0') == '1'
SECURE_HSTS_PRELOAD = os.getenv('HSTS_PRELOAD','0') == '1'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_REDIRECT_EXEMPT = [r'^healthz/$', r'^readyz/$']
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if x]
if os.getenv('TRUST_PROXY','0') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
if not DEBUG:
    STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 12*1024*1024
DATA_UPLOAD_MAX_NUMBER_FILES = 10
FILE_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
FILE_UPLOAD_HANDLERS = ['guilds.uploads.BoundedUploads','django.core.files.uploadhandler.MemoryFileUploadHandler','django.core.files.uploadhandler.TemporaryFileUploadHandler']
LOGGING = {'version':1,'disable_existing_loggers':False,
           'filters':{'credentials':{'()':'guilds.session_security.RedactCredentials'}},
           'handlers':{'console':{'class':'logging.StreamHandler','filters':['credentials']}},
           'root':{'handlers':['console'],'level':'WARNING'},
           'loggers':{'django.server':{'handlers':['console'],'level':'INFO','propagate':False},
                      'django':{'handlers':['console'],'level':'WARNING','propagate':False}}}
