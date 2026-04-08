"""Test PySide compatibility shim."""



def test_compat_import():
    """neurocad.ui.compat should export QtCore, QtWidgets, Qt, Signal, Slot."""
    from neurocad.ui.compat import (
        PYSIDE_VERSION,
        Qt,
        QtCore,
        QtGui,
        QtWidgets,
        Signal,
        Slot,
    )
    assert QtCore is not None
    assert QtGui is not None
    assert QtWidgets is not None
    assert Qt is not None
    assert Signal is not None
    assert Slot is not None
    assert PYSIDE_VERSION in (2, 6)


def test_compat_qt_bindings():
    """Verify that imported Qt bindings are usable."""
    from neurocad.ui.compat import QtCore, QtWidgets
    # Create a trivial Qt object
    obj = QtCore.QObject()
    assert obj is not None
    # Check that a widget class exists
    assert hasattr(QtWidgets, "QPushButton")
