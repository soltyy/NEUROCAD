"""Custom Qt widgets for NeuroCad UI."""

from .compat import Qt, QtWidgets


class MessageBubble(QtWidgets.QFrame):
    """A chat bubble displaying a message with role styling."""

    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self._text = text

        # Create label (common for all roles)
        self._label = QtWidgets.QLabel(text, self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore[attr-defined]

        # Layout differs per role
        if role == "assistant":
            # Horizontal layout: avatar left, label right
            hbox = QtWidgets.QHBoxLayout(self)
            # Avatar "N"
            self._avatar = QtWidgets.QLabel("N", self)
            self._avatar.setFixedSize(24, 24)
            self._avatar.setStyleSheet("""
                QLabel {
                    background-color: #2563eb;
                    border-radius: 12px;
                    color: white;
                    font-weight: bold;
                    qproperty-alignment: AlignCenter;
                }
            """)
            hbox.addWidget(self._avatar)
            hbox.addWidget(self._label, 1)  # stretch
            hbox.setContentsMargins(10, 8, 10, 8)
            # No card styling (transparent background, no border)
            self.setStyleSheet("""
                MessageBubble {
                    background-color: transparent;
                    border: none;
                }
            """)
        else:
            # Vertical layout for user and feedback
            vbox = QtWidgets.QVBoxLayout(self)
            vbox.addWidget(self._label)
            vbox.setContentsMargins(10, 8, 10, 8)

            if role == "user":
                self.setStyleSheet("""
                    MessageBubble {
                        background-color: #f4f4f4;
                        border: 1px solid #e0e0e0;
                        border-radius: 12px;
                    }
                """)
            else:  # feedback, system, etc.
                # Determine feedback color based on text content
                text_lower = text.lower()
                if any(word in text_lower for word in ("success", "exported")):
                    border_color = "#22c55e"   # green
                elif any(word in text_lower for word in ("unsupported", "timed out")):
                    border_color = "#f59e0b"   # yellow
                elif any(word in text_lower for word in ("failed", "error")):
                    border_color = "#ef4444"   # red
                else:
                    border_color = "#94a3b8"   # gray
                # Transparent background, left border only
                self.setStyleSheet(f"""
                    MessageBubble {{
                        background-color: transparent;
                        border: none;
                        border-left: 3px solid {border_color};
                        border-radius: 0px;
                    }}
                """)
                # Font style: 11px italic
                self._label.setStyleSheet("""
                    QLabel {
                        font-size: 11px;
                        font-style: italic;
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
