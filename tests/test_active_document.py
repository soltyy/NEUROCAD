"""Test GUI-aligned active document resolution."""

import importlib
from unittest.mock import MagicMock, patch

import pytest


def test_no_freecad():
    """Without FreeCAD, returns None."""
    with patch.dict("sys.modules", {"FreeCAD": None, "FreeCADGui": None}):
        import neurocad.core.active_document

        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        assert result is None


def test_with_gui_active_document():
    """Should return FreeCAD.getDocument(gui_doc.Document.Name)."""
    mock_gui_doc = MagicMock()
    mock_gui_doc.Document.Name = "TestDoc"
    mock_fc_doc = MagicMock()

    with (
        patch("FreeCADGui.ActiveDocument", mock_gui_doc),
        patch("FreeCAD.getDocument", return_value=mock_fc_doc) as mock_get,
    ):
        import neurocad.core.active_document

        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        mock_get.assert_called_once_with("TestDoc")
        assert result is mock_fc_doc


def test_fallback_to_freecad_active():
    """If FreeCADGui.ActiveDocument is None, fall back to FreeCAD.ActiveDocument."""
    with patch("FreeCADGui.ActiveDocument", None):
        mock_fc_doc = MagicMock()
        with patch("FreeCAD.ActiveDocument", mock_fc_doc):
            import neurocad.core.active_document

            importlib.reload(neurocad.core.active_document)
            result = neurocad.core.active_document.get_active_document()
            assert result is mock_fc_doc


def test_fallback_to_none():
    """If both are missing, return None."""
    with patch("FreeCADGui.ActiveDocument", None), patch("FreeCAD.ActiveDocument", None), patch(
        "FreeCAD.listDocuments", return_value={}
    ):
        import neurocad.core.active_document

        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        assert result is None


def test_gui_document_fallback_when_getdocument_fails():
    """If FreeCAD.getDocument() fails, return gui_doc.Document directly."""
    mock_gui_doc = MagicMock()
    mock_fc_doc = MagicMock()
    mock_fc_doc.Name = "TestDoc"
    mock_gui_doc.Document = mock_fc_doc

    with (
        patch("FreeCADGui.ActiveDocument", mock_gui_doc),
        patch("FreeCAD.getDocument", side_effect=RuntimeError("boom")),
    ):
        import neurocad.core.active_document

        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        assert result is mock_fc_doc


def test_list_documents_fallback():
    """If both GUI and ActiveDocument are unavailable, use listDocuments()."""
    mock_fc_doc = MagicMock()
    mock_fc_doc.Name = "FallbackDoc"
    with (
        patch("FreeCADGui.ActiveDocument", None),
        patch("FreeCAD.ActiveDocument", None),
        patch("FreeCAD.listDocuments", return_value={"FallbackDoc": mock_fc_doc}),
    ):
        import neurocad.core.active_document

        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        assert result is mock_fc_doc




@pytest.mark.xfail(reason="Mock side_effect not raising on attribute access")
def test_exception_safety():
    """Exceptions during resolution should not crash."""
    from unittest.mock import PropertyMock
    with (
        patch("FreeCADGui.ActiveDocument", new_callable=PropertyMock, side_effect=RuntimeError),
        patch("FreeCAD.ActiveDocument", new_callable=PropertyMock, side_effect=RuntimeError),
    ):
        import importlib

        import neurocad.core.active_document
        importlib.reload(neurocad.core.active_document)
        result = neurocad.core.active_document.get_active_document()
        assert result is None
