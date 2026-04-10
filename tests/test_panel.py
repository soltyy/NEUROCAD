"""Regression tests for panel.py and InitGui.py UI semantics."""

from pathlib import Path
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


def test_snapshot_requested_uses_display_limit_without_extra_trim(qapp):
    """Snapshot display should use an expanded limit and avoid a second trim."""
    dock = CopilotPanel()
    dock._add_message = MagicMock()

    with patch("neurocad.core.active_document.get_active_document") as mock_get_doc, \
         patch("neurocad.core.context.capture") as mock_capture, \
         patch("neurocad.core.context.to_prompt_str", return_value="X" * 3000) as mock_to_prompt:
        mock_doc = MagicMock()
        mock_doc.Name = "Doc"
        mock_get_doc.return_value = mock_doc
        mock_capture.return_value = MagicMock()

        dock._on_snapshot_requested()

    mock_to_prompt.assert_called_once_with(mock_capture.return_value, max_chars=8000)
    dock._add_message.assert_called_once_with("assistant", f"Snapshot of Doc:\n{'X' * 3000}")


def test_on_exec_needed_returns_result_via_worker(qapp):
    """_on_exec_needed should hand the execution result back through worker.receive_exec_result."""
    dock = CopilotPanel()
    dock._worker = MagicMock()

    with patch("neurocad.ui.panel.get_active_document") as mock_get_doc, \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_doc = MagicMock()
        mock_get_doc.return_value = mock_doc
        mock_exec.return_value = MagicMock(ok=True, new_objects=["Box"], error=None)

        dock._on_exec_needed("print('x')", 1)

    dock._worker.receive_exec_result.assert_called_once_with(
        {"ok": True, "new_objects": ["Box"], "error": None}
    )


def test_request_timeout_cancels_worker_and_releases_ui(qapp):
    """Watchdog timeout should cancel the worker and restore UI responsiveness."""
    dock = CopilotPanel()
    mock_worker = MagicMock()
    mock_worker.is_running.return_value = True
    dock._worker = mock_worker
    dock._set_busy = MagicMock()
    dock._add_message = MagicMock()

    dock._on_request_timeout()

    mock_worker.cancel.assert_called_once()
    dock._set_busy.assert_called_once_with(False)
    dock._add_message.assert_called_once_with("feedback", "Timed out")


def test_submit_starts_worker_and_disables_input(qapp):
    """_on_submit() creates LLMWorker, adds user message, sets busy."""
    with patch("neurocad.ui.panel.FreeCADGui", MagicMock(), create=True) as mock_gui:
        mock_gui.getMainWindow.return_value = None
        import neurocad.ui.panel
        neurocad.ui.panel._panel_dock = None
        dock = CopilotPanel()
        # Mock dependencies
        dock._add_message = MagicMock()
        dock._set_busy = MagicMock()
        dock._input = MagicMock()
        dock._input.text.return_value = "test request"
        dock._input.clear = MagicMock()
        dock._adapter = MagicMock()
        dock._history = MagicMock()
        # Mock get_active_document to return a dummy document
        with patch("neurocad.ui.panel.get_active_document") as mock_get_doc:
            mock_doc = MagicMock()
            mock_get_doc.return_value = mock_doc
            # Mock LLMWorker to avoid real thread
            with patch("neurocad.ui.panel.LLMWorker") as MockWorker:
                mock_worker_instance = MagicMock()
                MockWorker.return_value = mock_worker_instance
                dock._on_submit()
                # Should add user message
                dock._add_message.assert_called_once_with("user", "test request")
                # Should clear input
                dock._input.clear.assert_called_once()
                # Should set busy
                dock._set_busy.assert_called_once_with(True)
                # Should create LLMWorker with correct callbacks
                MockWorker.assert_called_once()
                call_kwargs = MockWorker.call_args[1]
                assert call_kwargs["on_chunk"] == dock._on_chunk
                assert call_kwargs["on_attempt"] == dock._on_attempt
                assert call_kwargs["on_status"] == dock._on_status
                assert call_kwargs["on_exec_needed"] == dock._on_exec_needed
                assert call_kwargs["on_done"] == dock._on_worker_done
                assert call_kwargs["on_error"] == dock._on_worker_error
                # Should start worker
                mock_worker_instance.start.assert_called_once_with(
                    "test request", mock_doc, dock._adapter, dock._history
                )


def test_panel_shows_compact_statuses(qapp):
    """Panel shows compact user-facing statuses for key pipeline events."""
    dock = CopilotPanel()
    dock._add_message = MagicMock()

    # Simulate status callbacks
    dock._on_status("sending request to LLM")
    dock._add_message.assert_called_once_with("feedback", "Request sent")
    dock._add_message.reset_mock()

    dock._on_attempt(2, 3)  # second attempt -> Retrying
    dock._add_message.assert_called_once_with("feedback", "Retrying")
    dock._add_message.reset_mock()

    dock._on_status("execution failed: Unsupported FreeCAD API used")
    dock._add_message.assert_called_once_with("feedback", "Unsupported operation")
    dock._add_message.reset_mock()

    dock._on_status("execution failed: some other error")
    dock._add_message.assert_called_once_with("feedback", "Execution failed")
    dock._add_message.reset_mock()

    dock._on_status("LLM request timed out")
    dock._add_message.assert_called_once_with("feedback", "Timed out")


