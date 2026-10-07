from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")


def normalise_url_prefix(value, name="DASHBOARD_PATH"):
    """Accepts "zen", "zen/" or "/zen/" and always returns "zen/".

    Every mount point and every prefix comparison assumes this exact shape, so a stray
    slash in the environment would otherwise silently unmount the staff dashboard.
    """
    cleaned = (value or "").strip().strip("/")
    if not cleaned:
        raise ImproperlyConfigured(f"{name} must not be empty: it is the mount point for the staff dashboard.")
    return f"{cleaned}/"


def cache_config(url="", debug=False):
    """Picks the cache backend. Login lockouts and rate limits live here, so it has to be shared.

    LocMemCache is per worker process and is wiped on restart, which would let an attacker
    reset a lockout simply by landing on another gunicorn worker. It is therefore only used
    for local development; production falls back to the database cache when no CACHE_URL is set.
    """
    if url:
        if url.startswith(("redis://", "rediss://", "unix://")):
            return {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": url}
        return env.cache_url_config(url)
    if debug:
        return {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "zencraft"}
    return {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "zencraft_cache"}

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
    "django_otp",
    "django_otp.plugins.otp_totp",
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
    "apps.core.logging.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves the collected static files in production. In development and in tests
    # django.contrib.staticfiles does it, and WhiteNoise would only warn that STATIC_ROOT is
    # not there yet, which is true and not interesting.
    *([] if DEBUG else ["whitenoise.middleware.WhiteNoiseMiddleware"]),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Adds request.user.is_verified(); the staff gate enforces it when STAFF_2FA_REQUIRED is on.
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
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

# Public media (product photos, portfolio images, blog images) goes to Cloudinary when it is
# configured, which is required on Render: its disk is ephemeral, so anything under MEDIA_ROOT would
# be lost on every redeploy. Local development, tests and CI have no Cloudinary account, so they fall
# back to local file storage instead of failing to start.
# This does NOT affect PRIVATE_MEDIA_ROOT below - CVs stay on local disk on purpose,
# served only through apps.core.uploads.PrivateStorage and permission-checked views.
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME", default="")
USE_CLOUDINARY = bool(CLOUDINARY_CLOUD_NAME)

if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        # Required once a cloud name is set, so a half-configured deploy fails loudly at startup.
        "API_KEY": env("CLOUDINARY_API_KEY"),
        "API_SECRET": env("CLOUDINARY_API_SECRET"),
    }
    _rf = INSTALLED_APPS.index("rest_framework") + 1
    INSTALLED_APPS[_rf:_rf] = ["cloudinary_storage", "cloudinary"]

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"
        if USE_CLOUDINARY
        else "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# CVs and requirement documents are never public and never go through the Cloudinary STORAGES
# entry above. They are streamed by permission-checked dashboard views, never linked directly.
#
# PRIVATE_STORAGE_BACKEND picks where the bytes actually live:
#   "local" - PRIVATE_MEDIA_ROOT on disk. Correct for development. On a host with an ephemeral
#             disk, such as Render, this loses every CV on the next deploy, so a deploy check
#             refuses it unless PRIVATE_MEDIA_PERSISTENT says a real disk is mounted there.
#   "s3"    - any S3-compatible bucket (AWS, Cloudflare R2, Backblaze B2, DigitalOcean Spaces),
#             private, with signed URLs that expire in minutes. Nothing hands those URLs to a
#             browser; they exist so the application itself can read the object back.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
PRIVATE_STORAGE_BACKEND = env("PRIVATE_STORAGE_BACKEND", default="local")
PRIVATE_MEDIA_PERSISTENT = env.bool("PRIVATE_MEDIA_PERSISTENT", default=False)
PRIVATE_S3 = {
    "bucket_name": env("PRIVATE_S3_BUCKET", default=""),
    "region_name": env("PRIVATE_S3_REGION", default=""),
    "endpoint_url": env("PRIVATE_S3_ENDPOINT_URL", default="") or None,
    "access_key": env("PRIVATE_S3_ACCESS_KEY", default=""),
    "secret_key": env("PRIVATE_S3_SECRET_KEY", default=""),
    "location": env("PRIVATE_S3_PREFIX", default="private"),
    "querystring_expire": env.int("PRIVATE_S3_URL_SECONDS", default=300),
}
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
IMAGE_UPLOAD_MAX_BYTES = env.int("IMAGE_UPLOAD_MAX_BYTES", default=4 * 1024 * 1024)
# Virus scanning for CVs and requirement documents.
#   "strict"     - scan during the upload and refuse the file if the scanner is unreachable.
#                  Needs a ClamAV daemon the web process can talk to.
#   "quarantine" - accept and store the upload, but mark it unscanned and refuse to serve it to
#                  staff until `manage.py scan_quarantined_uploads` has cleared it. For hosts
#                  where the web service cannot run ClamAV, which includes a plain Render service.
#   "off"        - no scanning at all. Local development only.
UPLOAD_SCAN_MODE = env("UPLOAD_SCAN_MODE", default="off" if DEBUG else "strict")
if UPLOAD_SCAN_MODE not in {"strict", "quarantine", "off"}:
    raise ImproperlyConfigured(f"UPLOAD_SCAN_MODE must be strict, quarantine or off, not {UPLOAD_SCAN_MODE!r}.")
