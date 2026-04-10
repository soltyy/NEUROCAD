"""Singleton dock panel for NeuroCad.

Contains get_panel_dock() lazy singleton and CopilotPanel QDockWidget.
"""


from ..config.config import load as load_config
from ..core.active_document import get_active_document
from ..core.debug import log_error, log_info, log_warn
from ..core.history import History
from ..core.worker import LLMWorker
from ..llm.registry import load_adapter
from .compat import Qt, QtCore, QtWidgets
from .widgets import MessageBubble, StatusDot

# Global singleton dock widget
_panel_dock = None


def get_panel_dock(create: bool = True):
    """Return the global NeuroCad dock widget, creating it if needed.

    If create=False and the dock does not exist, returns None.
    """
    global _panel_dock
    if _panel_dock is not None:
        return _panel_dock
    if not create:
        return None

    # Need FreeCAD's main window
    try:
        import FreeCADGui  # type: ignore
        mw = FreeCADGui.getMainWindow()
    except ImportError:
        mw = None

    if mw is None:
        return None

    _panel_dock = CopilotPanel(mw)
    if hasattr(mw, "addDockWidget"):
        mw.addDockWidget(Qt.RightDockWidgetArea, _panel_dock)  # type: ignore[attr-defined]
    return _panel_dock


class CopilotPanel(QtWidgets.QDockWidget):
    """Main chat panel dock widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCad")
        self._worker = None
        self._history = History()
        self._adapter = None
        self._request_watchdog = None
        self._last_new_objects = []

        self._build_ui()
        self._connect_signals()
        self._init_adapter()

    def _init_adapter(self):
        """Load adapter from config (falls back to mock if no key)."""
        try:
            config = load_config()
            log_info(
                "panel.init_adapter",
                "loading adapter",
                provider=config.get("provider"),
                model=config.get("model"),
                base_url=config.get("base_url"),
            )
            self._adapter = load_adapter(config)
            log_info(
                "panel.init_adapter",
                "adapter loaded",
                adapter_type=type(self._adapter).__name__,
            )
        except Exception as e:
            # If no API key is configured, we'll keep adapter as None
            # and show an error when user tries to submit.
            self._adapter = None
            log_warn("panel.init_adapter", "adapter unavailable", error=e)

    def set_adapter(self, adapter):
        """Set adapter directly (e.g., from Use once session)."""
        self._adapter = adapter
        if adapter is not None:
            from ..core.debug import log_info
            log_info(
                "panel.set_adapter",
                "adapter updated",
                adapter_type=type(adapter).__name__,
            )
        else:
            from ..core.debug import log_warn
            log_warn("panel.set_adapter", "adapter cleared")

    def _build_ui(self):
        """Create UI elements."""
        central = QtWidgets.QWidget()
        self.setWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Chat area (scrollable)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(scroll_content)
        self._scroll_area = scroll
        self._scroll_layout = scroll_layout
        self._scroll_content = scroll_content

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText("Type your CAD request...")
        self._send_btn = QtWidgets.QPushButton("Send")
        self._snapshot_btn = QtWidgets.QPushButton("Show Snapshot")
        self._export_btn = QtWidgets.QPushButton("Export")
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_btn)
        input_row.addWidget(self._snapshot_btn)
        input_row.addWidget(self._export_btn)

        self._request_watchdog = QtCore.QTimer(self)
        self._request_watchdog.setSingleShot(True)
        self._request_watchdog.timeout.connect(self._on_request_timeout)

        # Status dot in title bar
        self._status_dot = StatusDot()
        title_widget = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QtWidgets.QLabel("NeuroCad"))
        title_layout.addStretch()
        title_layout.addWidget(self._status_dot)
        self.setTitleBarWidget(title_widget)

        # Status line
        status_layout = QtWidgets.QHBoxLayout()
        self._status_label = QtWidgets.QLabel("Ready")
        self._status_label.setStyleSheet("color: #666; font-style: italic;")
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        status_layout.addWidget(self._status_label)
        status_layout.addWidget(self._progress_bar)
        status_layout.setStretch(0, 1)

        # Assemble
        layout.addWidget(scroll)
        layout.addLayout(status_layout)
        layout.addLayout(input_row)

    def _connect_signals(self):
        """Connect UI signals."""
        self._send_btn.clicked.connect(self._on_submit)
        self._snapshot_btn.clicked.connect(self._on_snapshot_requested)
        self._export_btn.clicked.connect(self._on_export_requested)
        self._input.returnPressed.connect(self._on_submit)

    def _add_message(self, role: str, text: str):
        """Append a message bubble to the chat area."""
        bubble = MessageBubble(role, text)
        self._scroll_layout.addWidget(bubble)
        # Scroll to bottom
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll chat area to the bottom."""
        scrollbar = self._scroll_area.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def _set_busy(self, busy: bool):
        """Enable/disable input and update status dot."""
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._snapshot_btn.setEnabled(not busy)
        self._export_btn.setEnabled(not busy)
        self._status_dot.set_state("thinking" if busy else "idle")
        if busy:
            self._status_label.setText("Thinking...")
            self._progress_bar.setVisible(False)  # hide until attempt numbers known
        else:
            self._status_label.setText("Ready")
            self._progress_bar.setVisible(False)
            self._progress_bar.setValue(0)

    def _on_submit(self):
        """Handle Send button or Enter press."""
        text = self._input.text().strip()
        if not text:
            return
        log_info("panel.submit", "received user request", text=text)
        doc = get_active_document()
        if doc is None:
            log_warn("panel.submit", "blocked: no active document")
            self._add_message("feedback", "No active document.")
            return
        if self._adapter is None:
            log_warn("panel.submit", "blocked: adapter is not configured")
            self._add_message("feedback", "LLM adapter not configured. Set API key in Settings.")
            return
        if self._worker is not None and self._worker.is_running():
            # Already running, ignore
            log_warn("panel.submit", "ignored: worker already running")
            return

        self._add_message("user", text)
        self._input.clear()
        self._set_busy(True)
        log_info(
            "panel.submit",
            "starting worker",
            document=getattr(doc, "Name", None),
            adapter_type=type(self._adapter).__name__,
        )

        self._worker = LLMWorker(
            on_chunk=self._on_chunk,
            on_attempt=self._on_attempt,
            on_status=self._on_status,
            on_exec_needed=self._on_exec_needed,
            on_done=self._on_worker_done,
            on_error=self._on_worker_error,
        )
        self._worker.start(text, doc, self._adapter, self._history)
        self._request_watchdog.start(30000)

    def _on_chunk(self, chunk: str):
        """Append a chunk of LLM response to the assistant message."""
        log_info("panel.chunk", "received assistant output", chars=len(chunk), preview=chunk[:160])
        # For simplicity, we'll just add a new assistant message on first chunk
        # and append to it on subsequent chunks.
        # This can be improved with a proper streaming UI in Sprint 3.
        if not hasattr(self, "_current_assistant_bubble"):
            bubble = MessageBubble("assistant", chunk)
            self._scroll_layout.addWidget(bubble)
            self._current_assistant_bubble = bubble
        else:
            self._current_assistant_bubble.append_text(chunk)
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_attempt(self, n: int, mx: int):
        """Update status dot with attempt progress."""
        log_info("panel.attempt", "agent attempt", attempt=n, max_attempts=mx)
        self._status_dot.set_state("thinking")
        # Update progress bar
        self._progress_bar.setRange(0, mx)
        self._progress_bar.setValue(n)
        self._progress_bar.setVisible(True)
        # Update status label
        self._status_label.setText(f"Attempt {n} of {mx}")
        if n > 1:
            self._add_message("feedback", "Retrying")

    def _on_status(self, msg: str):
        """Log pipeline status internally; show compact user-facing statuses."""
        log_info("panel.status", "pipeline status", msg=msg)
        # Map internal status messages to compact user-facing bubbles
        if "sending request to LLM" in msg:
            self._add_message("feedback", "Request sent")
            self._status_label.setText("Request sent")
        elif "execution failed:" in msg:
            # Determine if it's unsupported operation
            if "Unsupported FreeCAD API used" in msg:
                self._add_message("feedback", "Unsupported operation")
                self._status_label.setText("Unsupported operation")
            else:
                self._add_message("feedback", "Execution failed")
                self._status_label.setText("Execution failed")
        elif "timed out" in msg.lower():
            self._add_message("feedback", "Timed out")
            self._status_label.setText("Timed out")
        else:
            # Generic status update (keep existing label)
            pass

    def _on_exec_needed(self, code: str, attempt: int) -> None:
        """Execute code in the main thread and hand the result back to the worker."""
        from ..core.agent import _execute_with_rollback
        log_info("panel.exec", "execution requested", attempt=attempt, code_preview=code[:200])
        doc = get_active_document()
        result_data = {"ok": False, "new_objects": [], "error": "No active document"}
        if doc is None:
            log_warn("panel.exec", "no active document during exec handoff")
            if self._worker is not None:
                self._worker.receive_exec_result(result_data)
            return

        result = _execute_with_rollback(code, doc)
        result_data = {
            "ok": result.ok,
            "new_objects": result.new_objects,
            "error": result.error,
        }
        log_info(
            "panel.exec",
            "execution finished",
            ok=result.ok,
            new_objects=result.new_objects,
            error=result.error,
        )
        if self._worker is not None:
            self._worker.receive_exec_result(result_data)

    def _on_worker_done(self, result):
        """Handle completion of the worker."""
        if self._request_watchdog is not None:
            self._request_watchdog.stop()
        log_info(
            "panel.done",
            "worker finished",
            ok=result.ok,
            attempts=result.attempts,
            error=result.error,
            new_objects=result.new_objects,
        )
        self._worker = None
        self._last_new_objects = result.new_objects if result.ok else []
        self._set_busy(False)
        if not result.ok:
            self._add_message(
                "feedback",
                f"Failed after {result.attempts} attempts: {result.error}",
            )
        else:
            self._add_message("feedback", f"Success! Created {len(result.new_objects)} object(s).")
        # Clear current assistant bubble
        if hasattr(self, "_current_assistant_bubble"):
            del self._current_assistant_bubble

    def _on_worker_error(self, msg: str):
        """Handle worker error."""
        if self._request_watchdog is not None:
            self._request_watchdog.stop()
        log_error("panel.error", "worker error", error=msg)
        self._worker = None
        self._set_busy(False)
        self._add_message("feedback", f"Worker error: {msg}")

    def _on_request_timeout(self):
        """Release the UI if a request appears stuck for too long."""
        if self._worker is None or not self._worker.is_running():
            return
        log_error("panel.timeout", "request watchdog fired", timeout_ms=30000)
        self._worker.cancel()
        self._worker = None
        self._set_busy(False)
        self._add_message("feedback", "Timed out")

    def _on_export_requested(self):
        """Handle Export button click."""
        from pathlib import Path

        from ..core.active_document import get_active_document
        from ..core.exporter import ExportError, export_last_successful
        from .compat import QtWidgets

        doc = get_active_document()
        if doc is None:
            log_warn("panel.export", "blocked: no active document")
            self._add_message("feedback", "No active document.")
            return

        if not self._last_new_objects:
            log_warn("panel.export", "no objects to export")
            self._add_message("feedback", "No objects created yet.")
            return

        # File dialog
        file_filter = "STEP files (*.step *.stp);;STL files (*.stl)"
        file_path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Geometry",
            "",
            file_filter,
        )
        if not file_path:
            return

        # Determine format from filter
        if "STEP" in selected_filter:
            fmt = "step"
            if not file_path.lower().endswith((".step", ".stp")):
                file_path += ".step"
        else:
            fmt = "stl"
            if not file_path.lower().endswith(".stl"):
                file_path += ".stl"

        try:
            export_last_successful(doc, Path(file_path), fmt, self._last_new_objects)
        except ExportError as e:
            log_error("panel.export", "export failed", error=str(e))
            self._add_message("feedback", f"Export failed: {e}")
            return
        except Exception as e:
            log_error("panel.export", "unexpected export error", error=e)
            self._add_message("feedback", f"Export error: {e}")
            return

        filename = Path(file_path).name
        log_info("panel.export", "export succeeded", path=file_path, format=fmt)
        self._add_message(
            "feedback",
            f"Exported {len(self._last_new_objects)} object(s) to {filename}",
        )

    def _on_snapshot_requested(self):
        """Show Snapshot button handler."""
        from ..core import context
        from ..core.active_document import get_active_document

        doc = get_active_document()
        if doc is None:
            log_warn("panel.snapshot", "blocked: no active document")
            self._add_message("feedback", "No active document.")
            return

        try:
            snap = context.capture(doc)
            prompt_str = context.to_prompt_str(snap, max_chars=8000)
            log_info(
                "panel.snapshot",
                "snapshot created",
                document=getattr(doc, "Name", None),
                chars=len(prompt_str),
            )
            self._add_message("assistant", f"Snapshot of {doc.Name}:\n{prompt_str}")
        except Exception as e:
            log_error("panel.snapshot", "snapshot failed", error=e)
            self._add_message("feedback", f"Snapshot failed: {e}")

    def showEvent(self, event):
        """Ensure the dock is raised when shown."""
        super().showEvent(event)
        self.raise_()
