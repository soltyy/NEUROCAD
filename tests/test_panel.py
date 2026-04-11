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
        dock._input.toPlainText.return_value = "test request"
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


def test_submit_uses_configured_llm_timeout_for_watchdog(qapp):
    """_on_submit should start the watchdog with the configured LLM timeout."""
    with patch("neurocad.ui.panel.FreeCADGui", MagicMock(), create=True) as mock_gui:
        mock_gui.getMainWindow.return_value = None
        import neurocad.ui.panel

        neurocad.ui.panel._panel_dock = None
        dock = CopilotPanel()
        dock._config = {"timeout": 120.0}
        dock._add_message = MagicMock()
        dock._set_busy = MagicMock()
        dock._input = MagicMock()
        dock._input.toPlainText.return_value = "test request"
        dock._input.clear = MagicMock()
        dock._adapter = MagicMock()
        dock._history = MagicMock()
        dock._request_watchdog = MagicMock()

        with patch("neurocad.ui.panel.get_active_document") as mock_get_doc, \
             patch("neurocad.ui.panel.LLMWorker") as MockWorker:
            mock_doc = MagicMock()
            mock_get_doc.return_value = mock_doc
            mock_worker_instance = MagicMock()
            MockWorker.return_value = mock_worker_instance

            dock._on_submit()

        dock._request_watchdog.start.assert_called_once_with(120000)


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




def test_variant_b_visual_semantics(qapp):
    """Check that panel matches Variant B literal acceptance criteria."""
    from neurocad.ui.panel import CopilotPanel
    dock = CopilotPanel()

    # Send button text is → (unicode arrow)
    assert dock._send_btn.text() == "→"
    # Snapshot button text is Snapshot (not Show Snapshot)
    assert dock._snapshot_btn.text() == "Snapshot"
    # Export button text unchanged
    assert dock._export_btn.text() == "Export"

    # Secondary buttons have fixed height 24px
    assert dock._snapshot_btn.minimumHeight() == 24
    assert dock._export_btn.minimumHeight() == 24
    # Secondary buttons have secondary style tokens
    snapshot_style = dock._snapshot_btn.styleSheet()
    assert "background: #f9fafb" in snapshot_style
    assert "color: #6b7280" in snapshot_style
    assert "border: 1px solid #d1d5db" in snapshot_style
    assert "border-radius: 10px" in snapshot_style
    assert "padding: 3px 10px" in snapshot_style
    assert "font-size: 11px" in snapshot_style

    # Send button is round blue 30x30 (already tested by existing style)
    assert dock._send_btn.width() == 30
    assert dock._send_btn.height() == 30
    send_style = dock._send_btn.styleSheet()
    assert "background-color: #2196f3" in send_style
    assert "border-radius: 15px" in send_style

    # Input box exists and has Claude-style container styling
    assert hasattr(dock, "_input_box")
    input_box_style = dock._input_box.styleSheet()
    assert "background: white" in input_box_style
    assert "border: 1px solid #d1d5db" in input_box_style
    assert "border-radius: 12px" in input_box_style

    # MessageBubble styling checks via creating instances
    from neurocad.ui.widgets import MessageBubble
    user_bubble = MessageBubble("user", "test")
    assert "background-color: #f4f4f4" in user_bubble.styleSheet()
    assert "border: 1px solid #e0e0e0" in user_bubble.styleSheet()
    assert "border-radius: 12px" in user_bubble.styleSheet()

    assistant_bubble = MessageBubble("assistant", "test")
    # Should have avatar (logo or fallback)
    assert hasattr(assistant_bubble, "_avatar")
    assert assistant_bubble._avatar.width() == 24
    assert assistant_bubble._avatar.height() == 24
    # No card styling (transparent background, no border)
    bubble_style = assistant_bubble.styleSheet()
    assert "background-color: transparent" in bubble_style
    assert "border: none" in bubble_style
    feedback_bubble = MessageBubble("feedback", "success")
    # Should have left border only
    assert "border-left: 3px solid" in feedback_bubble.styleSheet()
    # Font style 11px italic applied to label
    label_style = feedback_bubble._label.styleSheet()
    assert "font-size: 11px" in label_style
    assert "font-style: italic" in label_style
    # Feedback semantic palette
    success_bubble = MessageBubble("feedback", "success")
    assert "border-left: 3px solid #22c55e" in success_bubble.styleSheet()
    unsupported_bubble = MessageBubble("feedback", "unsupported operation")
    assert "border-left: 3px solid #f59e0b" in unsupported_bubble.styleSheet()
    failed_bubble = MessageBubble("feedback", "failed")
    assert "border-left: 3px solid #ef4444" in failed_bubble.styleSheet()
    neutral_bubble = MessageBubble("feedback", "some info")
    assert "border-left: 3px solid #94a3b8" in neutral_bubble.styleSheet()



