"""Deploy checks for the settings that silently break a production deployment.

Each of these produces a site that boots and serves pages, which is what makes them worth a
check: nothing errors, the damage shows up later as absolute URLs pointing at localhost, media
that disappears on redeploy, email that is printed to a log nobody reads, or lockout counters
that reset. They run only under `manage.py check --deploy`, and only when DEBUG is off.
"""

from django.conf import settings
from django.core.checks import Error, Tags, register

LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")  # noqa: S104  # nosec B104 - a list to reject, not an address to bind


def _production():
    return not settings.DEBUG


@register(Tags.urls, deploy=True)
def check_site_url(app_configs, **kwargs):
    """SITE_URL ends up in canonical tags, sitemaps, emails and payment callbacks."""
    if not _production():
        return []
    url = (getattr(settings, "SITE_URL", "") or "").strip()
    if not url:
        return [Error("SITE_URL is not set.", hint="Set SITE_URL to the public https URL of the site.", id="zencraft.E001")]
    problems = []
    if any(host in url for host in LOCAL_HOSTS):
        problems.append(Error(
            f"SITE_URL points at a local address ({url}).",
            hint="Canonical tags, the sitemap and payment return URLs would all point at the server itself.",
            id="zencraft.E002",
        ))
    if not url.startswith("https://"):
        problems.append(Error(
            f"SITE_URL is not https ({url}).",
            hint="Set SITE_URL to the https URL; browsers and payment gateways reject plain http returns.",
            id="zencraft.E003",
        ))
    return problems


@register(Tags.files, deploy=True)
def check_media_storage(app_configs, **kwargs):
    """Without Cloudinary, uploaded images live on a disk that is wiped on every redeploy."""
    if not _production() or getattr(settings, "USE_CLOUDINARY", False):
        return []
    return [Error(
        "Media storage is the local filesystem.",
        hint=(
            "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET. On a host with "
            "an ephemeral disk, such as Render, every uploaded image is lost on the next deploy."
        ),
        id="zencraft.E004",
    )]


@register(Tags.files, deploy=True)
def check_private_storage(app_configs, **kwargs):
    """CVs on a container's own disk are gone at the next deploy, and nobody is told."""
    if not _production() or getattr(settings, "PRIVATE_STORAGE_BACKEND", "local") != "local":
        return []
    if getattr(settings, "PRIVATE_MEDIA_PERSISTENT", False):
        return []
    return [Error(
        "Private uploads (CVs, requirement documents) are stored on the local filesystem.",
        hint=(
            "Set PRIVATE_STORAGE_BACKEND=s3 with the PRIVATE_S3_* settings, then run "
            "`manage.py migrate_private_files`. If a persistent disk really is mounted at "
            "PRIVATE_MEDIA_ROOT, set PRIVATE_MEDIA_PERSISTENT=True to say so."
        ),
        id="zencraft.E008",
    )]


@register(Tags.compatibility, deploy=True)
def check_email_backend(app_configs, **kwargs):
    """The console backend prints email instead of sending it, and nobody notices for weeks."""
    if not _production():
        return []
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend.endswith(("console.EmailBackend", "dummy.EmailBackend", "locmem.EmailBackend")):
        return [Error(
            f"EMAIL_BACKEND is {backend}, which does not send anything.",
            hint="Set EMAIL_URL (or EMAIL_BACKEND and the SMTP settings) so order and application emails reach people.",
            id="zencraft.E005",
        )]
    return []


@register(Tags.caches, deploy=True)
def check_cache_backend(app_configs, **kwargs):
    """Login lockouts and rate limits are only as shared as the cache they are stored in."""
    if not _production():
        return []
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if backend.endswith("locmem.LocMemCache"):
        return [Error(
            "The default cache is LocMemCache.",
            hint=(
                "It is per worker process and is wiped on restart, so an attacker can reset a login "
                "lockout by retrying. Leave CACHE_URL empty to use the database cache (and run "
                "`manage.py createcachetable` in the build), or point it at Redis."
            ),
            id="zencraft.E006",
        )]
    return []


@register(Tags.caches, deploy=True)
def check_cache_is_usable(app_configs, **kwargs):
    """The cache must actually answer, not just be configured.

    The database cache needs a table that `createcachetable` creates as a separate build step.
    Configured but missing, everything looks right until the first write, which on one deploy
    was `cache.clear()` at the end of seeding and took the whole build down with it.
    """
    if not _production():
        return []
    from django.core.cache import cache

    probe = "zencraft-deploy-check"
    try:
        cache.set(probe, "ok", 5)
        value = cache.get(probe)
        cache.delete(probe)
    except Exception as exc:  # a missing table, an unreachable Redis, a bad URL: all fatal here
        return [Error(
            f"The cache is configured but not usable: {exc.__class__.__name__}: {exc}",
            hint=(
                "With the database cache, add `python manage.py createcachetable` to the build "
                "command, before any command that touches the cache."
            ),
            id="zencraft.E009",
        )]
    if value != "ok":
        return [Error(
            "The cache accepted a write but did not return it.",
            hint="Check CACHE_URL and that the backend is reachable.",
            id="zencraft.E010",
        )]
    return []


@register(Tags.security, deploy=True)
def check_upload_scanning(app_configs, **kwargs):
    """Quarantine mode is a deliberate choice, not something to drift into unnoticed."""
    if not _production():
        return []
    hook = getattr(settings, "UPLOAD_SCAN_HOOK", "")
    if hook.endswith(".noop_scan"):
        return [Error(
            "UPLOAD_SCAN_HOOK accepts every file without scanning it.",
            hint="Use apps.core.uploads.clamav_scan, or UPLOAD_SCAN_MODE=quarantine to hold files until a scanner sees them.",
            id="zencraft.E007",
        )]
    return []
