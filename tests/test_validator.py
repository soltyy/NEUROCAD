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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