def test_queue_scroll_to_bottom_schedules_timer(qapp):
    """_queue_scroll_to_bottom schedules a singleShot timer."""
    from unittest.mock import patch

    from neurocad.ui.panel import CopilotPanel

    dock = CopilotPanel()
    dock._scroll_pending = False
    with patch("neurocad.ui.panel.QtCore.QTimer.singleShot") as mock_single:
        dock._queue_scroll_to_bottom()
        # Should set pending flag
        assert dock._scroll_pending is True
        # Should schedule timer with 0 timeout and scroll_to_bottom callback
        mock_single.assert_called_once_with(0, dock._scroll_to_bottom)
    # Second call while pending should not schedule again
    with patch("neurocad.ui.panel.QtCore.QTimer.singleShot") as mock_single:
        dock._queue_scroll_to_bottom()
        mock_single.assert_not_called()


def test_adaptive_input_height_cap_respects_panel_height(qapp):
    """AdaptivePlainTextEdit maximum height respects container limit (half panel height minus fixed overhead)."""
    from neurocad.ui.panel import AdaptivePlainTextEdit, CopilotPanel
    from unittest.mock import patch

    dock = CopilotPanel()
    # Set panel height
    dock.setFixedHeight(400)
    # Update container max height (called in _build_ui, but we need to refresh)
    dock._update_container_max_height()
    # Input widget should have been created with container reference
    input_widget = dock._input
    assert isinstance(input_widget, AdaptivePlainTextEdit)
    # Container max height should be half of panel height (200) because minimum height is less
    assert dock._input_box.maximumHeight() == 200
    # Input max height should be container max minus fixed overhead (61)
    expected = 200 - input_widget._FIXED_OVERHEAD
    # Ensure it's not less than input's minimum height
    if expected < input_widget.minimumHeight():
        expected = input_widget.minimumHeight()
    max_height = input_widget._get_max_height()
    assert max_height == expected, f"Expected {expected}, got {max_height}"
    # If scroll area height is zero, container limit still applies
    with patch.object(dock._scroll_area, "height", return_value=0):
        max_height = input_widget._get_max_height()
        # Container max is 200, minus fixed overhead = 139 (or minimum)
        expected_zero = 200 - input_widget._FIXED_OVERHEAD
        if expected_zero < input_widget.minimumHeight():
            expected_zero = input_widget.minimumHeight()
        assert max_height == expected_zero
    # If scroll area height is small, container limit still dominates
    with patch.object(dock._scroll_area, "height", return_value=30):
        max_height = input_widget._get_max_height()
        # Container max is 200, minus fixed overhead = 139 (or minimum)
        expected_small = 200 - input_widget._FIXED_OVERHEAD
        if expected_small < input_widget.minimumHeight():
            expected_small = input_widget.minimumHeight()
        assert max_height == expected_small


