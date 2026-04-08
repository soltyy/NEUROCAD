"""
Custom widgets for NeuroCad.

Implements MessageBubble (chat message with role-based styling) and
StatusDot (small indicator for idle/thinking/error states).
"""

try:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
    from PySide6.QtWidgets import QFrame, QLabel, QWidget
except ImportError:
    # Safe fallback for environments without PySide6 (e.g., docs generation)
    QFrame = object
    QLabel = object
    QWidget = object
    Qt = object
    QSize = object
    QPainter = object
    QBrush = object
    QColor = object
    QPalette = object


class MessageBubble(QFrame):
    """
    A chat message bubble with role-based styling.

    Roles:
        - "user": light blue background, right-aligned text.
        - "assistant": light gray background, left-aligned text.
        - "system": light yellow background, centered text.
    """

    def __init__(self, text="", role="assistant", parent=None):
        super().__init__(parent)
        self._role = role
        self.label = QLabel(text, self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("background-color: transparent;")
        # Use a layout to manage label positioning
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self._update_style()

    def set_role(self, role):
        """Change the role and update styling."""
        self._role = role
        self._update_style()

    def _update_style(self):
        """Apply CSS styling based on current role."""
        if self._role == "user":
            self.setStyleSheet(
                "QFrame {"
                "  background-color: #d1ecf1;"
                "  border: 1px solid #bee5eb;"
                "  border-radius: 12px;"
                "  padding: 8px 12px;"
                "  margin: 4px 0;"
                "  color: #0c5460;"
                "}"
            )
            self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
        elif self._role == "system":
            self.setStyleSheet(
                "QFrame {"
                "  background-color: #fff3cd;"
                "  border: 1px solid #ffeaa7;"
                "  border-radius: 12px;"
                "  padding: 8px 12px;"
                "  margin: 4px 0;"
                "  color: #856404;"
                "}"
            )
            self.label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        else:  # assistant (default)
            self.setStyleSheet(
                "QFrame {"
                "  background-color: #f8f9fa;"
                "  border: 1px solid #e9ecef;"
                "  border-radius: 12px;"
                "  padding: 8px 12px;"
                "  margin: 4px 0;"
                "  color: #495057;"
                "}"
            )
            self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore[attr-defined]

    def text(self):
        """Return the bubble's text."""
        return self.label.text()

    def setText(self, text):
        """Set the bubble's text."""
        self.label.setText(text)


class StatusDot(QWidget):
    """
    A small circular status indicator with three states: idle, thinking, error.

    States:
        - idle: gray (#6c757d)
        - thinking: yellow (#ffc107)
        - error: red (#dc3545)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(16, 16))
        self._state = "idle"
        self._color = QColor("#6c757d")

    def set_state(self, state):
        """
        Change the displayed state.

        Args:
            state: one of "idle", "thinking", "error".
        """
        state = state.lower()
        if state not in ("idle", "thinking", "error"):
            raise ValueError(f"Invalid state: {state}")
        self._state = state
        if state == "idle":
            self._color = QColor("#6c757d")   # gray
        elif state == "thinking":
            self._color = QColor("#ffc107")   # yellow
        else:  # error
            self._color = QColor("#dc3545")   # red
        self.update()  # trigger repaint

    def paintEvent(self, event):
        """Draw a filled circle with the current color."""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)  # type: ignore[attr-defined]
            painter.setBrush(QBrush(self._color))
            painter.setPen(Qt.NoPen)  # type: ignore[attr-defined]
            painter.drawEllipse(0, 0, self.width(), self.height())
        except (AttributeError, TypeError):
            # Fallback when PySide6 is not available
            pass
