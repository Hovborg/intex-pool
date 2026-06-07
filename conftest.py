"""Pytest config: make the repo importable and enable custom integrations."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the intex_pool custom integration in all tests."""
    yield
