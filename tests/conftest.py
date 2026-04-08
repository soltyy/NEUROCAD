"""
Pytest configuration and fixtures for NeuroCad tests.

Provides a session‑scoped QApplication fixture.
"""

from typing import Generator

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Generator[QApplication, None, None]:
    """
    Session‑scoped QApplication fixture.

    Creates a single QApplication instance for the entire test session.
    The instance is reused across all tests that require a Qt event loop.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
    yield app
