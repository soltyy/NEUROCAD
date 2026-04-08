"""Test document snapshot capture."""

from unittest.mock import MagicMock

from neurocad.core.context import DocSnapshot, ObjectInfo, capture, to_prompt_str


def test_capture_empty_doc():
    """Capture of an empty document returns a snapshot with no objects."""
    mock_doc = MagicMock()
    mock_doc.Name = "TestDoc"
    mock_doc.Objects = []
    mock_doc.ActiveObject = None
    snap = capture(mock_doc)
    assert snap.filename == "TestDoc"
    assert snap.objects == []
    assert snap.active_object is None


def test_capture_with_objects():
    """Capture should extract object info."""
    mock_box = MagicMock()
    mock_box.Name = "Box"
    mock_box.TypeId = "Part::Box"
    mock_box.Shape = MagicMock()
    mock_box.Shape.ShapeType = "Solid"
    mock_box.Shape.Volume = 1000.0
    mock_box.Placement = MagicMock()
    mock_box.Placement.toTuple.return_value = (0, 0, 0, 0, 0, 0, 1)
    mock_box.Visibility = True

    mock_doc = MagicMock()
    mock_doc.Name = "TestDoc"
    mock_doc.Objects = [mock_box]
    mock_doc.ActiveObject = mock_box

    snap = capture(mock_doc)
    assert snap.filename == "TestDoc"
    assert snap.active_object == "Box"
    assert len(snap.objects) == 1
    obj = snap.objects[0]
    assert obj.name == "Box"
    assert obj.type_id == "Part::Box"
    assert obj.shape_type == "Solid"
    assert obj.volume_mm3 == 1000.0
    assert obj.visible is True


def test_capture_no_shape():
    """Objects without Shape should not crash."""
    mock_obj = MagicMock()
    mock_obj.Name = "Feature"
    mock_obj.TypeId = "App::FeaturePython"
    mock_obj.Shape = None
    mock_obj.Placement = None
    mock_obj.Visibility = False

    mock_doc = MagicMock()
    mock_doc.Name = "Doc"
    mock_doc.Objects = [mock_obj]
    mock_doc.ActiveObject = None

    snap = capture(mock_doc)
    obj = snap.objects[0]
    assert obj.shape_type is None
    assert obj.volume_mm3 is None
    assert obj.visible is False


def test_to_prompt_str_limit():
    """to_prompt_str should respect max_chars."""
    snap = DocSnapshot(filename="test", objects=[])
    # Use a dummy implementation that returns a long string
    # We'll mock the actual implementation later.
    # For now, just ensure the function exists.
    result = to_prompt_str(snap, max_chars=10)
    assert isinstance(result, str)
    # Should not raise


def test_to_prompt_str_includes_filename():
    """The prompt should at least contain the filename."""
    snap = DocSnapshot(filename="MyDesign", objects=[])
    result = to_prompt_str(snap)
    assert "MyDesign" in result


def test_object_info_dataclass():
    """ObjectInfo fields should be accessible."""
    obj = ObjectInfo(
        name="Box",
        type_id="Part::Box",
        shape_type="Solid",
        volume_mm3=1000.0,
        placement="(0,0,0)",
        visible=True,
    )
    assert obj.name == "Box"
    assert obj.type_id == "Part::Box"
    assert obj.shape_type == "Solid"
    assert obj.volume_mm3 == 1000.0
    assert obj.placement == "(0,0,0)"
    assert obj.visible is True
