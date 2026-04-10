"""Tests for geometry exporter."""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Re‑import after patching in each test
import neurocad.core.exporter as exporter_module


def test_get_shapes():
    """_get_shapes extracts valid shapes, ignores null/invalid."""
    mock_shape_valid = MagicMock()
    mock_shape_valid.isNull.return_value = False
    mock_shape_valid.isValid.return_value = True
    mock_shape_null = MagicMock()
    mock_shape_null.isNull.return_value = True
    mock_shape_invalid = MagicMock()
    mock_shape_invalid.isNull.return_value = False
    mock_shape_invalid.isValid.return_value = False

    mock_obj_valid = MagicMock()
    mock_obj_valid.Shape = mock_shape_valid
    mock_obj_null = MagicMock()
    mock_obj_null.Shape = mock_shape_null
    mock_obj_invalid = MagicMock()
    mock_obj_invalid.Shape = mock_shape_invalid
    mock_obj_no_shape = MagicMock()
    del mock_obj_no_shape.Shape  # no Shape attribute

    # Patch Part module to be present
    with patch.dict(sys.modules, {"Part": MagicMock()}):
        importlib.reload(exporter_module)
        shapes = exporter_module._get_shapes([
            mock_obj_valid,
            mock_obj_null,
            mock_obj_invalid,
            mock_obj_no_shape,
        ])
        assert len(shapes) == 1
        assert shapes[0] is mock_shape_valid