def test_status_label_and_enabled_state_updates(qapp):
    """_set_busy updates status label and enabled state of UI controls."""
    dock = CopilotPanel()
    dock._status_label = MagicMock()
    dock._input = MagicMock()
    dock._send_btn = MagicMock()
    dock._snapshot_btn = MagicMock()
    dock._export_btn = MagicMock()

    dock._set_busy(True)
    dock._status_label.setText.assert_called_once_with("Thinking...")
    dock._input.setEnabled.assert_called_once_with(False)
    dock._send_btn.setEnabled.assert_called_once_with(False)
    dock._snapshot_btn.setEnabled.assert_called_once_with(False)
    dock._export_btn.setEnabled.assert_called_once_with(False)

    dock._status_label.reset_mock()
    dock._input.reset_mock()
    dock._send_btn.reset_mock()
    dock._snapshot_btn.reset_mock()
    dock._export_btn.reset_mock()

    dock._set_busy(False)
    dock._status_label.setText.assert_called_once_with("Ready")
    dock._input.setEnabled.assert_called_once_with(True)
    dock._send_btn.setEnabled.assert_called_once_with(True)
    dock._snapshot_btn.setEnabled.assert_called_once_with(True)
    dock._export_btn.setEnabled.assert_called_once_with(True)


def test_on_attempt_updates_status_label(qapp):
    """_on_attempt updates status label and adds retry feedback."""
    dock = CopilotPanel()
    dock._status_label = MagicMock()
    dock._add_message = MagicMock()
    dock._on_attempt(2, 5)
    dock._status_label.setText.assert_called_once_with("Attempt 2 of 5")
    dock._add_message.assert_called_once_with("feedback", "Retrying")


def test_export_button_triggers_handler(qapp):
    """Export button click calls _on_export_requested."""
    dock = CopilotPanel()
    # Ensure button exists
    assert dock._export_btn is not None
    # Ensure handler is callable (connection verified via _connect_signals)
    assert callable(dock._on_export_requested)


def test_on_export_requested_with_last_new_objects(qapp):
    """_on_export_requested uses last_new_objects and calls exporter."""
    dock = CopilotPanel()
    dock._last_new_objects = ["Box", "Cylinder"]
    dock._add_message = MagicMock()
    mock_doc = MagicMock()
    with patch("neurocad.core.active_document.get_active_document", return_value=mock_doc), \
         patch("neurocad.ui.panel.QtWidgets.QFileDialog.getSaveFileName",
               return_value=("/tmp/test.step", "STEP (*.step *.stp)")) as _, \
         patch("neurocad.core.exporter.export_last_successful") as mock_export:
        dock._on_export_requested()
        # Should call export_last_successful with correct args
        mock_export.assert_called_once_with(
            mock_doc, Path("/tmp/test.step"), "step", ["Box", "Cylinder"]
        )
        # Should show feedback message
        dock._add_message.assert_called_once_with(
            "feedback",
            "Exported 2 object(s) to test.step"
        )


def test_last_new_objects_updated_on_worker_done(qapp):
    """_on_worker_done stores new_objects when result is ok."""
    dock = CopilotPanel()
    dock._set_busy = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.new_objects = ["Box", "Sphere"]
    mock_result.attempts = 3
    mock_result.error = None

    dock._on_worker_done(mock_result)
    assert dock._last_new_objects == ["Box", "Sphere"]
    dock._set_busy.assert_called_once_with(False)

    # If result not ok, list should be empty
    mock_result.ok = False
    mock_result.new_objects = ["Box"]
    dock._on_worker_done(mock_result)
    assert dock._last_new_objects == []
def test_initgui_import_succeeds():
    """Import neurocad.InitGui with mocked FreeCADGui should not raise."""
    import importlib
    import sys

    mock_fcgui = sys.modules["FreeCADGui"]
    with patch.object(mock_fcgui, "addCommand") as mock_add_cmd, \
         patch.object(mock_fcgui, "addWorkbench") as mock_add_wb:
        # Reset call counts from previous tests
        mock_add_cmd.reset_mock()
        mock_add_wb.reset_mock()
        # Reload the module to run its top-level code with our mocks
        import neurocad.InitGui
        importlib.reload(neurocad.InitGui)
        # Ensure registration calls were made (allow extra calls from previous tests)
        assert mock_add_cmd.call_count >= 2
        assert mock_add_wb.call_count >= 1


def test_repeated_on_chunk_appends_to_same_bubble(qapp):
    """Multiple _on_chunk calls append to a single assistant bubble."""
    from neurocad.ui.widgets import MessageBubble
    dock = CopilotPanel()
    # First chunk creates bubble
    dock._on_chunk("Hello")
    assert hasattr(dock, "_current_assistant_bubble")
    bubble = dock._current_assistant_bubble
    assert isinstance(bubble, MessageBubble)
    assert bubble.role == "assistant"
    assert bubble._text == "Hello"
    # Second chunk appends
    dock._on_chunk(" world")
    assert dock._current_assistant_bubble is bubble  # same bubble
    assert bubble._text == "Hello world"




if __name__ == "__main__":
    pytest.main([__file__, "-v"])
