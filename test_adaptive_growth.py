#!/usr/bin/env python3
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
app = QApplication([])

from neurocad.ui.panel import CopilotPanel

panel = CopilotPanel()
panel.setFixedHeight(600)
panel.show()
panel.adjustSize()

input_widget = panel._input
container = panel._input_box
toolbar_layout = container.layout().itemAt(2).layout()

def print_heights():
    print(f"Container height: {container.height()}")
    print(f"Input height: {input_widget.height()}")
    print(f"Input max height: {input_widget.maximumHeight()}")
    print(f"Container max height: {container.maximumHeight()}")
    print(f"Toolbar layout geometry: {toolbar_layout.geometry()}")
    # compute toolbar bottom relative to container bottom
    toolbar_bottom = toolbar_layout.geometry().bottom()
    container_bottom = container.height()
    print(f"Toolbar bottom offset from container bottom: {container_bottom - toolbar_bottom}")

print("Initial state:")
print_heights()

# Simulate adding lines
input_widget.setPlainText("line 1")
input_widget.textChanged.emit()  # trigger _adjust_height
app.processEvents()
print("\nAfter one line:")
print_heights()

# Simulate many lines
long_text = "\n".join([f"line {i}" for i in range(20)])
input_widget.setPlainText(long_text)
input_widget.textChanged.emit()
app.processEvents()
print("\nAfter 20 lines:")
print_heights()

# Check that container does not exceed half panel height (300)
assert container.height() <= 300, f"Container height {container.height()} exceeds half panel"
# Check that toolbar stays at bottom
toolbar_bottom = toolbar_layout.geometry().bottom()
container_bottom = container.height()
# allow 1 pixel tolerance
assert abs(container_bottom - toolbar_bottom) <= 1, f"Toolbar not at bottom, offset {container_bottom - toolbar_bottom}"

# Simulate reaching max height (add many lines)
max_lines = 100
long_text2 = "\n".join([f"line {i}" for i in range(max_lines)])
input_widget.setPlainText(long_text2)
input_widget.textChanged.emit()
app.processEvents()
print("\nAfter many lines (should cap):")
print_heights()
assert input_widget.height() == input_widget.maximumHeight(), "Input height should be at max"
assert container.height() <= 300

# Ensure toolbar still at bottom
toolbar_bottom = toolbar_layout.geometry().bottom()
container_bottom = container.height()
assert abs(container_bottom - toolbar_bottom) <= 1

print("\nAll checks passed.")
app.quit()