def test_export_objects_step():
    """export_objects calls Part.exportStep for step format."""
    mock_shape = MagicMock()
    mock_shape.isNull.return_value = False
    mock_shape.isValid.return_value = True
    mock_obj = MagicMock()
    mock_obj.Shape = mock_shape

    mock_part = MagicMock()
    mock_part.Compound = MagicMock(return_value=mock_shape)
    mock_part.exportStep = MagicMock()

    with patch.dict(sys.modules, {"Part": mock_part, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        file_path = Path("/tmp/test.step")
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mode = 16877  # directory mode
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.stat", return_value=mock_stat),
        ):
            exporter_module.export_objects([mock_obj], file_path, "step")
            # Should call exportStep with string path and shape
            mock_part.exportStep.assert_called_once_with("/tmp/test.step", mock_shape)


def test_export_objects_stl():
    """export_objects calls Part.exportStl for stl format."""
    mock_shape = MagicMock()
    mock_shape.isNull.return_value = False
    mock_shape.isValid.return_value = True
    mock_obj = MagicMock()
    mock_obj.Shape = mock_shape

    mock_part = MagicMock()
    mock_part.Compound = MagicMock(return_value=mock_shape)
    mock_part.exportStl = MagicMock()

    with patch.dict(sys.modules, {"Part": mock_part, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        file_path = Path("/tmp/test.stl")
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mode = 16877  # directory mode
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.stat", return_value=mock_stat),
        ):
            exporter_module.export_objects([mock_obj], file_path, "stl")
            mock_part.exportStl.assert_called_once_with("/tmp/test.stl", mock_shape)


def test_export_objects_multiple_shapes_creates_compound():
    """Multiple shapes are combined into a Part.Compound."""
    mock_shape1 = MagicMock()
    mock_shape1.isNull.return_value = False
    mock_shape1.isValid.return_value = True
    mock_shape2 = MagicMock()
    mock_shape2.isNull.return_value = False
    mock_shape2.isValid.return_value = True
    mock_obj1 = MagicMock()
    mock_obj1.Shape = mock_shape1
    mock_obj2 = MagicMock()
    mock_obj2.Shape = mock_shape2

    mock_part = MagicMock()
    mock_part.Compound = MagicMock(return_value=mock_shape1)
    mock_part.exportStep = MagicMock()

    with patch.dict(sys.modules, {"Part": mock_part, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        file_path = Path("/tmp/test.step")
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mode = 16877  # directory mode
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.stat", return_value=mock_stat),
        ):
            exporter_module.export_objects([mock_obj1, mock_obj2], file_path, "step")
            # Compound should be called with a list of shapes
            mock_part.Compound.assert_called_once_with([mock_shape1, mock_shape2])
            # exportStep called with the compound shape
            mock_part.exportStep.assert_called_once_with(
                "/tmp/test.step", mock_part.Compound.return_value
            )


def test_export_objects_no_shapes_raises():
    """export_objects raises ExportError when no valid shapes."""
    mock_obj = MagicMock()
    mock_obj.Shape = None

    with patch.dict(sys.modules, {"Part": MagicMock(), "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        with pytest.raises(exporter_module.ExportError, match="No objects with valid geometry"):
            exporter_module.export_objects([mock_obj], Path("/tmp/test.step"), "step")


def test_export_objects_unsupported_format_raises():
    """export_objects raises ExportError for unsupported format."""
    mock_shape = MagicMock()
    mock_shape.isNull.return_value = False
    mock_shape.isValid.return_value = True
    mock_obj = MagicMock()
    mock_obj.Shape = mock_shape

    with patch.dict(sys.modules, {"Part": MagicMock(), "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        with pytest.raises(exporter_module.ExportError, match="Unsupported format"):
            exporter_module.export_objects([mock_obj], Path("/tmp/test.obj"), "obj")


def test_export_objects_part_unavailable_raises():
    """export_objects raises ExportError when Part module missing."""
    # Simulate Part = None (import failed)
    with patch.dict(sys.modules, {"Part": None, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        mock_obj = MagicMock()
        mock_obj.Shape = MagicMock()
        with pytest.raises(exporter_module.ExportError, match="FreeCAD Part module not available"):
            exporter_module.export_objects([mock_obj], Path("/tmp/test.step"), "step")


def test_export_objects_occ_error_wrapped():
    """OCCError is caught and re‑raised as ExportError."""
    mock_shape = MagicMock()
    mock_shape.isNull.return_value = False
    mock_shape.isValid.return_value = True
    mock_obj = MagicMock()
    mock_obj.Shape = mock_shape

    mock_part = MagicMock()
    mock_part.Compound = MagicMock(return_value=mock_shape)
    # Define OCCError as a proper exception class
    mock_part.OCCError = RuntimeError
    mock_part.exportStep = MagicMock(side_effect=RuntimeError("OCC error"))

    with patch.dict(sys.modules, {"Part": mock_part, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mode = 16877  # directory mode
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.stat", return_value=mock_stat),
            pytest.raises(
                exporter_module.ExportError,
                match="Geometry export failed",
            ),
        ):
            exporter_module.export_objects([mock_obj], Path("/tmp/test.step"), "step")


def test_export_selected_all_objects():
    """export_selected with selected_names=None exports all objects."""
    mock_doc = MagicMock()
    mock_obj1 = MagicMock()
    mock_obj2 = MagicMock()
    mock_doc.Objects = [mock_obj1, mock_obj2]

    with patch.dict(sys.modules, {"FreeCAD": MagicMock(), "Part": MagicMock()}):
        importlib.reload(exporter_module)
        with patch.object(exporter_module, "export_objects") as mock_export:
            file_path = Path("/tmp/test.step")
            exporter_module.export_selected(mock_doc, file_path, "step", selected_names=None)
            mock_export.assert_called_once_with([mock_obj1, mock_obj2], file_path, "step")


def test_export_selected_by_names():
    """export_selected filters objects by name."""
    mock_doc = MagicMock()
    mock_obj1 = MagicMock()
    mock_obj2 = MagicMock()
    mock_doc.getObject.side_effect = lambda name: {
        "Box": mock_obj1,
        "Cylinder": mock_obj2,
    }.get(name)

    with patch.dict(sys.modules, {"FreeCAD": MagicMock(), "Part": MagicMock()}):
        importlib.reload(exporter_module)
        with patch.object(exporter_module, "export_objects") as mock_export:
            file_path = Path("/tmp/test.step")
            exporter_module.export_selected(
                mock_doc, file_path, "step", selected_names=["Box", "Cylinder", "Missing"]
            )
            # Missing object is ignored
            mock_export.assert_called_once_with([mock_obj1, mock_obj2], file_path, "step")


def test_export_selected_freecad_unavailable_raises():
    """export_selected raises ExportError when FreeCAD missing."""
    with patch.dict(sys.modules, {"FreeCAD": None}):
        importlib.reload(exporter_module)
        with pytest.raises(exporter_module.ExportError, match="FreeCAD not available"):
            exporter_module.export_selected(MagicMock(), Path("/tmp/test.step"), "step")


def test_export_last_successful():
    """export_last_successful passes last_new_objects as selected_names."""
    mock_doc = MagicMock()
    with patch.dict(sys.modules, {"FreeCAD": MagicMock(), "Part": MagicMock()}):
        importlib.reload(exporter_module)
        with patch.object(exporter_module, "export_selected") as mock_export:
            file_path = Path("/tmp/test.step")
            exporter_module.export_last_successful(
                mock_doc, file_path, "step", ["Box", "Cylinder"]
            )
            mock_export.assert_called_once_with(
                mock_doc, file_path, "step", selected_names=["Box", "Cylinder"]
            )


def test_export_objects_verifies_file_exists_and_non_empty():
    """export_objects raises ExportError when file missing or empty, passes when valid."""
    mock_shape = MagicMock()
    mock_shape.isNull.return_value = False
    mock_shape.isValid.return_value = True
    mock_obj = MagicMock()
    mock_obj.Shape = mock_shape

    mock_part = MagicMock()
    mock_part.Compound = MagicMock(return_value=mock_shape)
    mock_part.exportStep = MagicMock()
    mock_part.exportStl = MagicMock()

    with patch.dict(sys.modules, {"Part": mock_part, "FreeCAD": MagicMock()}):
        importlib.reload(exporter_module)

        file_path = Path("/tmp/test.step")
        # Mock directory creation
        with patch("pathlib.Path.parent") as mock_parent:
            mock_mkdir = MagicMock()
            mock_parent.mkdir = mock_mkdir
            # Test success case: file exists and non-empty
            with patch("pathlib.Path.exists", return_value=True):
                mock_stat = MagicMock()
                mock_stat.st_size = 1024
                with patch("pathlib.Path.stat", return_value=mock_stat):
                    exporter_module.export_objects([mock_obj], file_path, "step")
                    mock_part.exportStep.assert_called_once_with("/tmp/test.step", mock_shape)
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # Test file missing
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(exporter_module.ExportError) as exc_info:
                    exporter_module.export_objects([mock_obj], file_path, "step")
                assert "was not created" in str(exc_info.value)
                # Ensure export was called (but verification fails)
                mock_part.exportStep.assert_called()
            # Test file empty
            with patch("pathlib.Path.exists", return_value=True):
                mock_stat_empty = MagicMock()
                mock_stat_empty.st_size = 0
                with patch("pathlib.Path.stat", return_value=mock_stat_empty):
                    with pytest.raises(exporter_module.ExportError) as exc_info:
                        exporter_module.export_objects([mock_obj], file_path, "step")
                    assert "is empty" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
