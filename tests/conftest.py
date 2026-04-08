"""Pytest fixtures for NeuroCad tests."""

import sys
from unittest.mock import MagicMock

import pytest

from neurocad.ui.compat import QtWidgets


# Mock FreeCAD and FreeCADGui before any import of neurocad modules
@pytest.fixture(scope="session", autouse=True)
def mock_freecad():
    """Provide mock FreeCAD and FreeCADGui modules."""
    mock_fc = MagicMock()
    mock_fc.ActiveDocument = None
    mock_fc.getDocument = MagicMock(return_value=MagicMock(Name="TestDoc"))
    mock_fc.listDocuments = MagicMock(return_value={})

    mock_fcgui = MagicMock()
    mock_fcgui.ActiveDocument = None

    sys.modules["FreeCAD"] = mock_fc
    sys.modules["FreeCADGui"] = mock_fcgui
    yield
    # Cleanup
    sys.modules.pop("FreeCAD", None)
    sys.modules.pop("FreeCADGui", None)


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for Qt tests."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app
    # Do not quit, reuse across tests


@pytest.fixture
def freecad_document(mock_freecad):
    """Return a mock FreeCAD document."""
    from unittest.mock import MagicMock
    doc = MagicMock()
    doc.Name = "TestDoc"
    doc.Objects = []
    return doc
