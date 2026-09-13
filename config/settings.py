from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

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
    # Public media (product photos, portfolio images, blog images) goes to Cloudinary.
    # This does NOT affect PRIVATE_MEDIA_ROOT below - CVs stay on local disk on purpose,
    # served only through apps.core.uploads.PrivateStorage and permission-checked views.
    "cloudinary_storage",
    "cloudinary",
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

# Cloudinary credentials for public media only (products, portfolio, blog images).
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": env("CLOUDINARY_API_KEY"),
    "API_SECRET": env("CLOUDINARY_API_SECRET"),
}

STORAGES = {
    # Public media only. Render's disk is ephemeral, so anything under MEDIA_ROOT would be lost
    # on every redeploy without this.
    "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# CVs and requirement documents never live under MEDIA_ROOT, and are NOT covered by the
# Cloudinary STORAGES entry above - PrivateStorage (apps/core/uploads.py) hardcodes this
# local path directly. On Render this means CVs do not survive a redeploy or restart unless
# a persistent disk is mounted at this path. They are served only through permission-checked
# dashboard views.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
# Virus scanning for CVs and requirement documents. ClamAV is the default; the no-op scanner is
# only allowed for local development with DEBUG=True.
UPLOAD_SCAN_HOOK = env(
    "UPLOAD_SCAN_HOOK",
    default="apps.core.uploads.noop_scan" if DEBUG else "apps.core.uploads.clamav_scan",
)
if not DEBUG and UPLOAD_SCAN_HOOK.endswith(".noop_scan"):
    raise ImproperlyConfigured("UPLOAD_SCAN_HOOK=noop_scan is only allowed when DEBUG=True. Configure ClamAV instead.")
CLAMAV_UNIX_SOCKET = env("CLAMAV_UNIX_SOCKET", default="")
CLAMAV_HOST = env("CLAMAV_HOST", default="127.0.0.1")
CLAMAV_PORT = env.int("CLAMAV_PORT", default=3310)
CLAMAV_TIMEOUT = env.int("CLAMAV_TIMEOUT", default=30)
CV_RETENTION_DAYS = env.int("CV_RETENTION_DAYS", default=180)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DASHBOARD_PATH = env("DASHBOARD_PATH", default="hq/")
LOGIN_MAX_FAILURES = env.int("LOGIN_MAX_FAILURES", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)
# Number of reverse proxies in front of Django that append to X-Forwarded-For. 0 = ignore the header.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)
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
# DENY everywhere. The only same-origin frame is the staff CV preview, whose view opts in with
# @xframe_options_sameorigin (apps.dashboard.views.application_cv).
X_FRAME_OPTIONS = "DENY"
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
