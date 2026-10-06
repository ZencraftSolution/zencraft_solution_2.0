import functools

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone

SESSION_STARTED_KEY = "staff_session_started"


def is_staff_user(user):
    return user.is_authenticated and user.is_active and user.is_staff


def session_expired(request):
    """True once a staff session is older than STAFF_SESSION_HOURS, counted from sign-in.

    An absolute limit rather than an idle one: a dashboard left open on a shared machine stays
    usable all day under an idle timeout, which is the case this is meant to cover.
    """
    started = request.session.get(SESSION_STARTED_KEY)
    if not started:
        return False
    age_hours = (timezone.now().timestamp() - started) / 3600
    return age_hours >= settings.STAFF_SESSION_HOURS


def needs_second_factor(request):
    """True when 2FA is required and this session has not passed it."""
    if not settings.STAFF_2FA_REQUIRED:
        return False
    verified = getattr(request.user, "is_verified", None)
    return not (verified and verified())


def staff_gate(request):
    """Returns a response when the staff request must be stopped, or None to let it through."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not is_staff_user(request.user):
        raise Http404  # never confirm that the area exists
    if session_expired(request):
        from django.contrib.auth import logout

        logout(request)
        return redirect_to_login(request.get_full_path())
    if needs_second_factor(request):
        return redirect("dashboard:two_factor")
    return None


def staff_required(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        stop = staff_gate(request)
        if stop is not None:
            return stop
        return view(request, *args, **kwargs)

    return wrapped
