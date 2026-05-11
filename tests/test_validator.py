"""Tests for validator.py."""

from unittest.mock import MagicMock

import pytest

from neurocad.core.validator import validate


def test_validate_state_error_list():
    """validate returns error when obj.State contains 'error'."""
    obj = MagicMock()
    obj.State = ["Error", "Something"]
    result = validate(obj)
    assert result.ok is False
    assert "error" in result.error.lower()


def test_validate_state_error_string():
    """validate returns error when obj.State is a string with 'invalid'."""
    obj = MagicMock()
    obj.State = "Invalid shape"
    result = validate(obj)
    assert result.ok is False
    assert "invalid" in result.error.lower()


def test_validate_state_ok():
    """validate returns ok when State is clean."""
    obj = MagicMock()
    obj.State = ["Normal"]
    del obj.Shape  # ensure no shape to validate
    result = validate(obj)
    assert result.ok is True


def test_validate_no_shape():
    """validate returns ok if object has no Shape attribute."""
    obj = MagicMock()
    del obj.Shape
    result = validate(obj)
    assert result.ok is True


def test_validate_null_shape():
    """validate returns error when Shape.isNull() is True."""
    obj = MagicMock()
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = True
    result = validate(obj)
    assert result.ok is False
    assert "null" in result.error.lower()


def test_validate_invalid_shape():
    """validate returns error when Shape.isValid() is False."""
    obj = MagicMock()
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = False
    result = validate(obj)
    assert result.ok is False
    assert "invalid" in result.error.lower()


def test_validate_valid_shape():
    """validate returns ok for a valid shape."""
    obj = MagicMock()
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    result = validate(obj)
    assert result.ok is True
    assert result.error is None


def test_validate_body_with_tip_shape_valid():
    """validate uses Tip.Shape for PartDesign::Body."""
    obj = MagicMock()
    obj.State = None
    obj.TypeId = "PartDesign::Body"
    del obj.Shape  # Body has no Shape
    obj.Tip = MagicMock()
    obj.Tip.Shape = MagicMock()
    obj.Tip.Shape.isNull.return_value = False
    obj.Tip.Shape.isValid.return_value = True
    result = validate(obj)
    assert result.ok is True


def test_validate_body_with_tip_shape_null():
    """validate returns error when Tip.Shape is null for PartDesign::Body."""
    obj = MagicMock()
    obj.State = None
    obj.TypeId = "PartDesign::Body"
    del obj.Shape
    obj.Tip = MagicMock()
    obj.Tip.Shape = MagicMock()
    obj.Tip.Shape.isNull.return_value = True
    result = validate(obj)
    assert result.ok is False
    assert "null" in result.error.lower()


def test_validate_body_with_tip_shape_invalid():
    """validate returns error when Tip.Shape is invalid for PartDesign::Body."""
    obj = MagicMock()
    obj.State = None
    obj.TypeId = "PartDesign::Body"
    del obj.Shape
    obj.Tip = MagicMock()
    obj.Tip.Shape = MagicMock()
    obj.Tip.Shape.isNull.return_value = False
    obj.Tip.Shape.isValid.return_value = False
    result = validate(obj)
    assert result.ok is False
    assert "invalid" in result.error.lower()


def test_validate_body_without_shape_or_tip():
    """validate returns ok for PartDesign::Body without Shape and Tip."""
    obj = MagicMock()
    obj.State = None
    obj.TypeId = "PartDesign::Body"
    del obj.Shape
    obj.Tip = None  # explicit None, not missing
    result = validate(obj)
    assert result.ok is True


def test_validate_body_with_tip_no_shape():
    """validate returns ok when PartDesign::Body Tip exists but has no Shape."""
    obj = MagicMock()
    obj.State = None
    obj.TypeId = "PartDesign::Body"
    del obj.Shape
    obj.Tip = MagicMock()
    del obj.Tip.Shape  # Tip has no Shape attribute
    result = validate(obj)
    assert result.ok is True


def test_validate_body_with_shape_and_tip():
    """validate prefers Shape over Tip.Shape."""
    obj = MagicMock()
    obj.State = None
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    obj.Tip = MagicMock()
    obj.Tip.Shape = MagicMock()
    obj.Tip.Shape.isNull.return_value = True  # would cause error if used
    result = validate(obj)
    assert result.ok is True  # because Shape is valid


# --- Sprint 5.23: wheel anti-pattern checks ---------------------------------

def _make_wheel_mock(name, xy_len_mm, z_len_mm, volume_mm3):
    """Build a MagicMock obj+Shape with the given bbox + volume."""
    import math
    obj = MagicMock()
    obj.Name = name
    obj.Label = name
    obj.State = None
    obj.TypeId = "Part::Feature"
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    obj.Shape.Volume = float(volume_mm3)
    bb = MagicMock()
    bb.XLength = xy_len_mm
    bb.YLength = xy_len_mm
    bb.ZLength = z_len_mm
    obj.Shape.BoundBox = bb
    return obj


