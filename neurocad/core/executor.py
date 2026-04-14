"""Safe execution of Python code in a sandboxed namespace."""

import io
import tokenize
from dataclasses import dataclass

from ..config.config import load as load_config
from .debug import log_warn

_BLOCKED_NAME_TOKENS = frozenset({
    # Intrinsics — can execute arbitrary code
    "__import__", "eval", "exec",
    # File / process / network access
    "open", "os", "sys", "subprocess",
    "socket", "urllib", "http", "requests",
    "shutil", "tempfile", "pathlib",
    # C-level access
    "ctypes", "cffi",
    # Serialisation that can execute code
    "pickle", "shelve",
    # Dynamic import — would bypass name-level blocking
    "importlib",
    # GUI — not available in headless execution context
    "FreeCADGui",
    # "import" and "from" are intentionally NOT blocked:
    # safe imports (math, Part, FreeCAD, Sketcher, etc.) work fine;
    # dangerous modules are caught by their own names above.
})

# Tokens that are dangerous only when used as a module import target, NOT as variable names.
# e.g.  import socket        → blocked (socket after import keyword)
#        socket = doc.add...  → allowed (socket as local variable name)
# Tokens NOT in this set but in _BLOCKED_NAME_TOKENS (eval, exec, open, etc.)
# are blocked unconditionally regardless of context.
_IMPORT_CONTEXT_ONLY = frozenset({
    "socket", "urllib", "http", "requests",
    "shutil", "tempfile", "pathlib",
    "ctypes", "cffi", "pickle", "shelve", "importlib",
    "os", "sys", "subprocess",
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
    Tokens in _IMPORT_CONTEXT_ONLY are only blocked when they appear immediately
    after an 'import' or 'from' keyword (module import context), not as variable names.
    """
    try:
        prev_meaningful: str | None = None
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in tokens:
            if tok.type not in (tokenize.COMMENT, tokenize.NEWLINE,
                                tokenize.NL, tokenize.INDENT, tokenize.DEDENT):
                if tok.type == tokenize.NAME and tok.string in _BLOCKED_NAME_TOKENS:
                    if tok.string in _IMPORT_CONTEXT_ONLY:
                        # Only block when used as a module name in import statement
                        if prev_meaningful in ("import", "from"):
                            return f"Blocked token '{tok.string}' found at line {tok.start[0]}"
                    else:
                        # Always block (eval, exec, open, __import__, FreeCADGui)
                        return f"Blocked token '{tok.string}' found at line {tok.start[0]}"
                prev_meaningful = tok.string if tok.type == tokenize.NAME else prev_meaningful
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
    import math  # type: ignore
    import random  # type: ignore

    # Load InvoluteGearFeature so its Python proxy class is registered.
    # Without this, doc.addObject("PartDesign::InvoluteGear", ...) produces a
    # bare C++ object that cannot compute its shape (state: Touched/Invalid).
    try:
        import InvoluteGearFeature  # type: ignore  # noqa: F401
    except (ImportError, Exception):
        pass

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
        "math": math,
        "random": random,
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
