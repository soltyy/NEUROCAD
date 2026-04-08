"""
Unit tests for NeuroCad workbench registration and lifecycle.
"""
from unittest.mock import Mock, patch

# Import the module after patching
from neurocad.workbench import CadCopilotWorkbench, register_workbench


def test_register_workbench_success():
    """
    register_workbench should call FreeCADGui.addWorkbench when FreeCADGui is available.
    """
    mock_freecad_gui = Mock()
    mock_freecad_gui.addWorkbench = Mock()
    with patch('neurocad.workbench.FreeCADGui', mock_freecad_gui):
        from neurocad.workbench import register_workbench
        register_workbench()
        mock_freecad_gui.addWorkbench.assert_called_once_with(CadCopilotWorkbench)


def test_register_workbench_no_freecadgui():
    """
    register_workbench should do nothing and not raise when FreeCADGui is None.
    """
    # Ensure FreeCADGui is None (as in non‑FreeCAD environments)
    with patch("neurocad.workbench.FreeCADGui", None):
        # The function should simply skip registration
        # No exception should be raised
        register_workbench()


def test_register_workbench_exception_handled():
    """
    register_workbench should catch exceptions from addWorkbench and log them.
    """
    mock_freecad_gui = Mock()
    mock_freecad_gui.addWorkbench = Mock(side_effect=RuntimeError("test error"))
    with patch('neurocad.workbench.FreeCADGui', mock_freecad_gui), \
         patch('neurocad.workbench.logging.error') as mock_error:
        from neurocad.workbench import register_workbench
        register_workbench()
        mock_freecad_gui.addWorkbench.assert_called_once_with(CadCopilotWorkbench)
        # Should have logged an error message
        assert mock_error.called
        assert "Failed to register workbench" in mock_error.call_args[0][0]


def test_workbench_initialize_with_freecadgui(qapp):
    """
    CadCopilotWorkbench.Initialize should create and dock a panel when
    FreeCADGui exists.
    """
    from PySide6.QtWidgets import QWidget
    main_window = QWidget()
    main_window.addDockWidget = Mock()
    mock_freecad_gui = Mock()
    mock_freecad_gui.getMainWindow = Mock(return_value=main_window)
    mock_qt_core = Mock()
    mock_qt_core.Qt = Mock()
    mock_qt_core.Qt.RightDockWidgetArea = 2  # default value from workbench

    with patch("neurocad.workbench.FreeCADGui", mock_freecad_gui), \
         patch("neurocad.workbench.QtCore", mock_qt_core):
        workbench = CadCopilotWorkbench()
        workbench.Initialize()

        # Verify getMainWindow was called
        mock_freecad_gui.getMainWindow.assert_called_once()
        # Verify panel was created and docked
        assert workbench.panel is not None
        main_window.addDockWidget.assert_called_once_with(2, workbench.panel)
        # Panel should be hidden initially
        assert workbench.panel.isHidden()


def test_workbench_initialize_without_freecadgui():
    """
    Initialize should do nothing when FreeCADGui is None (e.g., console mode).
    """
    with patch("neurocad.workbench.FreeCADGui", None):
        workbench = CadCopilotWorkbench()
        # Should not raise
        workbench.Initialize()
        assert workbench.panel is None


def test_workbench_activated_deactivated(qapp):
    """
    Activated should show the panel, Deactivated should hide it.
    """
    mock_panel = Mock()
    mock_panel.show = Mock()
    mock_panel.hide = Mock()
    mock_panel.isHidden = Mock(return_value=True)

    workbench = CadCopilotWorkbench()
    workbench.panel = mock_panel

    workbench.Activated()
    mock_panel.show.assert_called_once()

    workbench.Deactivated()
    mock_panel.hide.assert_called_once()


def test_workbench_activated_deactivated_no_panel():
    """
    Activated/Deactivated should tolerate missing panel (e.g., if Initialize
    wasn't called).
    """
    workbench = CadCopilotWorkbench()
    workbench.panel = None
    # Should not raise
    workbench.Activated()
    workbench.Deactivated()


def test_workbench_context_menu():
    """ContextMenu is a stub; verify it doesn't crash."""
    workbench = CadCopilotWorkbench()
    # Should return None (or nothing)
    assert workbench.ContextMenu("some_recipient") is None


def test_workbench_get_class_name():
    """GetClassName must return the FreeCAD‑expected string."""
    workbench = CadCopilotWorkbench()
    assert workbench.GetClassName() == "Gui::PythonWorkbench"
