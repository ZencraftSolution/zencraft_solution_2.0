"""Fixtures for every test in the project."""

import pytest


@pytest.fixture(autouse=True)
def fresh_display_cache():
    """Empties the per-process display cache (apps/core/display_cache.py) before each test.

    It lives in this process's memory and survives the database rollback between tests, so without
    this a test would see the navigation, site settings or home content an earlier test cached.
    """
    from apps.core import display_cache

    display_cache.clear()
    yield
