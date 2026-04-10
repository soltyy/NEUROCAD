"""Export geometry to STEP/STL."""

from pathlib import Path
from typing import Literal

# FreeCAD API imports (optional for testing)
try:
    import FreeCAD  # type: ignore
    import Part  # type: ignore
    OCC_ERROR = Part.OCCError
except ImportError:
    # Mock for tests
    Part = None
    FreeCAD = None
    OCC_ERROR = RuntimeError

SUPPORTED_FORMATS = ("step", "stl")
ExportFormat = Literal["step", "stl"]


class ExportError(Exception):
    """Raised when export fails."""


def _get_shapes(objects: list["FreeCAD.DocumentObject"]) -> list["Part.Shape"]:
    """Extract valid shapes from objects."""
    shapes = []
    for obj in objects:
        if hasattr(obj, "Shape") and obj.Shape is not None:
            shape = obj.Shape
            if not shape.isNull() and shape.isValid():
                shapes.append(shape)
    return shapes


def export_objects(
    objects: list["FreeCAD.DocumentObject"],
    file_path: Path,
    fmt: ExportFormat,
) -> None:
    """Export selected objects to STEP or STL.

    Args:
        objects: List of FreeCAD DocumentObjects.
        file_path: Destination file path.
        fmt: "step" or "stl".

    Raises:
        ExportError: If no valid shapes, unsupported format, or export fails.
    """
    if Part is None:
        raise ExportError("FreeCAD Part module not available.")
    if fmt not in SUPPORTED_FORMATS:
        raise ExportError(f"Unsupported format: {fmt}. Supported: {SUPPORTED_FORMATS}")

    shapes = _get_shapes(objects)
    if not shapes:
        raise ExportError("No objects with valid geometry to export.")

    # Create a compound if multiple shapes
    shape = shapes[0] if len(shapes) == 1 else Part.Compound(shapes)

    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "step":
            Part.exportStep(str(file_path), shape)
        else:  # stl
            Part.exportStl(str(file_path), shape)
    except OCC_ERROR as e:
        raise ExportError(f"Geometry export failed: {e}") from e
    except Exception as e:
        raise ExportError(f"Unexpected error during export: {e}") from e

    # Verify export succeeded: file must exist and be non-empty
    if not file_path.exists():
        raise ExportError(f"Export failed: file '{file_path}' was not created.")
    if file_path.stat().st_size == 0:
        raise ExportError(f"Export failed: file '{file_path}' is empty.")

def export_selected(
    doc: "FreeCAD.Document",
    file_path: Path,
    fmt: ExportFormat,
    selected_names: list[str] | None = None,
) -> None:
    """Export selected objects (or all objects) from a document.

    If selected_names is None, exports all objects with valid geometry.

    Args:
        doc: FreeCAD document.
        file_path: Destination file path.
        fmt: "step" or "stl".
        selected_names: Optional list of object names to export.

    Raises:
        ExportError: If export fails.
    """
    if FreeCAD is None:
        raise ExportError("FreeCAD not available.")

    if selected_names is None:
        objects = doc.Objects
    else:
        objects = [
            doc.getObject(name)
            for name in selected_names
            if doc.getObject(name) is not None
        ]

    export_objects(objects, file_path, fmt)


def export_last_successful(
    doc: "FreeCAD.Document",
    file_path: Path,
    fmt: ExportFormat,
    last_new_objects: list[str],
) -> None:
    """Export objects created in the last successful NeuroCad run.

    Convenience wrapper around export_selected.

    Args:
        doc: FreeCAD document.
        file_path: Destination file path.
        fmt: "step" or "stl".
        last_new_objects: List of object names created by the last successful execution.
    """
    export_selected(doc, file_path, fmt, selected_names=last_new_objects)
