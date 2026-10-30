from pathlib import Path
import os
from django.db import connections
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent
Temp_Dir=os.path.join(BASE_DIR,'TEMP')
Static_Dir=os.path.join(BASE_DIR,'static')

SECRET_KEY =config("SECRET_KEY")

DEBUG = True
ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "camerain_app.apps.CamerainAppConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "camerain.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Temp_Dir],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "camerain.wsgi.application"


# Database connection
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER":config("DB_USER"),
        "PASSWORD":config("DB_PASS"),
        "HOST":config("DB_HOST"),
        "PORT":config("DB_PORT")
    }
}




# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS=[BASE_DIR / "static",]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATA_UPLOAD_MAX_NUMBER_FIELDS = 100000


ATTENDANCE_COOLDOWN_MINUTES = float(os.getenv("ATTENDANCE_COOLDOWN_MINUTES", 0.1))
ATTENDANCE_API_URL = config('ATTENDANCE_API_URL')
API_USERNAME = config('API_USERNAME')
API_PASSWORD = config('API_PASSWORD')
NUM_GPUS = int(config('NUM_GPUS', default=1))  # Default to 1 if not set

# MAX_FACES = config('MAX_FACES')
# DETECT_EVERY_N = config ('DETECT_EVERY_N')

