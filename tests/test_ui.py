"""
UI tests for NeuroCad widgets and panel.

Tests cover:
    - StatusDot state changes
    - MessageBubble role styling
    - CopilotPanel signal emission
"""

import pytest
from PySide6.QtCore import Qt

from neurocad.ui.panel import CopilotPanel
from neurocad.ui.widgets import MessageBubble, StatusDot


def test_status_dot_set_state(qapp):
    """Verify that StatusDot.set_state() updates the internal color."""
    dot = StatusDot()
    # Default state is "idle"
    assert dot._state == "idle"
    # Check that color is set to idle gray
    assert dot._color.name() == "#6c757d"

    dot.set_state("thinking")
    assert dot._state == "thinking"
    assert dot._color.name() == "#ffc107"

    dot.set_state("error")
    assert dot._state == "error"
    assert dot._color.name() == "#dc3545"

    dot.set_state("idle")
    assert dot._state == "idle"
    assert dot._color.name() == "#6c757d"

    # Invalid state raises ValueError
    with pytest.raises(ValueError, match="Invalid state"):
        dot.set_state("unknown")


def test_message_bubble_role_styling(qapp):
    """Verify that MessageBubble applies different CSS per role."""
    from PySide6.QtCore import Qt
    # Assistant (default)
    bubble = MessageBubble("Hello", role="assistant")
    style = bubble.styleSheet()
    assert "background-color: #f8f9fa" in style
    assert "color: #495057" in style
    # alignment is set on internal label, not via stylesheet
    assert bubble.label.alignment() == (Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore[attr-defined]

    # User
    bubble.set_role("user")
    style = bubble.styleSheet()
    assert "background-color: #d1ecf1" in style
    assert "color: #0c5460" in style
    assert bubble.label.alignment() == (Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]

    # System
    bubble.set_role("system")
    style = bubble.styleSheet()
    assert "background-color: #fff3cd" in style
    assert "color: #856404" in style
    assert bubble.label.alignment() == Qt.AlignCenter  # type: ignore[attr-defined]


def test_copilot_panel_signals(qtbot):
    """
    Verify that CopilotPanel emits message_submitted and snapshot_requested signals.
    """
    panel = CopilotPanel()
    qtbot.addWidget(panel)

    # Connect signal spies
    with qtbot.waitSignal(panel.message_submitted, timeout=1000) as blocker:
        panel.input_line.setText("Test message")
        panel.send_button.click()
    # Check that the signal carries the correct text
    assert blocker.args == ["Test message"]
    # Input should be cleared after submission
    assert panel.input_line.text() == ""

    # Simulate Enter key press
    with qtbot.waitSignal(panel.message_submitted, timeout=1000) as blocker:
        panel.input_line.setText("Another message")
        qtbot.keyPress(panel.input_line, Qt.Key_Return)  # type: ignore[attr-defined]
    assert blocker.args == ["Another message"]
    assert panel.input_line.text() == ""

    # Snapshot button
    with qtbot.waitSignal(panel.snapshot_requested, timeout=1000):
        panel.snapshot_button.click()


def test_copilot_panel_status(qapp):
    """Verify that set_status forwards to the StatusDot."""
    panel = CopilotPanel()
    panel.set_status("thinking")
    assert panel.status_dot._state == "thinking"
    assert panel.status_dot._color.name() == "#ffc107"

    panel.set_status("error")
    assert panel.status_dot._state == "error"
    assert panel.status_dot._color.name() == "#dc3545"


def test_message_bubble_add_message(qapp):
    """Test convenience method add_message."""
    panel = CopilotPanel()
    panel.add_message("Hello, world!", role="user")
    # The scroll layout should now contain one widget
    assert panel.scroll_layout.count() == 1
    item = panel.scroll_layout.itemAt(0)
    assert item is not None
    child = item.widget()
    assert isinstance(child, MessageBubble)
    assert child._role == "user"
    assert child.text() == "Hello, world!"
