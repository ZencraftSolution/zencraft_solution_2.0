"""Optional Sentry reporting, off unless SENTRY_DSN is set.

The site handles CVs, contact messages and orders, so the default is to send Sentry as little
about people as possible: no request bodies, no cookies, no session, and headers and query
strings scrubbed of anything that identifies someone. An error report is worth having; a copy
of an applicant's phone number in a third-party dashboard is not.
"""

import logging

logger = logging.getLogger(__name__)

# Lower-cased header and field names that must never leave the server in a report.
SENSITIVE_KEYS = frozenset(
    """authorization cookie set-cookie x-csrftoken csrfmiddlewaretoken sessionid password
    password1 password2 old_password new_password token access_token refresh_token secret
    api_key apikey email phone full_name name cv signature pidx transaction_uuid""".split()
)
REDACTED = "[redacted]"


def _scrub_mapping(mapping):
    if not isinstance(mapping, dict):
        return mapping
    return {key: (REDACTED if key.lower() in SENSITIVE_KEYS else value) for key, value in mapping.items()}


def scrub(event, hint=None):
    """Sentry before_send hook: drop the parts of a request that describe a person."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)  # the posted form: a CV, a message, an address
        request.pop("cookies", None)
        request["headers"] = _scrub_mapping(request.get("headers"))
        if isinstance(request.get("query_string"), dict):
            request["query_string"] = _scrub_mapping(request["query_string"])
    event.pop("user", None)  # username, email and IP that the Django integration collects
    if isinstance(event.get("extra"), dict):
        event["extra"] = _scrub_mapping(event["extra"])
    return event


def init_sentry(dsn, environment, release="", traces_sample_rate=0.0):
    """Starts Sentry when a DSN is configured. A missing package is a warning, not a crash."""
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; error reporting is off.")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        traces_sample_rate=traces_sample_rate,
        before_send=scrub,
    )
    return True
