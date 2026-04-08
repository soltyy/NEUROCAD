"""
Settings UI for NeuroCad.

Placeholder module.
"""

try:
    from PySide6.QtWidgets import QCheckBox, QDialog, QVBoxLayout
except ImportError:
    # Safe fallback
    QDialog = object
    QVBoxLayout = object
    QCheckBox = object


class SettingsDialog(QDialog):
    """Stub settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCad Settings")
        layout = QVBoxLayout()
        layout.addWidget(QCheckBox("Enable AI suggestions"))
        self.setLayout(layout)
