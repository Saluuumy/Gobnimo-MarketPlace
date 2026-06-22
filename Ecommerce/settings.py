from pathlib import Path
import environ
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# ENVIRONMENT
# =========================
env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(str(BASE_DIR / ".env"))

# =========================
# SECURITY
# =========================
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "waaheen-d8bzabe3fehygpgg.westeurope-01.azurewebsites.net",
    ],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://waaheen-d8bzabe3fehygpgg.westeurope-01.azurewebsites.net",
    ],
)

# =========================
# APPLICATIONS
# =========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # MUST be before staticfiles
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "base.apps.BaseConfig",
    # ALLAUTH
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # STORAGE
    "storages",
]

AUTH_USER_MODEL = "base.User"

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # right after SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "Ecommerce.urls"

# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "base.context_processors.unread_notifications",
                "base.context_processors.user_counts",
            ],
        },
    },
]

WSGI_APPLICATION = "Ecommerce.wsgi.application"

# =========================
# DATABASE
# =========================
DATABASE_URL = env("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# =========================
# PASSWORD VALIDATION
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# INTERNATIONALIZATION
# =========================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =========================
# STATIC FILES (WhiteNoise — never Azure)
# =========================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# =========================
# MEDIA FILES (Azure Blob in production, local in dev)
# =========================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AZURE_STORAGE_CONNECTION_STRING = env("AZURE_STORAGE_CONNECTION_STRING", default="")

if AZURE_STORAGE_CONNECTION_STRING:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "connection_string": AZURE_STORAGE_CONNECTION_STRING,
                "azure_container": env("AZURE_CONTAINER", default="media"),
                "overwrite_files": True,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {
                "location": str(MEDIA_ROOT),
                "base_url": MEDIA_URL,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# =========================
# DEFAULT AUTO FIELD
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# SECURITY (PRODUCTION / AZURE)
# =========================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
USE_X_FORWARDED_HOST = True

# =========================
# SITE / ALLAUTH
# =========================
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Adver Platform] "

LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# =========================
# EMAIL (SENDGRID)
# =========================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = env("SENDGRID_API_KEY", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="salmamacash@gmail.com")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# =========================
# PASSWORD RESET
# =========================
PASSWORD_RESET_TIMEOUT = 172800  # 48 hours

# =========================
# LOGGING
# =========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",  # logs full 500 tracebacks to Azure console
            "propagate": False,
        },
        "django.core.mail": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "storages": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}