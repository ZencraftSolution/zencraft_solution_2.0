"""Private file storage and upload validation shared by careers and the estimator."""
import io
import logging
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
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


private_storage = PrivateStorage()


def get_private_storage():
    return private_storage


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
    scan = import_string(settings.UPLOAD_SCAN_HOOK)
    if not scan(uploaded):
        raise ValidationError("The file could not be accepted by our security scan.")
    return detected


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
