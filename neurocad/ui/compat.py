"""PySide2/PySide6 compatibility shim.

All UI files must import from this module, never directly from PySide6/PySide2.
"""

import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    from PySide6.QtCore import Qt, Signal, Slot  # type: ignore
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
        from PySide2.QtCore import Qt, Signal, Slot  # type: ignore
        PYSIDE_VERSION = 2
    except ImportError as e:
        raise ImportError(
            "Neither PySide6 nor PySide2 could be imported. "
            "Make sure FreeCAD is installed and its Python environment is available."
        ) from e

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Qt",
    "Signal",
    "Slot",
    "PYSIDE_VERSION",
]

# Re‑export commonly used submodules for convenience
QtCore = QtCore
QtGui = QtGui
QtWidgets = QtWidgets
Qt = Qt
Signal = Signal
Slot = Slot

if __name__ == "__main__":
    print(f"PySide{PYSIDE_VERSION} detected")
    print(f"QtCore: {QtCore.__version__}")  # type: ignore[attr-defined]
