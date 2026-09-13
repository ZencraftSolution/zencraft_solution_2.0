from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django.contrib.sitemaps",
    "rest_framework",
    "apps.accounts",
    "apps.core",
    "apps.services",
    "apps.portfolio",
    "apps.commerce",
    "apps.estimator",
    "apps.careers",
    "apps.blog",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.PageViewMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.dashboard.context_processors.dashboard_nav",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# CVs and requirement documents never live under MEDIA_ROOT. They are served
# only through permission-checked dashboard views.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
UPLOAD_SCAN_HOOK = env("UPLOAD_SCAN_HOOK", default="apps.core.uploads.noop_scan")
CV_RETENTION_DAYS = env.int("CV_RETENTION_DAYS", default=180)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DASHBOARD_PATH = env("DASHBOARD_PATH", default="hq/")
LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:overview"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "zencraft"}}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
if env("EMAIL_URL", default=""):
    vars().update(env.email_url("EMAIL_URL"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Zencraft Solution <hello@zencraftsolution.com>")
INTERNAL_NOTIFY_EMAIL = env("INTERNAL_NOTIFY_EMAIL", default="team@zencraftsolution.com")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

PAYMENTS = {
    "ESEWA_PRODUCT_CODE": env("ESEWA_PRODUCT_CODE", default="EPAYTEST"),
    "ESEWA_SECRET_KEY": env("ESEWA_SECRET_KEY", default=""),
    "ESEWA_FORM_URL": env("ESEWA_FORM_URL", default="https://rc-epay.esewa.com.np/api/epay/main/v2/form"),
    "KHALTI_SECRET_KEY": env("KHALTI_SECRET_KEY", default=""),
    "KHALTI_API_URL": env("KHALTI_API_URL", default="https://dev.khalti.com/api/v2/"),
    "STRIPE_SECRET_KEY": env("STRIPE_SECRET_KEY", default=""),
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
