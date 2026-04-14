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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