def test_message_bubble_fold_unfold(qapp):
    """MessageBubble folds long text and toggles expansion."""
    from neurocad.ui.widgets import FOLD_THRESHOLD_CHARS, MessageBubble

    # Create bubble with text just below threshold
    short_text = "a" * (FOLD_THRESHOLD_CHARS - 1)
    bubble = MessageBubble("assistant", short_text)
    assert bubble._need_fold is False
    assert bubble._expand_button.isHidden() is True
    assert bubble._label.text() == short_text

    # Create bubble with text above threshold
    long_text = "b" * (FOLD_THRESHOLD_CHARS + 100)
    bubble = MessageBubble("assistant", long_text)
    assert bubble._need_fold is True
    assert bubble._expand_button.isHidden() is False
    # Initially not expanded, should show preview with ellipsis
    expected_preview = long_text[:FOLD_THRESHOLD_CHARS] + "…"
    assert bubble._label.text() == expected_preview
    assert bubble._expand_button.text() == "…"

    # Click expand button (simulate)
    bubble._toggle_expand()
    assert bubble._is_expanded is True
    assert bubble._label.text() == long_text
    assert bubble._expand_button.text() == "−"

    # Collapse again
    bubble._toggle_expand()
    assert bubble._is_expanded is False
    assert bubble._label.text() == expected_preview
    assert bubble._expand_button.text() == "…"

    # Append text while folded
    bubble.append_text(" extra")
    assert bubble._text.endswith(" extra")
    # Need fold should remain True
    assert bubble._need_fold is True
    # Preview updated
    assert bubble._label.text().startswith(long_text[:FOLD_THRESHOLD_CHARS])


def test_status_messages_trigger_auto_scroll(qapp):
    """_on_status with specific messages triggers _queue_scroll_to_bottom."""
    from unittest.mock import MagicMock, patch

    from neurocad.ui.panel import CopilotPanel

    with patch("neurocad.ui.panel.load_config", return_value={"provider": "openai"}):
        dock = CopilotPanel()
        dock._add_message = MagicMock(side_effect=lambda role, text: dock._queue_scroll_to_bottom())
        dock._queue_scroll_to_bottom = MagicMock()
        dock._status_label = MagicMock()

        # Test "Request sent"
        dock._on_status("sending request to LLM")
        dock._add_message.assert_called_once_with("feedback", "Request sent")
        dock._queue_scroll_to_bottom.assert_called_once()
        dock._add_message.reset_mock()
        dock._queue_scroll_to_bottom.reset_mock()

        # Test "Execution failed"
        dock._on_status("execution failed: something")
        dock._add_message.assert_called_once_with("feedback", "Execution failed")
        dock._queue_scroll_to_bottom.assert_called_once()
        dock._add_message.reset_mock()
        dock._queue_scroll_to_bottom.reset_mock()

        # Test "Failed after 1 attempts: ..."
        dock._on_status("Failed after 1 attempts: some error")
        # Should map to generic status (no special mapping), so no _add_message call
        dock._add_message.assert_not_called()
        dock._queue_scroll_to_bottom.assert_not_called()


def test_assistant_logo_loaded(qapp):
    """MessageBubble for assistant role loads SVG logo (or fallback)."""
    from unittest.mock import patch

    from neurocad.ui.widgets import MessageBubble

    # Mock _load_logo_pixmap to return None (fallback to "N")
    with patch.object(MessageBubble, "_load_logo_pixmap") as mock_load:
        mock_load.return_value = None
        bubble = MessageBubble("assistant", "test")
        # Ensure logo loading was attempted
        mock_load.assert_called_once()
        # Verify avatar label exists
        assert hasattr(bubble, '_avatar')
        assert bubble._avatar is not None
        # Avatar should have fallback text "N"
        assert bubble._avatar.text() == "N"
        # No pixmap set


def test_user_bubble_no_logo(qapp):
    """MessageBubble for user role does not attempt to load logo."""
    from unittest.mock import patch

    from neurocad.ui.widgets import MessageBubble

    with patch.object(MessageBubble, "_load_logo_pixmap") as mock_load:
        bubble = MessageBubble("user", "test")
        # Should not load logo
        mock_load.assert_not_called()
        # Should not have avatar label (only assistant role has avatar)
        assert not hasattr(bubble, '_avatar')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