def test_validate_wheel_anti_pattern_solid_disc_caught():
    """A 'Wheel' named solid with density ≥ 0.5 vs equivalent disc fails."""
    import math
    # Bicycle wheel 700 mm diameter, 25 mm thick, full solid:
    xy = 700.0
    z = 25.0
    v_solid = math.pi * (xy / 2) ** 2 * z
    obj = _make_wheel_mock("Wheel", xy, z, v_solid * 1.02)  # density 1.02
    result = validate(obj)
    assert result.ok is False
    assert "anti-pattern" in result.error.lower()
    assert "density" in result.error.lower()
    assert "Part::Cut" in result.error


def test_validate_wheel_hollow_passes():
    """A 'Wheel' named solid with density < 0.5 (properly hollow) passes."""
    import math
    xy = 700.0
    z = 25.0
    v_solid = math.pi * (xy / 2) ** 2 * z
    obj = _make_wheel_mock("Wheel", xy, z, v_solid * 0.15)  # 15 % density
    result = validate(obj)
    assert result.ok is True


def test_validate_non_wheel_name_skips_anti_pattern():
    """A solid disc named 'Disc' (no wheel tokens) is not flagged."""
    import math
    obj = _make_wheel_mock("Disc", 700.0, 25.0, math.pi * 350 * 350 * 25)
    result = validate(obj)
    assert result.ok is True  # solid disc is fine if not a wheel


def test_validate_wheel_russian_name_caught():
    """Cyrillic 'колесо' name also triggers anti-pattern check."""
    import math
    xy, z = 600.0, 30.0
    v_solid = math.pi * (xy / 2) ** 2 * z
    obj = _make_wheel_mock("колесо", xy, z, v_solid * 0.80)
    result = validate(obj)
    assert result.ok is False
    assert "anti-pattern" in result.error.lower()


def test_validate_wheel_tall_solid_skipped():
    """A tall solid (z_len > xy/2) is not a wheel disc — anti-pattern skipped."""
    obj = _make_wheel_mock("Wheel", 100.0, 200.0, 100000.0)  # tall cylinder
    result = validate(obj)
    assert result.ok is True


# --- Sprint 5.23 L8: axle anti-pattern (plain cylinder vs stepped) ---------

def _make_axle_mock(name, xy_len_mm, z_len_mm, volume_mm3):
    """Build an axle-like obj with bbox + volume."""
    obj = MagicMock()
    obj.Name = name
    obj.Label = name
    obj.State = None
    obj.TypeId = "Part::Feature"
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    obj.Shape.Volume = float(volume_mm3)
    bb = MagicMock()
    bb.XLength = xy_len_mm
    bb.YLength = xy_len_mm
    bb.ZLength = z_len_mm
    obj.Shape.BoundBox = bb
    return obj


def test_validate_axle_plain_cylinder_caught():
    """A plain cylinder named 'Axle' is flagged."""
    import math
    xy = 165.0
    z = 2294.0
    v_plain = math.pi * (xy / 2) ** 2 * z
    obj = _make_axle_mock("Axle", xy, z, v_plain * 0.99)  # almost full cylinder
    result = validate(obj)
    assert result.ok is False
    assert "axle anti-pattern" in result.error.lower()
    assert "stepped" in result.error.lower()


def test_validate_axle_stepped_passes():
    """A stepped axle (volume ≈ 0.74 × plain cylinder) passes."""
    import math
    xy = 194.0  # max hub diameter
    z = 2294.0
    v_plain = math.pi * (xy / 2) ** 2 * z
    obj = _make_axle_mock("AxleRU1Sh", xy, z, v_plain * 0.74)
    result = validate(obj)
    assert result.ok is True


def test_validate_axle_short_skips():
    """Short solids aren't axles even if named 'Axle' — anti-pattern skipped."""
    import math
    obj = _make_axle_mock("Axle", 100.0, 200.0, math.pi * 50 ** 2 * 200)
    result = validate(obj)
    assert result.ok is True


def test_validate_axle_russian_name_caught():
    """Cyrillic 'ось ' name also triggers the anti-pattern check."""
    import math
    xy, z = 165.0, 2294.0
    v_plain = math.pi * (xy / 2) ** 2 * z
    obj = _make_axle_mock("ось колёсной пары", xy, z, v_plain * 0.99)
    result = validate(obj)
    assert result.ok is False
    assert "axle anti-pattern" in result.error.lower()


# --- Sprint 5.23 L9: gear anti-pattern (no center axle hole) ---------------

def _make_gear_mock(name, xy_len_mm, z_len_mm, *, center_is_inside: bool):
    """Build a gear-like obj. center_is_inside=True simulates a solid disc
    (no axle hole); False simulates a gear with hole at centre."""
    obj = MagicMock()
    obj.Name = name
    obj.Label = name
    obj.State = None
    obj.TypeId = "Part::Feature"
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    obj.Shape.Volume = 1000.0
    bb = MagicMock()
    bb.XLength = xy_len_mm
    bb.YLength = xy_len_mm
    bb.ZLength = z_len_mm
    bb.XMin = -xy_len_mm / 2
    bb.XMax = xy_len_mm / 2
    bb.YMin = -xy_len_mm / 2
    bb.YMax = xy_len_mm / 2
    bb.ZMin = 0
    bb.ZMax = z_len_mm
    obj.Shape.BoundBox = bb
    obj.Shape.isInside = MagicMock(return_value=center_is_inside)
    return obj


