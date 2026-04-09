"""Test code extraction from LLM responses."""

from neurocad.core.code_extractor import extract_code


def test_extract_fenced_python():
    """Fenced Python block should be stripped."""
    raw = """```python
print("hello")
```"""
    result = extract_code(raw)
    assert "print" in result
    assert "```" not in result
    assert result.strip() == 'print("hello")'


def test_extract_fenced_without_lang():
    """Fenced block without language should also be stripped."""
    raw = """```
print("hello")
```"""
    result = extract_code(raw)
    assert "print" in result
    assert "```" not in result


def test_extract_unfenced():
    """Unfenced text should be returned as‑is (trimmed)."""
    raw = "Just plain text"
    result = extract_code(raw)
    assert result == "Just plain text"


def test_extract_empty():
    """Empty raw string returns empty string."""
    raw = ""
    result = extract_code(raw)
    assert result == ""


def test_extract_multiple_blocks():
    """Only the first fenced block should be used."""
    raw = """```python
a = 1
```
```
b = 2
```"""
    result = extract_code(raw)
    assert result == "a = 1"
    assert result.count("```") == 0


def test_extract_backticks_inside():
    """Backticks inside the code should be preserved."""
    raw = """```python
print("```")
```"""
    result = extract_code(raw)
    assert 'print("```")' in result


def test_extract_strips_redundant_safe_imports():
    """Sandbox-provided imports should be removed from extracted code."""
    raw = """```python
import FreeCAD
import Part
box = Part.makeBox(10, 10, 10)
Part.show(box)
```"""
    result = extract_code(raw)
    assert "import FreeCAD" not in result
    assert "import Part" not in result
    assert "Part.makeBox" in result


def test_extract_keeps_other_imports_for_executor_to_block():
    """Unsafe imports should remain so executor can reject them explicitly."""
    raw = """```python
import FreeCADGui
print("x")
```"""
    result = extract_code(raw)
    assert "import FreeCADGui" in result
