"""One way to send transactional email, so a failure is recorded rather than lost.

`send_mail(..., fail_silently=True)` does what it says: the exception disappears and nobody ever
finds out that the order confirmations stopped going out three weeks ago. These wrappers keep the
"never break the visitor's request" behaviour and add the part that was missing, which is saying
so in the log, with enough context to find the record afterwards.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_transactional_email(subject, body, to, *, reference="", html_body=None, reply_to=None):
    """Sends one message. Returns True when it went out, False when it did not.

    Never raises: a failing mail server must not turn a submitted application into an error page
    for the applicant. The record is already saved by the time this is called.
    """
    recipients = [address for address in ([to] if isinstance(to, str) else list(to)) if address]
    if not recipients:
        logger.warning("No recipient for %r (%s); nothing sent.", subject, reference or "no reference")
        return False

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[reply_to] if reply_to else None,
            connection=get_connection(fail_silently=False),
        )
        if html_body:
            # Plain text stays the message body, so it is what a text-only client shows.
            message.attach_alternative(html_body, "text/html")
        sent = message.send()
    except Exception:
        logger.error(
            "Failed to send %r to %s (%s)", subject, ", ".join(recipients), reference or "no reference", exc_info=True,
        )
        return False

    if not sent:
        logger.error("Mail backend accepted nothing for %r (%s)", subject, reference or "no reference")
        return False
    logger.info("Sent %r to %s (%s)", subject, ", ".join(recipients), reference or "no reference")
    return True


def send_templated_email(subject, template, context, to, *, reference="", reply_to=None):
    """Renders a plain-text template and sends it."""
    return send_transactional_email(
        subject, render_to_string(template, context), to, reference=reference, reply_to=reply_to
    )


def notify_internal(subject, body, *, reference=""):
    """Tells the team something happened. Same rules: logged if it fails, never raised."""
    return send_transactional_email(subject, body, settings.INTERNAL_NOTIFY_EMAIL, reference=reference)
