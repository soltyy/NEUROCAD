"""
Main panel for NeuroCad workbench.

Implements CopilotPanel as a dockable widget with chat input,
status indicator, and snapshot button.
"""

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QDockWidget,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    # Safe fallback for environments without PySide6 (e.g., docs generation)
    QDockWidget = object
    QWidget = object
    QVBoxLayout = object
    QHBoxLayout = object
    QScrollArea = object
    QLineEdit = object
    QPushButton = object
    QLabel = object
    def Signal(*args):
        return None
    Qt = object

from neurocad.ui.widgets import MessageBubble, StatusDot


class CopilotPanel(QDockWidget):
    """
    Dockable panel for the NeuroCad Copilot.

    Provides a simple chat‑like UI with a message list (scroll area),
    a single‑line input, Send button, Snapshot button, and a status indicator.

    Signals:
        message_submitted(str): emitted when the user submits a message.
        snapshot_requested(): emitted when the user requests a snapshot.
    """

    message_submitted = Signal(str)
    snapshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCad Copilot")
        self.setObjectName("NeuroCadCopilotPanel")  # required by FreeCAD

        # Main widget that will hold the layout
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Build the UI
        self._build_ui(main_widget)

    def _build_ui(self, container):
        """Create all UI elements and arrange them in layouts."""
        # Outer vertical layout
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)

        # Status header (horizontal row)
        status_header = QHBoxLayout()
        status_header.addWidget(QLabel("Status:"))
        self.status_dot = StatusDot()
        status_header.addWidget(self.status_dot)
        status_header.addStretch()
        outer_layout.addLayout(status_header)

        # Scroll area for message bubbles (currently empty)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(self.scroll_area)

        # Input row (horizontal)
        input_row = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Type your message...")
        self.input_line.returnPressed.connect(self._on_submit)
        input_row.addWidget(self.input_line)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_button)

        self.snapshot_button = QPushButton("Show Snapshot")
        self.snapshot_button.clicked.connect(self._on_snapshot)
        input_row.addWidget(self.snapshot_button)

        outer_layout.addLayout(input_row)

    def _on_submit(self):
        """Handle Send button click or Enter press."""
        text = self.input_line.text().strip()
        if text:
            self.message_submitted.emit(text)
            self.input_line.clear()

    def _on_snapshot(self):
        """Handle Snapshot button click."""
        self.snapshot_requested.emit()

    # Public API for external control
    def set_status(self, state):
        """
        Change the status dot state.

        Args:
            state: "idle", "thinking", or "error".
        """
        self.status_dot.set_state(state)

    def add_message(self, text, role="assistant"):
        """
        Add a message bubble to the scroll area (for demonstration).

        This is a convenience method; real message history will be managed
        by the workbench or a separate controller.
        """
        bubble = MessageBubble(text, role)
        self.scroll_layout.addWidget(bubble)
