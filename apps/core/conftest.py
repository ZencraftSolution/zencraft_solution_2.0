"""Shared fixtures for the browser tests.

These run against a real Django server in a real browser, so they catch what the test client
cannot: a JavaScript error, a button nothing is listening to, a layout that overflows, a focus
order that makes a form unusable with a keyboard.
"""

import base64
import os

import pytest
from django.core.cache import cache
from django.core.management import call_command

# Playwright's synchronous API runs an event loop in this thread, and Django then refuses ORM
# calls as "async unsafe". The queries here are ordinary synchronous ones in a test process, so
# the guard is describing a situation that does not apply. This is the documented way to use the
# sync API alongside Django's test tools.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

# Marks every test in this package's browser modules, so `-m "not e2e"` skips the slow ones.
pytestmark = pytest.mark.e2e

# A 1x1 transparent PNG, served in place of any image hosted elsewhere.
PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

STUBS = {
    "script": ("application/javascript", b"/* stubbed in tests */"),
    "stylesheet": ("text/css", b"/* stubbed in tests */"),
    "image": ("image/png", PIXEL),
    "font": ("font/woff2", b""),
}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """A desktop viewport, and no animations to wait out before a click."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": True,
        "reduced_motion": "reduce",
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # WebGL is not available in this environment, and the hero falls back without it.
    return {**browser_type_launch_args, "args": ["--disable-webgl", "--no-sandbox"]}


@pytest.fixture(autouse=True)
def patient(page):
    """Playwright's 30 second default is not enough on a slow machine.

    Closing a browser context alone takes about 25 seconds on the Windows laptop this was
    written on, and under that load navigations began timing out. The failures looked like
    layout faults and were not, which is worse than a slow test.
    """
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)


@pytest.fixture(autouse=True)
def offline(page, live_server):
    """Answers every request to another host with a harmless stub.

    Without this the tests wait on a CDN and a photo library, which makes them slow, makes them
    fail when the network does, and means a red build says nothing about this code. The site is
    built to work when GSAP does not load, so stubbing the scripts also exercises that path.
    """

    def handle(route, request):
        content_type, body = STUBS.get(request.resource_type, ("text/plain", b""))
        route.fulfill(status=200, content_type=content_type, body=body)

    # Matched by predicate so only external URLs cross into Python. Routing "**/*" sends every
    # local request through this callback too, which made each test's teardown take half a
    # minute while Playwright drained the queue.
    page.route(lambda url: not url.startswith(live_server.url), handle)
    yield


@pytest.fixture
def site(live_server, transactional_db):
    """The base URL of a running server with content in it.

    Seeded per test. live_server answers from another thread, so it only sees committed data,
    and pytest-django therefore gives these tests transactional behaviour and flushes between
    them. Seeding once at session scope was tried and does not survive that flush: every test
    after the first then looks at an empty site and fails in ways that look like browser faults.
    """
    call_command("seed_zencraft", verbosity=0)
    # The navigation menu is cached for two minutes. A list cached before the seed would make
    # every test that opens the services menu fail for a reason unrelated to the browser.
    cache.clear()
    return live_server.url


@pytest.fixture
def console_errors(page):
    """Collects browser errors so a test can assert the page did not break quietly."""
    errors = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors
