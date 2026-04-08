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
    """Multiple fenced blocks should be concatenated."""
    raw = """```python
a = 1
```
```
b = 2
```"""
    result = extract_code(raw)
    assert "a = 1" in result
    assert "b = 2" in result
    assert result.count("```") == 0


def test_extract_backticks_inside():
    """Backticks inside the code should be preserved."""
    raw = """```python
print("```")
```"""
    result = extract_code(raw)
    assert 'print("```")' in result
