"""GUI-aligned active document resolution."""

from __future__ import annotations

from .debug import log_info, log_warn


def _doc_name_from_gui(gui_doc) -> str | None:
    """Extract document name from a FreeCADGui document wrapper."""
    if gui_doc is None:
        return None

    document = getattr(gui_doc, "Document", None)
    if document is not None:
        name: str | None = getattr(document, "Name", None)
        if name:
            return name

    name: str | None = getattr(gui_doc, "Name", None)  # type: ignore[no-redef]
    if name:
        return name

    return None


def get_active_document():
    """Return the active FreeCAD document aligned with the GUI state."""
    try:
        import FreeCAD  # type: ignore
        import FreeCADGui  # type: ignore
    except ImportError:
        log_warn("active_document", "FreeCAD modules are unavailable")
        return None

    try:
        gui_doc = getattr(FreeCADGui, "ActiveDocument", None)
        gui_name = _doc_name_from_gui(gui_doc)
        if gui_name:
            try:
                doc = FreeCAD.getDocument(gui_name)
                if doc is not None:
                    log_info(
                        "active_document",
                        "resolved via FreeCADGui.ActiveDocument",
                        name=gui_name,
                    )
                    return doc
            except Exception as exc:
                log_warn(
                    "active_document",
                    "FreeCAD.getDocument(gui_name) failed",
                    name=gui_name,
                    error=exc,
                )

            document = getattr(gui_doc, "Document", None)
            if document is not None:
                log_info("active_document", "resolved via gui_doc.Document fallback", name=gui_name)
                return document
    except Exception as exc:
        log_warn("active_document", "GUI-aligned resolution failed", error=exc)

    try:
        app_doc = getattr(FreeCAD, "ActiveDocument", None)
        if app_doc is not None:
            log_info(
                "active_document",
                "resolved via FreeCAD.ActiveDocument",
                name=getattr(app_doc, "Name", None),
            )
            return app_doc
    except Exception as exc:
        log_warn("active_document", "FreeCAD.ActiveDocument lookup failed", error=exc)

    try:
        docs = FreeCAD.listDocuments()
        if docs:
            first_doc = next(iter(docs.values()))
            log_info(
                "active_document",
                "resolved via FreeCAD.listDocuments fallback",
                name=getattr(first_doc, "Name", None),
            )
            return first_doc
    except Exception as exc:
        log_warn("active_document", "FreeCAD.listDocuments lookup failed", error=exc)

    log_warn("active_document", "no active document resolved")
    return None
