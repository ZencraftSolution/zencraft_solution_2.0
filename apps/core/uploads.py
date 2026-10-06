"""Private file storage and upload validation shared by careers and the estimator."""
import io
import logging
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

class PrivateStorage(FileSystemStorage):
    """Filesystem storage with no public URL. Files are streamed by permission-checked views."""

    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        kwargs["base_url"] = None
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def _build_private_storage():
    """Builds the configured private backend. Called once and cached by get_private_storage()."""
    backend = getattr(settings, "PRIVATE_STORAGE_BACKEND", "local")
    if backend == "local":
        return PrivateStorage()
    if backend == "s3":
        from storages.backends.s3 import S3Storage

        config = settings.PRIVATE_S3
        missing = [k for k in ("bucket_name", "access_key", "secret_key") if not config.get(k)]
        if missing:
            raise ImproperlyConfigured(f"PRIVATE_STORAGE_BACKEND=s3 needs {', '.join(missing)}.")
        return S3Storage(
            bucket_name=config["bucket_name"],
            region_name=config["region_name"] or None,
            endpoint_url=config["endpoint_url"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            location=config["location"],
            # Private objects, signed URLs that expire in minutes, and never overwrite: the
            # upload path is already a UUID, so a collision would mean losing someone's CV.
            default_acl="private",
            querystring_auth=True,
            querystring_expire=config["querystring_expire"],
            file_overwrite=False,
        )
    raise ImproperlyConfigured(f"PRIVATE_STORAGE_BACKEND must be 'local' or 's3', not {backend!r}.")


_private_storage_cache = {}


def get_private_storage():
    """The storage every private FileField uses. Cached per backend so tests can switch it."""
    key = (
        getattr(settings, "PRIVATE_STORAGE_BACKEND", "local"),
        str(getattr(settings, "PRIVATE_MEDIA_ROOT", "")),
    )
    if key not in _private_storage_cache:
        _private_storage_cache[key] = _build_private_storage()
    return _private_storage_cache[key]



@deconstructible
class RandomisedPath:
    """Stores uploads under an unguessable UUID name inside a dated folder."""

    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, instance, filename):
        ext = Path(filename).suffix.lower()[:6]
        return f"{self.prefix}/{uuid.uuid4().hex}{ext}"


PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def sniff_document_type(uploaded):
    """Return 'pdf' or 'docx' by inspecting the file bytes, not the name or browser header."""
    uploaded.seek(0)
    head = uploaded.read(8)
    uploaded.seek(0)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            data = io.BytesIO(uploaded.read())
            with zipfile.ZipFile(data) as zf:
                names = set(zf.namelist())
            if "word/document.xml" in names and "[Content_Types].xml" in names:
                return "docx"
        except zipfile.BadZipFile:
            return None
        finally:
            uploaded.seek(0)
    return None


def validate_document(uploaded, allowed=("pdf", "docx"), max_bytes=None):
    max_bytes = max_bytes or settings.UPLOAD_MAX_BYTES
    if uploaded.size > max_bytes:
        raise ValidationError(f"File is too large. The limit is {max_bytes // (1024 * 1024)} MB.")
    ext = Path(uploaded.name).suffix.lower().lstrip(".")
    if ext not in allowed:
        raise ValidationError("Please upload a PDF or DOCX file.")
    detected = sniff_document_type(uploaded)
    if detected is None or detected != ext:
        raise ValidationError("This file does not look like a valid PDF or DOCX document.")
    if scan_mode() != "quarantine":
        # In quarantine mode the file is scanned later, by scan_quarantined_uploads, and is not
        # served to anyone until it has been. See quarantine() and upload_is_servable().
        scan = import_string(settings.UPLOAD_SCAN_HOOK)
        if not scan(uploaded):
            raise ValidationError("The file could not be accepted by our security scan.")
    return detected


def scan_mode():
    return getattr(settings, "UPLOAD_SCAN_MODE", "strict")


def quarantine(field_file):
    """Marks a stored file as not yet scanned. No-op outside quarantine mode.

    Called after the file has a storage path. Nothing reads the file here: the point is that the
    web process does not need a scanner at all, which is what makes this mode usable on a host
    where ClamAV cannot run next to the application.
    """
    from apps.core.models import ScannedUpload

    if not field_file or scan_mode() != "quarantine":
        return None
    record, _ = ScannedUpload.objects.get_or_create(path=field_file.name, defaults={"status": "pending"})
    return record


def upload_is_servable(name):
    """True when this stored file may be streamed to staff.

    A file with no record was scanned during its upload (strict mode) and is fine. A file with a
    record was taken in under quarantine and has to have been cleared since. Deciding per file
    rather than per current mode means switching modes later cannot release a file that was never
    looked at.
    """
    from apps.core.models import ScannedUpload

    if not name:
        return False
    record = ScannedUpload.objects.filter(path=name).first()
    return record is None or record.status == "clean"


IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


def validate_image_upload(uploaded):
    """Size and extension guard for staff-uploaded public images.

    Django's ImageField already proves the bytes are a real image via Pillow, so this adds the
    limits that matter for a public media library. These files are not virus-scanned: they are
    uploaded by signed-in staff and served as images, never executed.
    """
    max_bytes = getattr(settings, "IMAGE_UPLOAD_MAX_BYTES", 4 * 1024 * 1024)
    if uploaded.size and uploaded.size > max_bytes:
        raise ValidationError(f"This image is too large. The limit is {max_bytes // (1024 * 1024)} MB.")
    ext = Path(uploaded.name).suffix.lower().lstrip(".")
    if ext not in IMAGE_EXTENSIONS:
        raise ValidationError("Please upload a JPG, PNG or WebP image.")
    return ext


def noop_scan(uploaded):
    """Accepts every file. Only permitted when DEBUG=True (enforced in settings.py)."""
    return True


class ScannerUnavailable(ValidationError):
    pass


def _clamd_client():
    import clamd

    timeout = getattr(settings, "CLAMAV_TIMEOUT", 30)
    socket_path = getattr(settings, "CLAMAV_UNIX_SOCKET", "")
    if socket_path:
        return clamd.ClamdUnixSocket(path=socket_path, timeout=timeout)
    return clamd.ClamdNetworkSocket(
        host=getattr(settings, "CLAMAV_HOST", "127.0.0.1"),
        port=getattr(settings, "CLAMAV_PORT", 3310),
        timeout=timeout,
    )


def clamav_scan(uploaded):
    """Streams the upload to a ClamAV daemon (INSTREAM). Returns False on a positive match.

    Fails closed: if the daemon cannot be reached or returns an error, the upload is rejected
    rather than accepted unscanned.
    """
    import clamd

    uploaded.seek(0)
    try:
        result = _clamd_client().instream(uploaded)
    except (clamd.ClamdError, OSError) as exc:
        logger.error("ClamAV scan failed for %s: %s", getattr(uploaded, "name", "upload"), exc)
        raise ScannerUnavailable("We could not scan this file for viruses right now. Please try again in a few minutes.") from exc
    finally:
        uploaded.seek(0)

    status, signature = (result or {}).get("stream", ("ERROR", "no response"))
    if status == "OK":
        return True
    if status == "FOUND":
        logger.warning("ClamAV rejected upload %s: %s", getattr(uploaded, "name", "upload"), signature)
        return False
    logger.error("ClamAV returned %s for %s: %s", status, getattr(uploaded, "name", "upload"), signature)
    raise ScannerUnavailable("We could not scan this file for viruses right now. Please try again in a few minutes.")
