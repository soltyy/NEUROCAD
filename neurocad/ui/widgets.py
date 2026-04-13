"""Custom Qt widgets for NeuroCad UI."""

from .compat import Qt, QtCore, QtGui, QtWidgets

try:
    from PySide6 import QtSvg

    HAS_SVG = True
except ImportError:
    HAS_SVG = False

from pathlib import Path

FOLD_THRESHOLD_CHARS = 300


class MessageBubble(QtWidgets.QFrame):
    """A chat bubble displaying a message with role styling."""

    def __init__(self, role: str, text: str = "", parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.role = role
        self._text = text
        self._need_fold = len(text) > FOLD_THRESHOLD_CHARS
        if role == "user":
            self._need_fold = False
        self._is_expanded = False

        # Determine display text (preview if folded)
        if self._need_fold and not self._is_expanded:
            display_text = text[:FOLD_THRESHOLD_CHARS] + "…"
        else:
            display_text = text

        # Create label (common for all roles)
        self._label = QtWidgets.QLabel(display_text, self)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore[attr-defined]

        # Expand button (ellipsis/minus)
        self._expand_button = QtWidgets.QPushButton("…", self)
        self._expand_button.setFixedSize(20, 20)
        self._expand_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #666; }"
        )
        self._expand_button.clicked.connect(self._toggle_expand)
        self._expand_button.setVisible(self._need_fold)

        # Layout differs per role
        if role == "assistant":
            # Horizontal layout: avatar left, label right
            hbox = QtWidgets.QHBoxLayout(self)
            # Avatar logo
            self._avatar = QtWidgets.QLabel(self)
            self._avatar.setFixedSize(24, 24)
            # Try to load SVG logo
            pixmap = self._load_logo_pixmap()
            if pixmap is not None:
                self._avatar.setPixmap(pixmap)
                self._avatar.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        border: none;
                    }
                """)
            else:
                # Fallback to letter "N" with blue background
                self._avatar.setText("N")
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
            hbox.addWidget(self._expand_button)
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
            # Button row: stretch + button (only for non-user roles that need fold)
            if role != "user":
                button_row = QtWidgets.QHBoxLayout()
                button_row.addStretch()
                button_row.addWidget(self._expand_button)
                vbox.addLayout(button_row)
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
                    border_color = "#22c55e"  # green
                elif any(word in text_lower for word in ("unsupported", "timed out")):
                    border_color = "#f59e0b"  # yellow
                elif any(word in text_lower for word in ("failed", "error")):
                    border_color = "#ef4444"  # red
                else:
                    border_color = "#94a3b8"  # gray
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

    def _load_logo_pixmap(self):
        """Load neurocad.svg as QPixmap, scaled to 24x24."""
        if not HAS_SVG:
            return None
        try:
            svg_path = Path(__file__).parent.parent / "resources/icons/neurocad.svg"
            if not svg_path.exists():
                return None
            renderer = QtSvg.QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return None
            pixmap = QtGui.QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            try:
                renderer.render(painter)
            finally:
                painter.end()
            return pixmap
        except Exception:
            return None

    @QtCore.Slot()
    def _toggle_expand(self) -> None:
        """Toggle expanded/collapsed state."""
        self._is_expanded = not self._is_expanded
        self._update_display()

    def _update_display(self) -> None:
        """Update label text and button visibility based on expanded state."""
        if self._is_expanded:
            self._label.setText(self._text)
            self._expand_button.setText("−")
        else:
            if self._need_fold:
                preview = self._text[:FOLD_THRESHOLD_CHARS] + "…"
                self._label.setText(preview)
            else:
                self._label.setText(self._text)
            self._expand_button.setText("…")
        # Ensure button visible only if folding needed
        self._expand_button.setVisible(self._need_fold)

    def append_text(self, chunk: str) -> None:
        """Append text to the bubble (streaming)."""
        self._text += chunk
        # Re-evaluate if folding needed after text grows
        if not self._need_fold and len(self._text) > FOLD_THRESHOLD_CHARS:
            self._need_fold = True
        self._update_display()


class StatusDot(QtWidgets.QLabel):
    """A small colored dot indicating thinking/idle/error state."""

    _COLORS = {
        "idle": "#cccccc",
        "thinking": "#2196f3",
        "error": "#f44336",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        """Set visual state: 'idle', 'thinking', 'error'."""
        color = self._COLORS.get(state, "#cccccc")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                border: none;
            }}
        """)
