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


class TypedBubble(QtWidgets.QFrame):
    """Sprint 6.0+: a chat bubble for typed `Message` instances.

    Renders one of:
      * COMMENT  — italic gray text, left-border, no avatar (rationale)
      * PLAN     — collapsible card with «Plan: N parts» summary, click expands JSON
      * QUESTION — bold text + option-buttons (or text-input for free type);
                   on click emits `answered(text)` signal so the panel can
                   forward the answer to the worker.
      * SNAPSHOT — small status row «step N: M objects created»
      * VERIFY   — status row coloured by `ok` (green ✓ / red ✗)
      * ERROR    — red border + monospace
      * SUCCESS  — green border + bold
    Falls back to MessageBubble visuals for USER / SYSTEM kinds.
    """
    answered = QtCore.Signal(str)        # emitted by QUESTION bubbles

    def __init__(self, msg, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._msg = msg
        self._build()

    def _build(self):
        from ..core.message import MessageKind
        kind = self._msg.kind
        text = self._msg.text or ""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        if kind == MessageKind.COMMENT:
            self._add_foldable_label(
                layout, text, style="QLabel { font-size: 11px; font-style: italic; color: #555; }"
            )
            self.setStyleSheet(
                "TypedBubble { background-color: transparent; border: none; "
                "border-left: 2px solid #cbd5e1; }"
            )
            return

        if kind == MessageKind.PLAN:
            summary = QtWidgets.QLabel(
                f"📋 План: {len(self._msg.data.get('parts', []))} part(s) — "
                f"клик чтобы раскрыть"
            )
            summary.setStyleSheet("QLabel { font-weight: 600; font-size: 12px; }")
            layout.addWidget(summary)
            self._detail = QtWidgets.QPlainTextEdit(self)
            import json
            self._detail.setPlainText(json.dumps(self._msg.data, ensure_ascii=False, indent=2))
            self._detail.setReadOnly(True)
            self._detail.setMaximumHeight(220)
            self._detail.setStyleSheet(
                "QPlainTextEdit { background: #f8fafc; border: 1px solid #e2e8f0; "
                "font-family: monospace; font-size: 10px; }"
            )
            self._detail.hide()
            layout.addWidget(self._detail)
            summary.mousePressEvent = lambda _e: (
                self._detail.setVisible(not self._detail.isVisible())
            )
            self.setStyleSheet(
                "TypedBubble { background-color: #f1f5f9; border: 1px solid #cbd5e1; "
                "border-radius: 8px; }"
            )
            return

        if kind == MessageKind.QUESTION:
            label = QtWidgets.QLabel("❓ " + text, self)
            label.setWordWrap(True)
            label.setStyleSheet("QLabel { font-weight: 600; font-size: 12px; }")
            layout.addWidget(label)
            opts = (self._msg.data or {}).get("options")
            if opts:
                button_row = QtWidgets.QHBoxLayout()
                button_row.setSpacing(6)
                for opt in opts:
                    btn = QtWidgets.QPushButton(opt, self)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.clicked.connect(
                        lambda _checked=False, t=opt: self.answered.emit(t)
                    )
                    button_row.addWidget(btn)
                button_row.addStretch(1)
                layout.addLayout(button_row)
            else:
                edit = QtWidgets.QLineEdit(self)
                edit.setPlaceholderText("Введите ответ и Enter")
                edit.returnPressed.connect(
                    lambda: self.answered.emit(edit.text().strip())
                )
                layout.addWidget(edit)
            self.setStyleSheet(
                "TypedBubble { background-color: #fefce8; "
                "border: 1px solid #facc15; border-radius: 8px; }"
            )
            return

        if kind == MessageKind.SNAPSHOT:
            row = QtWidgets.QLabel(f"📸 {text}", self)
            row.setStyleSheet(
                "QLabel { font-size: 10px; color: #475569; font-family: monospace; }"
            )
            layout.addWidget(row)
            self.setStyleSheet(
                "TypedBubble { background-color: transparent; "
                "border-left: 2px solid #94a3b8; }"
            )
            return

        if kind == MessageKind.VERIFY:
            ok = bool(self._msg.data.get("ok"))
            mark = "✓" if ok else "✗"
            color = "#16a34a" if ok else "#dc2626"
            row = QtWidgets.QLabel(f"{mark} verify: {text}", self)
            row.setStyleSheet(
                f"QLabel {{ font-size: 11px; color: {color}; "
                f"font-weight: 600; }}"
            )
            row.setWordWrap(True)
            layout.addWidget(row)
            self.setStyleSheet(
                f"TypedBubble {{ background-color: transparent; "
                f"border-left: 2px solid {color}; }}"
            )
            return

        if kind == MessageKind.ERROR:
            label = QtWidgets.QLabel("⚠ " + text, self)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setStyleSheet(
                "QLabel { font-size: 11px; color: #b91c1c; font-family: monospace; }"
            )
            layout.addWidget(label)
            self.setStyleSheet(
                "TypedBubble { background-color: #fef2f2; "
                "border: 1px solid #fca5a5; border-radius: 6px; }"
            )
            return

        if kind == MessageKind.SUCCESS:
            label = QtWidgets.QLabel("✓ " + text, self)
            label.setStyleSheet(
                "QLabel { font-size: 12px; color: #15803d; font-weight: 700; }"
            )
            layout.addWidget(label)
            self.setStyleSheet(
                "TypedBubble { background-color: #f0fdf4; "
                "border: 1px solid #86efac; border-radius: 8px; }"
            )
            return

        # Fallback for USER / ANSWER / CODE / SYSTEM
        self._add_foldable_label(layout, text)
        if kind == MessageKind.USER or kind == MessageKind.ANSWER:
            self.setStyleSheet(
                "TypedBubble { background-color: #f4f4f4; "
                "border: 1px solid #e0e0e0; border-radius: 12px; }"
            )
        else:
            self.setStyleSheet(
                "TypedBubble { background-color: transparent; "
                "border-left: 2px solid #94a3b8; }"
            )

    def _add_foldable_label(self, layout, text: str, style: str | None = None) -> None:
        """Sprint 6.0+ UX: long messages fold to a preview + «…» button.
        Click expands. The label is selectable so users can copy text."""
        need_fold = len(text) > FOLD_THRESHOLD_CHARS
        self._fold_state = {"expanded": False, "full_text": text}
        self._fold_label = QtWidgets.QLabel(self)
        self._fold_label.setWordWrap(True)
        self._fold_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if style:
            self._fold_label.setStyleSheet(style)
        if need_fold:
            preview = text[:FOLD_THRESHOLD_CHARS] + "…"
            self._fold_label.setText(preview)
            btn_row = QtWidgets.QHBoxLayout()
            btn_row.setSpacing(4)
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.addStretch(1)
            self._fold_btn = QtWidgets.QPushButton("…", self)
            self._fold_btn.setFixedSize(28, 20)
            self._fold_btn.setToolTip("Развернуть / Свернуть")
            self._fold_btn.setStyleSheet(
                "QPushButton { background: #f3f4f6; border: 1px solid #e5e7eb; "
                "border-radius: 6px; font-size: 11px; }"
            )
            self._fold_btn.clicked.connect(self._toggle_fold)
            btn_row.addWidget(self._fold_btn)
            layout.addWidget(self._fold_label)
            layout.addLayout(btn_row)
        else:
            self._fold_label.setText(text)
            layout.addWidget(self._fold_label)

    def _toggle_fold(self):
        s = getattr(self, "_fold_state", None)
        if not s or not hasattr(self, "_fold_label"):
            return
        if s["expanded"]:
            self._fold_label.setText(s["full_text"][:FOLD_THRESHOLD_CHARS] + "…")
            self._fold_btn.setText("…")
        else:
            self._fold_label.setText(s["full_text"])
            self._fold_btn.setText("−")
        s["expanded"] = not s["expanded"]


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
