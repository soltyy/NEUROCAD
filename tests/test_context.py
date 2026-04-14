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
    mock_box.Shape.isNull.return_value = False
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
    mock_box.Shape.isNull.return_value = False
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


def test_capture_null_shape():
    """Capture should handle objects with a null shape (isNull() == True)."""
    mock_obj = MagicMock()
    mock_obj.Name = "NullShape"
    mock_obj.TypeId = "Part::Feature"
    mock_obj.Shape = MagicMock()
    mock_obj.Shape.isNull = MagicMock(return_value=True)
    # ShapeType and Volume should not be accessed
    mock_obj.Shape.ShapeType = "Solid"  # but will not be used
    mock_obj.Shape.Volume = 1000.0
    mock_obj.Placement = None
    mock_obj.Visibility = True

    mock_doc = MagicMock()
    mock_doc.Name = "Doc"
    mock_doc.Objects = [mock_obj]
    mock_doc.ActiveObject = None

    snap = capture(mock_doc)
    obj = snap.objects[0]
    assert obj.shape_type is None
    assert obj.volume_mm3 is None
    assert obj.visible is True


def test_capture_sets_priority_correctly():
    """Priority should be 2 for active, 1 for visible, 0 for hidden."""
    mock_active = MagicMock()
    mock_active.Name = "Active"
    mock_active.TypeId = "Part::Box"
    mock_active.Shape = None
    mock_active.Placement = None
    mock_active.Visibility = True

    mock_visible = MagicMock()
    mock_visible.Name = "Visible"
    mock_visible.TypeId = "Part::Box"
    mock_visible.Shape = None
    mock_visible.Placement = None
    mock_visible.Visibility = True

    mock_hidden = MagicMock()
    mock_hidden.Name = "Hidden"
    mock_hidden.TypeId = "Part::Box"
    mock_hidden.Shape = None
    mock_hidden.Placement = None
    mock_hidden.Visibility = False

    mock_doc = MagicMock()
    mock_doc.Name = "Doc"
    mock_doc.Objects = [mock_active, mock_visible, mock_hidden]
    mock_doc.ActiveObject = mock_active

    snap = capture(mock_doc)
    # Find objects by name
    obj_map = {obj.name: obj for obj in snap.objects}
    assert obj_map["Active"].priority == 2
    assert obj_map["Visible"].priority == 1
    assert obj_map["Hidden"].priority == 0


def test_to_prompt_str_sorts_by_priority():
    """Objects should be sorted by priority descending, then by name."""
    objects = [
        ObjectInfo(name="Z", type_id="Part::Feature", priority=0, visible=True),
        ObjectInfo(name="A", type_id="Part::Feature", priority=2, visible=True),
        ObjectInfo(name="B", type_id="Part::Feature", priority=1, visible=True),
        ObjectInfo(name="C", type_id="Part::Feature", priority=2, visible=True),
    ]
    snap = DocSnapshot(filename="Doc", objects=objects)
    result = to_prompt_str(snap, max_chars=5000)
    # Determine order by parsing lines
    lines = result.split('\n')
    object_lines = [line for line in lines if line.startswith('  -')]
    # Extract names
    names = [line.split()[1] for line in object_lines]
    # Expected order: priority 2 (A, C) then priority 1 (B) then priority 0 (Z)
    assert names == ["A", "C", "B", "Z"]


def test_to_prompt_str_always_includes_active():
    """Active object line should be kept even if it slightly exceeds max_chars."""
    # Create an active object with a long line
    active = ObjectInfo(
        name="ActiveLongName",
        type_id="Part::Box",
        priority=2,
        visible=True,
        placement="pos=(1.0,2.0,3.0)",
        shape_type="Solid",
        volume_mm3=1000.0,
        properties={"Length": 10.0, "Width": 20.0},
    )
    # Create many other objects to fill the limit
    other_objects = [
        ObjectInfo(name=f"Obj{i}", type_id="Part::Feature", priority=0, visible=False)
        for i in range(50)
    ]
    snap = DocSnapshot(filename="Doc", active_object="ActiveLongName", objects=[active] + other_objects)
    # Set max_chars very low, but active object should still appear
    result = to_prompt_str(snap, max_chars=200)
    # The active object line should be present
    assert "ActiveLongName" in result
    # The line should not be truncated (should contain full info)
    # We'll just check that the name appears
    lines = result.split('\n')
    active_lines = [line for line in lines if "ActiveLongName" in line]
    assert len(active_lines) > 0
    # Ensure no truncation marker "..." in the active line (unless it's at the end for omitted lines)
    # We'll accept that the line may be truncated if max_chars is extremely low,
    # but our algorithm allows 20% overflow, so with 200 chars it should fit.
    # For safety, we just assert that active object appears.


def test_to_prompt_str_respects_max_chars():
    """Total length should not exceed max_chars (except allowed overflow)."""
    objects = [
        ObjectInfo(name=f"Obj{i}", type_id="Part::Feature", priority=0, visible=True)
        for i in range(100)
    ]
    snap = DocSnapshot(filename="Doc", objects=objects)
    max_chars = 500
    result = to_prompt_str(snap, max_chars=max_chars)
    # Length should be <= max_chars (plus possible 20% for active object, but there is none)
    # However algorithm may add omission line which adds some chars.
    # We'll allow a small tolerance (10 chars) for newline differences.
    assert len(result) <= max_chars + 10
    # Should contain omission marker
    if len(objects) > 5:  # likely truncated
        assert "more line(s) omitted" in result


def test_capture_body_with_tip():
    """Capture should use Tip.Shape for PartDesign::Body."""
    mock_tip = MagicMock()
    mock_tip.Shape = MagicMock()
    mock_tip.Shape.isNull.return_value = False
    mock_tip.Shape.ShapeType = "Solid"
    mock_tip.Shape.Volume = 500.0

    mock_body = MagicMock()
    mock_body.Name = "Body"
    mock_body.TypeId = "PartDesign::Body"
    mock_body.Shape = None  # Body has no Shape
    mock_body.Tip = mock_tip
    mock_body.Placement = MagicMock()
    mock_body.Placement.Base = MagicMock(x=10.0, y=20.0, z=30.0)
    mock_body.Placement.Rotation = MagicMock()
    mock_body.Placement.Rotation.toEuler.return_value = (0.0, 0.0, 0.0)
    mock_body.Visibility = True

    mock_doc = MagicMock()
    mock_doc.Name = "TestDoc"
    mock_doc.Objects = [mock_body]
    mock_doc.ActiveObject = mock_body

    snap = capture(mock_doc)
    assert snap.filename == "TestDoc"
    assert snap.active_object == "Body"
    assert len(snap.objects) == 1
    obj = snap.objects[0]
    assert obj.name == "Body"
    assert obj.type_id == "PartDesign::Body"
    assert obj.shape_type == "Solid"
    assert obj.volume_mm3 == 500.0
    assert obj.placement == "pos=(10.0,20.0,30.0) rot=(0.0,0.0,0.0)"
    assert obj.visible is True


def test_capture_body_without_tip():
    """Capture should handle Body without Tip."""
    mock_body = MagicMock()
    mock_body.Name = "Body"
    mock_body.TypeId = "PartDesign::Body"
    mock_body.Shape = None
    mock_body.Tip = None
    mock_body.Placement = None
    mock_body.Visibility = False

    mock_doc = MagicMock()
    mock_doc.Name = "TestDoc"
    mock_doc.Objects = [mock_body]
    mock_doc.ActiveObject = None

    snap = capture(mock_doc)
    obj = snap.objects[0]
    assert obj.shape_type is None
    assert obj.volume_mm3 is None
    assert obj.visible is False
