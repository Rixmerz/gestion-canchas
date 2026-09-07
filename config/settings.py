"""
Configuración de la Prueba de Concepto (PoC).

La PoC NO usa base de datos: `DATABASES` va vacío a propósito y las sesiones
viajan firmadas en la cookie. Toda la persistencia son archivos JSON en `data/`.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# PoC: clave fija, sin DEBUG=False. No usar esto en producción.
SECRET_KEY = "poc-canchas-clave-no-secreta-solo-para-demostracion"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "canchas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# Sin base de datos: las sesiones se firman y viajan en la cookie.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
DATABASES = {}

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

LANGUAGE_CODE = "es-cl"

# RN-07: toda la operación ocurre en horario de Santiago de Chile.
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Parámetros de negocio de la PoC ---------------------------------------
# Directorio donde viven los archivos JSON que hacen de "base de datos".
DIRECTORIO_DATOS = BASE_DIR / "data"
