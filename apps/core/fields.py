"""Model fields with the behaviour this project wants, rather than the historical default."""

from django.db import models


class URLField(models.URLField):
    """A URL field that reads "example.com" as https, not http.

    Django 5 still assumes http for a scheme-less URL and warns about it; Django 6 switches to
    https. Setting it here rather than on the transitional setting means the behaviour does not
    change under us on upgrade, and the field keeps working when the setting is removed.
    """

    def formfield(self, **kwargs):
        return super().formfield(**{"assume_scheme": "https", **kwargs})