if not DEBUG and UPLOAD_SCAN_MODE == "off":
    raise ImproperlyConfigured("UPLOAD_SCAN_MODE=off is only allowed when DEBUG=True.")
UPLOAD_SCAN_HOOK = env(
    "UPLOAD_SCAN_HOOK",
    default="apps.core.uploads.noop_scan" if UPLOAD_SCAN_MODE == "off" else "apps.core.uploads.clamav_scan",
)
if not DEBUG and UPLOAD_SCAN_HOOK.endswith(".noop_scan"):
    raise ImproperlyConfigured("UPLOAD_SCAN_HOOK=noop_scan is only allowed when DEBUG=True. Configure ClamAV instead.")
CLAMAV_UNIX_SOCKET = env("CLAMAV_UNIX_SOCKET", default="")
CLAMAV_HOST = env("CLAMAV_HOST", default="127.0.0.1")
CLAMAV_PORT = env.int("CLAMAV_PORT", default=3310)
CLAMAV_TIMEOUT = env.int("CLAMAV_TIMEOUT", default=30)
CV_RETENTION_DAYS = env.int("CV_RETENTION_DAYS", default=180)
# Project inquiries that never became projects. The privacy policy promises 24 months.
INQUIRY_RETENTION_DAYS = env.int("INQUIRY_RETENTION_DAYS", default=730)
# How long one email address has to wait before applying for the same role again. A permanent
# block would let anyone lock a real candidate out of a role for good by using their address.
CAREERS_REAPPLY_DAYS = env.int("CAREERS_REAPPLY_DAYS", default=30)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DASHBOARD_PATH = normalise_url_prefix(env("DASHBOARD_PATH", default="hq/"))
LOGIN_MAX_FAILURES = env.int("LOGIN_MAX_FAILURES", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)
# Number of reverse proxies in front of Django that append to X-Forwarded-For. 0 = ignore the header.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)
# Staff sessions expire a fixed time after signing in, however active the person has been.
# Applied by the staff gate only, so a visitor's cart is not thrown away with it.
STAFF_SESSION_HOURS = env.int("STAFF_SESSION_HOURS", default=8)
# Turn on once every staff account has enrolled a TOTP app; until then they would lock themselves out.
STAFF_2FA_REQUIRED = env.bool("STAFF_2FA_REQUIRED", default=False)
OTP_TOTP_ISSUER = env("OTP_TOTP_ISSUER", default="Zencraft Solution")
LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:overview"

CACHES = {"default": cache_config(env("CACHE_URL", default=""), debug=DEBUG)}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
if env("EMAIL_URL", default=""):
    vars().update(env.email_url("EMAIL_URL"))
# A hung SMTP server must not hold a web worker open while an applicant waits on a spinner.
# Every send also goes through apps.core.mail, which logs a failure instead of swallowing it.
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
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

# Content-Security-Policy. Scripts are allow-listed by nonce, so no 'unsafe-inline' for scripts:
# an injected <script> has no nonce and will not run. Styles still need 'unsafe-inline' because the
# templates use style="..." attributes throughout; that is a far smaller risk than script injection.
CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=False)
CSP_REPORT_URI = env("CSP_REPORT_URI", default="")
# Hosts the payment step posts a form to. Redirect-based gateways (Khalti, Stripe) are not covered
# by form-action, but are listed so switching one to a POST form does not silently break checkout.
CSP_PAYMENT_HOSTS = [
    "https://epay.esewa.com.np",
    "https://rc-epay.esewa.com.np",
    "https://khalti.com",
    "https://*.khalti.com",
    "https://checkout.stripe.com",
]
CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    # jsdelivr: GSAP. cdnjs: highlight.js on case study pages.
    "script-src": ["'self'", "{nonce}", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
    # Fonts and icons are served from this origin now, so no third party can supply either.
    "style-src": ["'self'", "'unsafe-inline'"],
    "font-src": ["'self'", "data:"],
    "img-src": [
        "'self'",
        "data:",
        "blob:",
        "https://res.cloudinary.com",
        "https://images.unsplash.com",
        "https://picsum.photos",
        "https://fastly.picsum.photos",
        "https://cdn.jsdelivr.net",
        "https://cdn.simpleicons.org",
    ],
    "connect-src": ["'self'"],
    "media-src": ["'self'"],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    # The staff CV preview frames a same-origin view; nothing else is framed.
    "frame-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'", *CSP_PAYMENT_HOSTS],
}
# upgrade-insecure-requests is added by the middleware, from settings.DEBUG at request time
# rather than at import time, so the policy is right under override_settings and in any
# configuration that flips DEBUG after startup.

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

LOG_LEVEL = env("LOG_LEVEL", default="INFO")
# Plain text is readable in a terminal; JSON is what a log search backend can actually query.
LOG_FORMAT = env("LOG_FORMAT", default="text" if DEBUG else "json")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIDFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
        "text": {"format": "%(levelname)s %(asctime)s %(name)s [%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": LOG_FORMAT, "filters": ["request_id"]},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # The access log is the host's job; this keeps Django's own 4xx/5xx warnings.
        "django.server": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# Error reporting. Off until SENTRY_DSN is set, and scrubbed of personal data when it is.
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development" if DEBUG else "production")
SENTRY_RELEASE = env("SENTRY_RELEASE", default="")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
if SENTRY_DSN:
    from apps.core.observability import init_sentry

    init_sentry(SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_RELEASE, SENTRY_TRACES_SAMPLE_RATE)
