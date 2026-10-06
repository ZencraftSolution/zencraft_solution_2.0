"""Structured logging and a request id that ties a visitor's report to the lines in the log.

A person writes in with "the checkout broke at about two o'clock". Without an id to quote, that
is a search through every line in that hour; with one, it is a single grep. The id is taken from
the proxy's X-Request-ID when there is one, so a Render log line and an application log line for
the same request carry the same value.
"""

import json
import logging
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"

# Everything logging puts on a record by itself. Anything else was added by the caller and is
# worth keeping in the JSON output.
_STANDARD_ATTRS = frozenset(
    """args asctime created exc_info exc_text filename funcName levelname levelno lineno module
    msecs message msg name pathname process processName relativeCreated stack_info thread
    threadName taskName request_id""".split()
)


def get_request_id():
    return _request_id.get()


def set_request_id(value):
    return _request_id.set(value)


class RequestIDFilter(logging.Filter):
    """Puts the current request id on every record, including ones Django emits itself."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, which is what a log search backend wants to be given."""

    def format(self, record):
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload.setdefault(key, _safe(value))
        return json.dumps(payload, default=str)


def _safe(value):
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


class RequestIDMiddleware:
    """Gives every request an id, and sends it back so the visitor can quote it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(HEADER, "")
        # Trust an upstream id only when it looks like one, so it cannot be used to inject
        # arbitrary text into the logs.
        request_id = incoming if incoming.isalnum() and 8 <= len(incoming) <= 64 else uuid.uuid4().hex
        token = set_request_id(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response[RESPONSE_HEADER] = request_id
            return response
        finally:
            _request_id.reset(token)
