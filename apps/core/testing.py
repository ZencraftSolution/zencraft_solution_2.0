"""Small factories and fixtures shared by the per-app test modules. Not imported by application code."""
import io
import zipfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

NOOP_SCAN = "apps.core.uploads.noop_scan"
CLAMAV_SCAN = "apps.core.uploads.clamav_scan"
PASSWORD = "a-strong-passphrase-2026"
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_bytes(valid=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        if valid:
            zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def pdf_upload(name="cv.pdf", content=PDF_BYTES):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def docx_upload(name="cv.docx", valid=True):
    return SimpleUploadedFile(name, docx_bytes(valid), content_type=DOCX_MIME)


def make_user(username="visitor", **extra):
    return get_user_model().objects.create_user(username, f"{username}@example.com", PASSWORD, **extra)


def make_staff(username="hq-staff", **extra):
    extra.setdefault("is_staff", True)
    return make_user(username, **extra)


def make_department(slug="engineering", name="Engineering"):
    from apps.careers.models import Department

    return Department.objects.get_or_create(slug=slug, defaults={"name": name})[0]


def make_job(slug="backend-developer", **kwargs):
    from apps.careers.models import JobOpening

    defaults = dict(
        title="Backend Developer", department=make_department(), work_mode="hybrid", employment_type="full-time",
        experience_level="mid", summary="Build APIs.", description="Description.", responsibilities="Build\nReview",
        requirements="Python\nDjango", nice_to_haves="Docker", is_active=True,
    )
    defaults.update(kwargs)
    return JobOpening.objects.create(slug=slug, **defaults)


def make_application(job=None, **kwargs):
    from apps.careers.models import JobApplication

    defaults = dict(
        reference=f"ZA-{JobApplication.objects.count() + 1:06d}", full_name="Sita Sharma", email="sita@example.com",
        phone="9800000000", current_location="Butwal", years_experience=Decimal("2"), notice_period="1-month",
    )
    defaults.update(kwargs)
    return JobApplication.objects.create(job=job or make_job(), **defaults)


def make_product(slug="discovery-workshop", **kwargs):
    from apps.commerce.models import ProductizedService

    defaults = dict(
        name="Discovery Workshop", category="consultation", summary="Plan it.", description="Two days.",
        price_npr=Decimal("60000"), billing="one_time", deliverables=["Backlog"], is_active=True,
    )
    defaults.update(kwargs)
    return ProductizedService.objects.create(slug=slug, **defaults)


def make_estimator_catalog():
    """Two project types with a known feature set, independent of the seed data."""
    from apps.estimator.models import FeatureOption, ProjectType

    web = ProjectType.objects.create(key="web-app", label="Web application", description="Portal", base_hours=100, order=1)
    mobile = ProjectType.objects.create(key="mobile-app", label="Mobile app", description="App", base_hours=200, order=2)
    ProjectType.objects.create(key="retired", label="Retired", description="Old", base_hours=50, is_active=False, order=3)
    auth = FeatureOption.objects.create(key="auth", label="Login", hours=20, order=1)
    payments = FeatureOption.objects.create(key="payments", label="Payments", hours=30, order=2)
    offline = FeatureOption.objects.create(key="offline", label="Offline mode", hours=50, order=3)
    hidden = FeatureOption.objects.create(key="hidden", label="Hidden", hours=999, order=4, is_active=False)
    auth.project_types.set([web, mobile])
    payments.project_types.set([web, mobile])
    offline.project_types.set([mobile])
    hidden.project_types.set([web])
    return web, mobile


def release_file_response(response):
    """Close a FileResponse's file handle without firing request_finished (which would close the test DB connection)."""
    for closer in list(getattr(response, "_resource_closers", [])):
        closer()


def image_bytes(size=(40, 40), fmt="PNG", color=(31, 79, 216)):
    """The bytes of a genuine image, for a browser test that has to write one to disk."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def image_upload(name="photo.png", size=(40, 40), fmt="PNG", color=(31, 79, 216)):
    """A genuine image file, so ImageField's Pillow validation passes."""
    content_type = "image/png" if fmt == "PNG" else f"image/{fmt.lower()}"
    return SimpleUploadedFile(name, image_bytes(size, fmt, color), content_type=content_type)


def page_params(pages):
    """pytest.param for each (name, path) of a browser test, opening the shop for its own pages.

    The shop is closed by default, so /pricing/ and everything under it answers 404 unless a test
    is marked `store` (see the shop fixture in apps/core/conftest.py).
    """
    import pytest

    return [
        pytest.param(name, path, id=name, marks=[pytest.mark.store] if path.startswith("/pricing/") else [])
        for name, path in pages.items()
    ]
