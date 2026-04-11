#!/usr/bin/env python3
"""Debug script to measure input container heights."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
app = QApplication([])

from neurocad.ui.panel import CopilotPanel

panel = CopilotPanel()
panel.show()  # not necessary but ensures layout updates
panel.setFixedHeight(600)  # set panel height
panel._update_container_max_height()

input_widget = panel._input
container = panel._input_box

print(f"Panel height: {panel.height()}")
print(f"Container minimum height: {container.minimumHeight()}")
print(f"Container maximum height: {container.maximumHeight()}")
print(f"Container size hint: {container.sizeHint().height()}")
print(f"Container geometry: {container.geometry().height()}")
print(f"Input minimum height: {input_widget.minimumHeight()}")
print(f"Input maximum height: {input_widget.maximumHeight()}")
print(f"Input size hint: {input_widget.sizeHint().height()}")
print(f"Input geometry: {input_widget.geometry().height()}")
print(f"Fixed overhead: {input_widget._FIXED_OVERHEAD}")

# compute internal elements
layout = container.layout()
print(f"Layout margins: {layout.contentsMargins()}")
print(f"Layout spacing: {layout.spacing()}")

# iterate over layout items
for i in range(layout.count()):
    item = layout.itemAt(i)
    if item.widget():
        w = item.widget()
        print(f"Widget {i}: {w.metaObject().className()} height={w.height() if w.isVisible() else 'hidden'}")
    elif item.layout():
        sub = item.layout()
        print(f"Sub layout {i}: spacing={sub.spacing()}")

# compute sum
# we'll just compute expected minimum height
input_min = input_widget.minimumHeight()
margins = layout.contentsMargins()
spacing = layout.spacing()
# there are two spacings (between three items)
divider_height = 1
toolbar_height = panel._send_btn.height()
expected_min = input_min + margins.top() + margins.bottom() + 2*spacing + divider_height + toolbar_height
print(f"Expected min (input + margins + spacing*2 + divider + toolbar): {expected_min}")
print(f"Difference from container minimum: {container.minimumHeight() - expected_min}")

app.quit()