"""Regression tests for panel.py and InitGui.py UI semantics."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.ui.panel import CopilotPanel, get_panel_dock
from neurocad.ui.settings import SettingsDialog


def test_get_panel_dock_without_main_window():
    """get_panel_dock() returns None when FreeCAD main window is unavailable."""
    import sys
    mock_fcgui = sys.modules["FreeCADGui"]
    with patch.object(mock_fcgui, "getMainWindow", return_value=None):
        # Ensure singleton is reset
        import neurocad.ui.panel
        neurocad.ui.panel._panel_dock = None
        result = get_panel_dock()
        assert result is None
        # Subsequent call with create=False also returns None
        assert get_panel_dock(create=False) is None


def test_get_panel_dock_with_main_window(qapp):
    """get_panel_dock() creates a dock when main window exists."""
    import sys

    from neurocad.ui.compat import QtWidgets
    # Create a real QMainWindow
    real_mw = QtWidgets.QMainWindow()
    # Mock addDockWidget to track calls
    with patch.object(real_mw, "addDockWidget") as mock_add:
        mock_fcgui = sys.modules["FreeCADGui"]
        with patch.object(mock_fcgui, "getMainWindow", return_value=real_mw):
            import neurocad.ui.panel
            neurocad.ui.panel._panel_dock = None
            dock = get_panel_dock()
            assert dock is not None
            assert isinstance(dock, CopilotPanel)
            # Dock should be added to main window
            mock_add.assert_called_once()
            # Singleton persists
            assert get_panel_dock() is dock
            # create=False returns the existing dock
            assert get_panel_dock(create=False) is dock
    real_mw.deleteLater()


def test_settings_command_opens_dialog(qapp):
    """SettingsCommand.Activated() opens a SettingsDialog."""
    mock_mw = MagicMock()
    with patch("FreeCADGui.getMainWindow", return_value=mock_mw) as mock_get_main, \
         patch("neurocad.ui.settings.SettingsDialog") as DialogClass:
        mock_dialog = MagicMock(spec=SettingsDialog)
        DialogClass.return_value = mock_dialog
        # Import after patching FreeCADGui
        from neurocad.InitGui import SettingsCommand
        cmd = SettingsCommand()
        cmd.Activated()
        # Dialog instantiated with main window as parent
        DialogClass.assert_called_once_with(mock_mw)
        # exec called
        mock_dialog.exec.assert_called_once()
        # Ensure getMainWindow was called
        mock_get_main.assert_called_once()


def test_open_chat_command_imports_panel_lazily(qapp):
    """OpenChatCommand should resolve get_panel_dock at call time."""
    mock_dock = MagicMock()
    with patch("neurocad.ui.panel.get_panel_dock", return_value=mock_dock):
        from neurocad.InitGui import OpenChatCommand

        cmd = OpenChatCommand()
        cmd.Activated()

    mock_dock.show.assert_called_once()
    mock_dock.raise_.assert_called_once()


def test_scroll_to_bottom_uses_scroll_area_scrollbar(qapp):
    """_scroll_to_bottom() should use the QScrollArea scrollbar directly."""
    dock = CopilotPanel()
    scrollbar = MagicMock()
    dock._scroll_area = MagicMock()
    dock._scroll_area.verticalScrollBar.return_value = scrollbar
    scrollbar.maximum.return_value = 42

    dock._scroll_to_bottom()

    scrollbar.setValue.assert_called_once_with(42)


def test_submit_no_assistant_echo(qapp):
    """_on_submit() does not add an assistant message (inert behavior)."""
    with patch("neurocad.ui.panel.FreeCADGui", MagicMock(), create=True) as mock_gui:
        mock_gui.getMainWindow.return_value = None
        import neurocad.ui.panel
        neurocad.ui.panel._panel_dock = None
        dock = CopilotPanel()
        # Mock the add_message method to track calls
        dock._add_message = MagicMock()
        dock._set_busy = MagicMock()
        dock._input = MagicMock()
        dock._input.text.return_value = "test request"
        dock._input.clear = MagicMock()
        dock._on_submit()
        # Should call _add_message exactly once with role "user"
        assert dock._add_message.call_count == 1
        args, kwargs = dock._add_message.call_args
        assert args[0] == "user"
        assert args[1] == "test request"
        # Should NOT call _add_message with role "assistant"
        # (any second call would be assistant)
        # Also ensure _set_busy(False) called
        dock._set_busy.assert_called_once_with(False)
        dock._input.clear.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
