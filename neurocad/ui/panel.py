"""Singleton dock panel for NeuroCad.

Contains get_panel_dock() lazy singleton and CopilotPanel QDockWidget.
"""


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
        self._history = []

        self._build_ui()
        self._connect_signals()

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
        self._scroll_layout = scroll_layout
        self._scroll_content = scroll_content

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText("Type your CAD request...")
        self._send_btn = QtWidgets.QPushButton("Send")
        self._snapshot_btn = QtWidgets.QPushButton("Show Snapshot")
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_btn)
        input_row.addWidget(self._snapshot_btn)

        # Status dot in title bar
        self._status_dot = StatusDot()
        title_widget = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QtWidgets.QLabel("NeuroCad"))
        title_layout.addStretch()
        title_layout.addWidget(self._status_dot)
        self.setTitleBarWidget(title_widget)

        # Assemble
        layout.addWidget(scroll)
        layout.addLayout(input_row)

    def _connect_signals(self):
        """Connect UI signals."""
        self._send_btn.clicked.connect(self._on_submit)
        self._snapshot_btn.clicked.connect(self._on_snapshot_requested)
        self._input.returnPressed.connect(self._on_submit)

    def _add_message(self, role: str, text: str):
        """Append a message bubble to the chat area."""
        bubble = MessageBubble(role, text)
        self._scroll_layout.addWidget(bubble)
        # Scroll to bottom
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll chat area to the bottom."""
        scroll = self._scroll_content.parentWidget()
        if scroll:
            scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().maximum()
            )

    def _set_busy(self, busy: bool):
        """Enable/disable input and update status dot."""
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._snapshot_btn.setEnabled(not busy)
        self._status_dot.set_state("thinking" if busy else "idle")

    def _on_submit(self):
        """Handle Send button or Enter press."""
        text = self._input.text().strip()
        if not text:
            return
        self._add_message("user", text)
        self._input.clear()
        # TODO: connect to LLM worker in Sprint 2
        self._set_busy(False)

    def _on_snapshot_requested(self):
        """Show Snapshot button handler."""
        from ..core import context
        from ..core.active_document import get_active_document

        doc = get_active_document()
        if doc is None:
            self._add_message("feedback", "No active document.")
            return

        try:
            snap = context.capture(doc)
            prompt_str = context.to_prompt_str(snap)
            # Limit display length
            if len(prompt_str) > 2000:
                prompt_str = prompt_str[:1997] + "..."
            self._add_message("assistant", f"Snapshot of {doc.Name}:\n{prompt_str}")
        except Exception as e:
            self._add_message("feedback", f"Snapshot failed: {e}")

    def showEvent(self, event):
        """Ensure the dock is raised when shown."""
        super().showEvent(event)
        self.raise_()
