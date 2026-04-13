"""Tests for executor.py."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.core.executor import (
    _BLOCKED_NAME_TOKENS,
    _build_namespace,
    _pre_check,
    execute,
)


def test_pre_check_blocks_forbidden_tokens():
    """_pre_check detects blocked tokens."""
    for token in _BLOCKED_NAME_TOKENS:
        code = f"x = {token}.something"
        error = _pre_check(code)
        assert error is not None
        assert token in error


def test_pre_check_allows_comments():
    """Comments containing blocked tokens should not trigger."""
    code = "# import os\nprint('hello')"
    assert _pre_check(code) is None


def test_pre_check_allows_strings():
    """Blocked tokens inside strings are ignored."""
    code = 'message = "import os"'
    assert _pre_check(code) is None


def test_pre_check_tokenizer_error():
    """Malformed code leads to tokenization error."""
    code = "'''unclosed string"
    error = _pre_check(code)
    assert "Tokenization error" in error


def test_build_namespace_includes_freecad_modules():
    """_build_namespace returns dict with FreeCAD, Part, etc."""
    mock_doc = MagicMock()
    namespace = _build_namespace(mock_doc)
    assert "FreeCAD" in namespace
    assert "Part" in namespace
    assert "PartDesign" in namespace
    assert "Sketcher" in namespace
    assert "Draft" in namespace
    assert "Mesh" in namespace
    assert namespace["doc"] is mock_doc
    assert namespace["App"] is namespace["FreeCAD"]


@patch("neurocad.core.executor._pre_check", return_value=None)
@patch("neurocad.core.executor._build_namespace")
@patch("neurocad.core.executor.exec")
def test_execute_success(mock_exec, mock_build, mock_pre_check):
    """execute returns ok=True and new object names."""
    mock_doc = MagicMock()
    mock_doc.Objects = []
    # Provide a realistic namespace with mocked FreeCAD modules
    mock_namespace = {
        "FreeCAD": MagicMock(),
        "Part": MagicMock(),
        "PartDesign": MagicMock(),
        "Sketcher": MagicMock(),
        "Draft": MagicMock(),
        "Mesh": MagicMock(),
        "doc": mock_doc,
        "App": MagicMock(),
    }
    mock_build.return_value = mock_namespace

    # Simulate creation of a new object
    class MockObject:
        Name = "Box"
    mock_new_obj = MockObject()
    def add_object(*args, **kwargs):
        mock_doc.Objects = [mock_new_obj]
    mock_exec.side_effect = add_object

    result = execute("Part.makeBox(10,10,10)", mock_doc)
    assert result.ok is True
    assert result.new_objects == ["Box"]
    assert result.error is None


@patch("neurocad.core.executor._pre_check")
def test_execute_pre_check_fails(mock_pre_check):
    """execute returns error when pre‑check fails."""
    mock_pre_check.return_value = "Blocked token 'import' found"
    result = execute("import os", MagicMock())
    assert result.ok is False
    assert "Blocked token" in result.error
    assert result.new_objects == []


def test_execute_syntax_error():
    """execute returns error on syntax error."""
    mock_doc = MagicMock()
    result = execute("invalid python syntax", mock_doc)
    assert result.ok is False
    assert "Syntax error" in result.error




@patch("neurocad.core.executor.load_config")
@patch("neurocad.core.executor._pre_check", return_value=None)
@patch("neurocad.core.executor._build_namespace")
@patch("neurocad.core.executor.exec")
def test_execute_too_many_objects(mock_exec, mock_build, mock_pre_check, mock_load_config):
    """execute rejects creation of more than configured max objects."""
    mock_doc = MagicMock()
    mock_doc.Objects = []
    mock_build.return_value = {}
    # Mock config with limit 5
    mock_load_config.return_value = {"max_created_objects": 5}

    # Simulate that execution adds 6 new objects
    new_objects = [MagicMock(Name=f"Obj{i}") for i in range(6)]
    def add_objects(*args, **kwargs):
        mock_doc.Objects = new_objects
    mock_exec.side_effect = add_objects

    result = execute("", mock_doc)
    assert result.ok is False
    assert "too many objects" in result.error.lower()
    assert "6" in result.error
    assert "5" in result.error


def test_executor_logs_unsupported_api():
    """execute logs a warning when unsupported FreeCAD API is attempted."""
    from unittest.mock import MagicMock, patch

    from neurocad.core.executor import execute
    mock_doc = MagicMock()
    mock_doc.Objects = []
    with patch(
        "neurocad.core.executor.exec",
        side_effect=AttributeError("module 'Part' has no attribute 'makeGear'"),
    ), patch("neurocad.core.executor.log_warn") as mock_log:
            result = execute("Part.makeGear()", mock_doc)
            assert result.ok is False
            assert mock_log.called
            # Ensure the log category matches
            mock_log.assert_called_with(
                "executor.unsupported_api",
                "unsupported FreeCAD API attempted",
                error="module 'part' has no attribute 'makegear'",
            )


def test_build_namespace_includes_math():
    """_build_namespace includes math module."""
    mock_doc = MagicMock()
    namespace = _build_namespace(mock_doc)
    assert "math" in namespace
    import math
    assert namespace["math"] is math


def test_import_math_blocked():
    """import math is blocked by tokenizer."""
    code = "import math"
    error = _pre_check(code)
    assert error is not None
    assert "Blocked token 'import'" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