def test_validate_gear_solid_disc_caught():
    """Gear without axle hole (centre points all inside) fails."""
    obj = _make_gear_mock("Gear", 60.0, 20.0, center_is_inside=True)
    result = validate(obj)
    assert result.ok is False
    assert "gear anti-pattern" in result.error.lower()
    assert "axle hole" in result.error.lower()


def test_validate_gear_with_hole_passes():
    """Gear with central hole (centre points outside the solid) passes."""
    obj = _make_gear_mock("Gear", 60.0, 20.0, center_is_inside=False)
    result = validate(obj)
    assert result.ok is True


def test_validate_gear_russian_name_caught():
    """Cyrillic 'шестерёнка' name also triggers the anti-pattern."""
    obj = _make_gear_mock("шестерёнка", 60.0, 20.0, center_is_inside=True)
    result = validate(obj)
    assert result.ok is False
    assert "gear anti-pattern" in result.error.lower()


def test_validate_gear_tall_solid_skipped():
    """A tall solid (z_len > xy×0.8) is not a gear disc — anti-pattern skipped."""
    obj = _make_gear_mock("Gear", 30.0, 30.0, center_is_inside=True)
    result = validate(obj)
    assert result.ok is True  # tall — not a gear disc, skip check


def test_validate_intermediate_gear_skipped():
    """An intermediate object (consumed by Cut/Fuse — InList non-empty) is
    NOT checked against anti-pattern. The user's production failure on
    2026-05-11 was triggered by validator hitting `GearFused` (input to
    Cut(GearFused, GearBore)) — but that intermediate is correctly without
    a hole; only the final `Gear` (Cut result) should have one."""
    obj = _make_gear_mock("GearFused", 60.0, 20.0, center_is_inside=True)
    # Simulate this object is consumed by another (e.g. the Cut).
    consumer = MagicMock()
    consumer.Name = "Gear"
    obj.InList = [consumer]
    result = validate(obj)
    assert result.ok is True


def test_validate_final_gear_still_checked_with_inlist_empty():
    """The FINAL gear (no consumers — InList empty) IS checked."""
    obj = _make_gear_mock("Gear", 60.0, 20.0, center_is_inside=True)
    obj.InList = []
    result = validate(obj)
    assert result.ok is False
    assert "gear anti-pattern" in result.error.lower()


def test_validate_intermediate_wheel_skipped():
    """Same intermediate-skip rule for wheels: RimOuter / RimInner are
    inputs to Cut and should not trigger the wheel anti-pattern."""
    import math
    xy, z = 700.0, 25.0
    v_solid = math.pi * (xy / 2) ** 2 * z
    obj = _make_wheel_mock("RimOuter", xy, z, v_solid)  # full solid disc
    obj.InList = [MagicMock(Name="Rim")]
    result = validate(obj)
    assert result.ok is True


# --- Sprint 5.23 L10b: house anti-pattern (too tall = stacked storeys) ----

def _make_house_mock(name, z_len_mm):
    """Build a house-like obj with a given Z extent."""
    obj = MagicMock()
    obj.Name = name
    obj.Label = name
    obj.State = None
    obj.TypeId = "Part::Compound"
    obj.InList = []
    obj.Shape = MagicMock()
    obj.Shape.isNull.return_value = False
    obj.Shape.isValid.return_value = True
    obj.Shape.Volume = 1.0e6
    bb = MagicMock()
    bb.XLength = 10000.0
    bb.YLength = 8000.0
    bb.ZLength = z_len_mm
    bb.XMin = -5000; bb.XMax = 5000
    bb.YMin = -4000; bb.YMax = 4000
    bb.ZMin = 0; bb.ZMax = z_len_mm
    obj.Shape.BoundBox = bb
    return obj


def test_validate_house_too_tall_caught():
    """A 'House' object 15 m tall is flagged."""
    obj = _make_house_mock("House", 15000.0)
    result = validate(obj)
    assert result.ok is False
    assert "house anti-pattern" in result.error.lower()
    assert "9000" in result.error or "9 m" in result.error.lower()


def test_validate_house_realistic_passes():
    """A 'House' object 6.5 m tall passes."""
    obj = _make_house_mock("House", 6500.0)
    result = validate(obj)
    assert result.ok is True


def test_validate_house_russian_name_caught():
    """Cyrillic 'дом' name also triggers the anti-pattern."""
    obj = _make_house_mock("дом_2этажа", 12000.0)
    result = validate(obj)
    assert result.ok is False
    assert "house anti-pattern" in result.error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
