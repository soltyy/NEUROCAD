"""Safe execution of Python code in a sandboxed namespace."""

import io
import tokenize
from dataclasses import dataclass

from ..config.config import load as load_config
from .debug import log_warn

_BLOCKED_NAME_TOKENS = frozenset({
    "import", "from", "FreeCADGui", "__import__",
    "os", "sys", "subprocess", "open", "eval", "exec",
})


@dataclass
class ExecResult:
    """Result of executing code."""
    ok: bool
    new_objects: list[str]  # names of newly created objects
    error: str | None = None
    rollback_count: int = 0  # number of transaction rollbacks for this execution


def _pre_check(code: str) -> str | None:
    """Check for forbidden tokens using tokenize.

    Returns error message if blocked token found, otherwise None.
    """
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in tokens:
            if tok.type == tokenize.NAME and tok.string in _BLOCKED_NAME_TOKENS:
                return f"Blocked token '{tok.string}' found at line {tok.start[0]}"
    except tokenize.TokenError as e:
        return f"Tokenization error: {e}"
    return None


def _build_namespace(doc):
    """Build a safe namespace for code execution."""
    # Import FreeCAD modules inside the function to avoid early import errors
    import Draft  # type: ignore
    import FreeCAD  # type: ignore
    import Mesh  # type: ignore
    import Part  # type: ignore
    import PartDesign  # type: ignore
    import Sketcher  # type: ignore

    # Provide the active document as a convenience variable
    namespace = {
        "FreeCAD": FreeCAD,
        "Part": Part,
        "PartDesign": PartDesign,
        "Sketcher": Sketcher,
        "Draft": Draft,
        "Mesh": Mesh,
        "doc": doc,
        "App": FreeCAD,  # alias
    }
    return namespace


def execute(code: str, doc) -> ExecResult:
    """Execute Python code in a sandboxed namespace on the calling thread."""
    # Pre‑check for forbidden tokens
    error = _pre_check(code)
    if error:
        return ExecResult(ok=False, new_objects=[], error=error, rollback_count=0)

    # Build namespace
    namespace = _build_namespace(doc)

    # Compile code
    try:
        compiled = compile(code, "<neurocad>", "exec")
    except SyntaxError as e:
        return ExecResult(ok=False, new_objects=[], error=f"Syntax error: {e}", rollback_count=0)

    # Keep track of objects before execution
    before = set(doc.Objects) if hasattr(doc, "Objects") else set()

    try:
        exec(compiled, namespace)  # noqa: S102  # controlled namespace, main-thread execution
    except Exception as e:
        msg = str(e).lower()
        if "module 'part' has no attribute" in msg or "has no attribute 'make" in msg:
            log_warn("executor.unsupported_api", "unsupported FreeCAD API attempted", error=msg)
        return ExecResult(ok=False, new_objects=[], error=str(e), rollback_count=0)

    # Determine newly created objects
    after = set(doc.Objects) if hasattr(doc, "Objects") else set()
    new_objects = list(after - before)

    # Limit the number of new objects
    config = load_config()
    max_objects = config.get("max_created_objects", 1000)
    if len(new_objects) > max_objects:
        return ExecResult(
            ok=False,
            new_objects=[],
            error=f"Created too many objects ({len(new_objects)} > {max_objects})",
            rollback_count=0
        )

    return ExecResult(ok=True, new_objects=[obj.Name for obj in new_objects], rollback_count=0)
