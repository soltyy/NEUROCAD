"""Settings dialog for provider selection and API key management."""

from .compat import QtWidgets


class SettingsDialog(QtWidgets.QDialog):
    """Dialog to configure LLM provider and API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCad Settings")
        # Implementation will be added in Sprint 2/3
