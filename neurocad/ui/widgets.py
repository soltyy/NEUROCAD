"""Custom Qt widgets for NeuroCad UI."""

from .compat import Qt, QtWidgets


class MessageBubble(QtWidgets.QFrame):
    """A chat bubble displaying a message with role styling."""

    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self._text = text
        self._label = QtWidgets.QLabel(text, self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore[attr-defined]

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.setContentsMargins(10, 8, 10, 8)

        # Basic styling based on role
        if role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #e3f2fd;
                    border: 1px solid #90caf9;
                    border-radius: 12px;
                }
            """)
        elif role == "assistant":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #f5f5f5;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                }
            """)
        else:  # feedback, system, etc.
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #fff8e1;
                    border: 1px solid #ffd54f;
                    border-radius: 12px;
                }
            """)

    def append_text(self, chunk: str):
        """Append text to the bubble (streaming)."""
        self._text += chunk
        self._label.setText(self._text)


class StatusDot(QtWidgets.QLabel):
    """A small colored dot indicating thinking/idle/error state."""

    _COLORS = {
        "idle": "#cccccc",
        "thinking": "#2196f3",
        "error": "#f44336",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_state("idle")

    def set_state(self, state: str):
        """Set visual state: 'idle', 'thinking', 'error'."""
        color = self._COLORS.get(state, "#cccccc")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                border: none;
            }}
        """)
