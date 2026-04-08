"""GUI‑aligned active document resolution."""

try:
    import FreeCAD  # type: ignore
    import FreeCADGui  # type: ignore
    HAS_FREECAD = True
except ImportError:
    HAS_FREECAD = False


def get_active_document():
    """Return the active FreeCAD document, aligned with the GUI selection.

    Returns:
        FreeCAD.Document or None: The active document, or None if no document is open.
    """
    if not HAS_FREECAD:
        return None
    try:
        # Prefer the GUI‑active document (what the user sees)
        gui_doc = FreeCADGui.ActiveDocument
        if gui_doc is not None:
            return FreeCAD.getDocument(gui_doc.Document.Name)
    except Exception:
        pass
    try:
        return FreeCAD.ActiveDocument
    except Exception:
        return None
