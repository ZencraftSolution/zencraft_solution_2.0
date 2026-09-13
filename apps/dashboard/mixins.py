import functools

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404


def is_staff_user(user):
    return user.is_authenticated and user.is_active and user.is_staff


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Enforced on every dashboard view. Authenticated non-staff users get a 404, not a hint that the area exists."""

    def test_func(self):
        return is_staff_user(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise Http404
        return super().handle_no_permission()


def staff_required(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_staff_user(request.user):
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped
