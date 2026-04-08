"""
NeuroCad - AI‑powered CAD assistant for FreeCAD.
"""

__version__ = "0.1.0"

# Bootstrap workbench registration when imported inside FreeCAD GUI
# This is a pragmatic fix for FreeCAD not executing InitGui.py automatically
# while still importing the neurocad package.
#
# The bootstrap only runs if FreeCADGui is available and the workbench hasn't
# been registered yet. It is safe to call multiple times and does nothing
# in a pure Python environment (e.g., tests, CLI).

import sys

# Flag to avoid repeated bootstrap attempts
_bootstrapped = False


def _try_bootstrap():
    """
    Attempt to register the CadCopilotWorkbench with FreeCADGui.
    Safe to call multiple times; does nothing if FreeCADGui is missing,
    the workbench is already registered, or an error occurs.
    """
    global _bootstrapped

    # Prevent repeated attempts in the same process
    if _bootstrapped:
        return

    # Try to import FreeCADGui – it may be missing in pure Python environments
    try:
        import FreeCADGui
    except ImportError:
        # FreeCADGui not available (e.g., tests, CLI, docs)
        # Silently skip bootstrap – this is expected
        _bootstrapped = True
        return

    # Check if the workbench is already registered
    # FreeCADGui.listWorkbenches() returns a dict {key: class_name}
    # The key is the class name "CadCopilotWorkbench"
    try:
        workbenches = FreeCADGui.listWorkbenches()
        if "CadCopilotWorkbench" in workbenches:
            # Already registered, nothing to do
            _bootstrapped = True
            return
    except Exception:
        # listWorkbenches may fail in some contexts; treat as not registered
        pass

    # Actually register the workbench
    try:
        from neurocad.workbench import register_workbench
        register_workbench()
        print("[NeuroCad] Workbench bootstrapped via __init__.py")
    except Exception as e:
        # Log but do not crash the import
        print(f"[NeuroCad] WARNING: Bootstrap failed: {e}", file=sys.stderr)
    finally:
        _bootstrapped = True


# Run bootstrap automatically when the module is imported
# This is safe because the function guards itself against repeated runs
# and does nothing if FreeCADGui is absent.
_try_bootstrap()
