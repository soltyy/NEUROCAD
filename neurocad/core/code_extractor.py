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


def extract_code(raw: str) -> str:
    """Return a single normalized Python block from an LLM response."""
    if not raw:
        return ""

    match = _FENCED_PYTHON_RE.search(raw)
    if match is None:
        match = _FENCED_ANY_RE.search(raw)

    code = match.group(1).strip() if match else raw.strip()
    return _strip_safe_imports(code)
