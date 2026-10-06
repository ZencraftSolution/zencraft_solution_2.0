"""TOTP two-factor authentication for staff.

Switched on with STAFF_2FA_REQUIRED. While it is off, staff can still enrol voluntarily from
the security page, which is the order to do it in: enrol everyone first, then turn the flag on,
or the people without a device lock themselves out.
"""

import base64
import io

import qrcode
import qrcode.image.svg
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_otp import devices_for_user
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core.throttle import throttle_login
from apps.core.utils import log_action

from .mixins import is_staff_user

DEVICE_NAME = "Authenticator app"


def _staff_only(request):
    """2FA pages sit in front of the staff gate, so they do their own, lighter check."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not is_staff_user(request.user):
        from django.http import Http404

        raise Http404
    return None


def confirmed_device(user):
    return next((d for d in devices_for_user(user, confirmed=True) if isinstance(d, TOTPDevice)), None)


def _pending_device(user):
    """The not-yet-confirmed device being enrolled, created on first visit to the setup page."""
    device = TOTPDevice.objects.filter(user=user, confirmed=False).order_by("-id").first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name=DEVICE_NAME, confirmed=False)
    return device


def qr_data_uri(device):
    """The enrolment QR code as an inline SVG data URI, so no image leaves the server."""
    image = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


class TokenForm(forms.Form):
    token = forms.CharField(
        label="Six-digit code",
        max_length=8,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True}),
    )

    def __init__(self, *args, device=None, **kwargs):
        self.device = device
        super().__init__(*args, **kwargs)

    def clean_token(self):
        token = self.cleaned_data["token"].strip().replace(" ", "")
        if not self.device or not self.device.verify_token(token):
            raise forms.ValidationError("That code is not right, or it has expired. Try the next one your app shows.")
        return token


def security(request):
    """Shows the current state and lets a staff member enrol or remove their authenticator."""
    stop = _staff_only(request)
    if stop is not None:
        return stop
    device = confirmed_device(request.user)
    context = {"device": device, "required": settings.STAFF_2FA_REQUIRED, "title": "Security"}
    if device is None:
        pending = _pending_device(request.user)
        form = TokenForm(request.POST or None, device=pending)
        if request.method == "POST" and form.is_valid():
            pending.name = DEVICE_NAME
            pending.confirmed = True
            pending.save()
            otp_login(request, pending)
            log_action(request, "enabled two-factor authentication", request.user)
            messages.success(request, "Two-factor authentication is on. Keep your recovery options safe.")
            return redirect("dashboard:security")
        context.update({"form": form, "secret_uri": qr_data_uri(pending), "secret_key": pending.bin_key.hex()})
    return render(request, "dashboard/security.html", context)


@require_POST
def disable_two_factor(request):
    stop = _staff_only(request)
    if stop is not None:
        return stop
    if settings.STAFF_2FA_REQUIRED:
        messages.error(request, "Two-factor authentication is required for staff accounts and cannot be turned off.")
        return redirect("dashboard:security")
    TOTPDevice.objects.filter(user=request.user).delete()
    log_action(request, "disabled two-factor authentication", request.user)
    messages.success(request, "Two-factor authentication is off.")
    return redirect("dashboard:security")


@throttle_login()
def two_factor(request):
    """The code prompt shown between signing in and reaching the dashboard."""
    stop = _staff_only(request)
    if stop is not None:
        return stop
    device = confirmed_device(request.user)
    if device is None:
        # Required but never enrolled: send them to set it up rather than to a dead end.
        return redirect("dashboard:security")
    form = TokenForm(request.POST or None, device=device)
    if request.method == "POST" and form.is_valid():
        otp_login(request, device)
        log_action(request, "passed two-factor check", request.user)
        return redirect("dashboard:overview")
    return render(request, "dashboard/two_factor.html", {"form": form, "title": "Two-step verification"})
