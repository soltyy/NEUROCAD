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
    mock_box.Placement.Base = MagicMock(x=0.0, y=0.0, z=0.0)
    mock_box.Placement.Rotation = MagicMock()
    mock_box.Placement.Rotation.toEuler.return_value = (0.0, 0.0, 0.0)
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
    assert obj.placement == "pos=(0.0,0.0,0.0) rot=(0.0,0.0,0.0)"
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


def test_to_prompt_str_omits_whole_lines_when_truncated():
    """Truncation should happen on line boundaries with an omission marker."""
    snap = DocSnapshot(
        filename="Doc",
        active_object="Obj0",
        objects=[
            ObjectInfo(name=f"Obj{i}", type_id="Part::Feature", placement="pos=(0.0,0.0,0.0)")
            for i in range(10)
        ],
    )

    result = to_prompt_str(snap, max_chars=160)

    assert "more line(s) omitted" in result
    assert not result.endswith("placement=po...")


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


def test_capture_extracts_geometric_properties():
    """capture should extract Length, Width, Height etc. into properties dict."""
    mock_box = MagicMock()
    mock_box.Name = "Box"
    mock_box.TypeId = "Part::Box"
    mock_box.Shape = MagicMock()
    mock_box.Shape.ShapeType = "Solid"
    mock_box.Shape.Volume = 1000.0
    mock_box.Placement = MagicMock()
    mock_box.Placement.Base = MagicMock(x=0.0, y=0.0, z=0.0)
    mock_box.Placement.Rotation = MagicMock()
    mock_box.Placement.Rotation.toEuler.return_value = (0.0, 0.0, 0.0)
    mock_box.Visibility = True
    # Add geometric attributes
    mock_box.Length = 50.0
    mock_box.Width = 30.0
    mock_box.Height = 20.0
    mock_box.Radius = 5.0  # not typical for box but will be captured
    mock_box.Angle = 45.0

    mock_doc = MagicMock()
    mock_doc.Name = "TestDoc"
    mock_doc.Objects = [mock_box]
    mock_doc.ActiveObject = mock_box

    snap = capture(mock_doc)
    obj = snap.objects[0]
    assert obj.properties == {
        "Length": 50.0,
        "Width": 30.0,
        "Height": 20.0,
        "Radius": 5.0,
        "Angle": 45.0,
    }
    # Ensure rounding to two decimal places
    mock_box.Length = 12.345
    mock_box.Width = 67.891
    snap2 = capture(mock_doc)
    obj2 = snap2.objects[0]
    assert obj2.properties["Length"] == 12.35
    assert obj2.properties["Width"] == 67.89


def test_to_prompt_str_includes_properties():
    """to_prompt_str should include props= listing."""
    obj = ObjectInfo(
        name="Box",
        type_id="Part::Box",
        shape_type="Solid",
        volume_mm3=1000.0,
        placement="pos=(0.0,0.0,0.0)",
        visible=True,
        properties={"Length": 50.0, "Width": 30.0, "Height": 20.0},
    )
    snap = DocSnapshot(filename="Doc", active_object="Box", objects=[obj])
    result = to_prompt_str(snap)
    # Should contain props=Length=50.00 Width=30.00 Height=20.00 (or .2f)
    assert "props=" in result
    assert "Length=50.00" in result
    assert "Width=30.00" in result
    assert "Height=20.00" in result
    # Order sorted
    # If no properties, props= should not appear
    obj2 = ObjectInfo(name="Sphere", type_id="Part::Sphere", properties={})
    snap2 = DocSnapshot(filename="Doc", objects=[obj2])
    result2 = to_prompt_str(snap2)
    assert "props=" not in result2
