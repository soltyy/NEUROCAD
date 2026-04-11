"""Extract and normalize Python code from LLM responses."""

from __future__ import annotations

import re

_FENCED_PYTHON_RE = re.compile(r"```python\s*(.*?)(?<=\n)```", re.IGNORECASE | re.DOTALL)
_FENCED_ANY_RE = re.compile(r"```\s*(.*?)(?<=\n)```", re.DOTALL)
_SAFE_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(FreeCAD|Part|PartDesign|Sketcher|Draft|Mesh)\s+import\s+.+|"
    r"import\s+(FreeCAD|Part|PartDesign|Sketcher|Draft|Mesh)(?:\s+as\s+\w+)?)\s*$"
)


def _strip_safe_imports(code: str) -> str:
    """Remove redundant imports for names already present in the sandbox."""
    lines = []
    for line in code.splitlines():
        if _SAFE_IMPORT_RE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def extract_code_blocks(raw: str) -> list[str]:
    """Return a list of normalized Python blocks from an LLM response."""
    if not raw:
        return []
    # Find all fenced python blocks
    py_blocks = _FENCED_PYTHON_RE.findall(raw)
    if py_blocks:
        return [_strip_safe_imports(b.strip()) for b in py_blocks if b.strip()]
    # Fallback to any fenced blocks
    any_blocks = _FENCED_ANY_RE.findall(raw)
    if any_blocks:
        return [_strip_safe_imports(b.strip()) for b in any_blocks if b.strip()]
    # No fences, treat entire raw as one block
    stripped = raw.strip()
    return [_strip_safe_imports(stripped)] if stripped else []


def extract_code(raw: str) -> str:
    """Return a single normalized Python block from an LLM response."""
    blocks = extract_code_blocks(raw)
    if not blocks:
        return ""
    # For backward compatibility, return the first block.
    # (Historically, extract_code returned the first fenced block or the whole raw.)
    return blocks[0]
