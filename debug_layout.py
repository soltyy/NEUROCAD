#!/usr/bin/env python3
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
app = QApplication([])

from neurocad.ui.panel import CopilotPanel

panel = CopilotPanel()
panel.setFixedHeight(600)
panel.show()

# force layout update
panel.adjustSize()

scroll = panel._scroll_area
container = panel._input_box
main_layout = panel.widget().layout()

print(f"Panel fixed height: {panel.height()}")
print(f"Main layout margins: {main_layout.contentsMargins()}")
print(f"Main layout spacing: {main_layout.spacing()}")

# iterate main layout items
for i in range(main_layout.count()):
    item = main_layout.itemAt(i)
    w = item.widget()
    if w:
        print(f"Main widget {i}: {w.metaObject().className()} geometry={w.geometry().height()} sizeHint={w.sizeHint().height()} min={w.minimumHeight()} max={w.maximumHeight()}")

print("--- Scroll area details ---")
print(f"Scroll area geometry height: {scroll.geometry().height()}")
print(f"Scroll area viewport height: {scroll.viewport().geometry().height()}")
print(f"Scroll area widget (content) height: {scroll.widget().geometry().height() if scroll.widget() else None}")

print("--- Container details ---")
print(f"Container geometry: {container.geometry()}")
print(f"Container sizeHint: {container.sizeHint()}")
print(f"Container min: {container.minimumHeight()} max: {container.maximumHeight()}")
print(f"Container vertical size policy: {container.sizePolicy().verticalPolicy()}")

# compute expected height based on internal layout
input_widget = panel._input
input_height = input_widget.geometry().height()
divider = container.layout().itemAt(1).widget()
toolbar_layout = container.layout().itemAt(2).layout()
toolbar_height = toolbar_layout.geometry().height() if toolbar_layout else None
print(f"Input height: {input_height}")
print(f"Divider height: {divider.height()}")
print(f"Toolbar layout geometry height: {toolbar_height}")

# compute sum of internal heights + margins + spacing
layout = container.layout()
margins = layout.contentsMargins()
spacing = layout.spacing()
# count spacings: there are three items (input row, divider, toolbar) -> two spacings
internal_sum = input_height + divider.height() + (toolbar_height or 0) + margins.top() + margins.bottom() + 2 * spacing
print(f"Sum of internal heights + margins + spacing: {internal_sum}")
print(f"Difference with container geometry height: {container.geometry().height() - internal_sum}")

# check if container has extra space due to stretch factor
# see if input row is stretched
input_row_item = container.layout().itemAt(0)
if input_row_item.layout():
    input_row_layout = input_row_item.layout()
    print(f"Input row layout stretch factor: {container.layout().stretch(0)}")
    # check if input widget stretch factor inside row
    for j in range(input_row_layout.count()):
        item = input_row_layout.itemAt(j)
        if item.widget():
            print(f"  Input widget stretch: {input_row_layout.stretch(j)}")

app.quit()