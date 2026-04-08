"""
NeuroCad workbench for FreeCAD.

Implements CadCopilotWorkbench with a dockable chat panel.
"""

try:
    import FreeCAD
    import FreeCADGui
    from PySide6 import QtCore
except ImportError:
    # Mock modules for environments without FreeCAD (e.g., tests, docs)
    FreeCAD = None
    FreeCADGui = None
    QtCore = None

import logging

from neurocad.ui.panel import CopilotPanel


class CadCopilotWorkbench:
    """
    FreeCAD workbench that provides the NeuroCad Copilot panel.

    MenuText: "NeuroCad"
    ToolTip: "AI‑assisted CAD commands"
    Icon: (placeholder)
    """

    MenuText = "NeuroCad"
    ToolTip = "AI‑assisted CAD commands"
    Icon = ""  # optional path to an icon file

    def __init__(self):
        self.panel = None

    def Initialize(self):
        """
        Called once when the workbench is first loaded.

        Creates the CopilotPanel and docks it on the right side.
        """
        if FreeCADGui is not None:
            main_window = FreeCADGui.getMainWindow()
            # Create the panel
            self.panel = CopilotPanel(main_window)
            self.panel.setObjectName("NeuroCadCopilotPanel")
            # Dock it on the right side (QtCore.RightDockWidgetArea)
            area = QtCore.Qt.RightDockWidgetArea if QtCore else 2  # type: ignore[attr-defined]
            main_window.addDockWidget(area, self.panel)
            # Hide initially; will be shown when workbench is activated
            self.panel.hide()

    def Activated(self):
        """
        Called when the user switches to this workbench.

        Shows the CopilotPanel.
        """
        if self.panel:
            self.panel.show()

    def Deactivated(self):
        """
        Called when the user switches away from this workbench.

        Hides the CopilotPanel.
        """
        if self.panel:
            self.panel.hide()

    def ContextMenu(self, recipient):
        """Optional: context menu entries."""
        pass

    def GetClassName(self):
        """Required by FreeCAD."""
        return "Gui::PythonWorkbench"


def register_workbench():
    """
    Register the CadCopilotWorkbench with FreeCADGui.

    This function is called from InitGui.py when FreeCAD starts.
    It does nothing if FreeCADGui is not available (e.g., in console mode).
    """
    if FreeCADGui is not None:
        try:
            FreeCADGui.addWorkbench(CadCopilotWorkbench)
            logging.debug("[NeuroCad] Workbench registered.")
        except Exception as e:
            logging.error(f"[NeuroCad] Failed to register workbench: {e}")
    else:
        logging.debug(
            "[NeuroCad] FreeCADGui not available; workbench registration skipped."
        )
