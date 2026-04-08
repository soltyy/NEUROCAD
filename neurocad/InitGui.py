"""FreeCAD workbench entry point (ghbalf pattern)."""

import FreeCADGui  # type: ignore

from .ui.panel import get_panel_dock


class NeuroCadWorkbench(FreeCADGui.Workbench):
    """NeuroCad workbench."""

    MenuText = "NeuroCad"
    ToolTip = "AI‑powered CAD assistant"
    Icon = """placeholder"""

    def Initialize(self):
        """Called when workbench is loaded. Do NOT create dock widgets here."""
        # Create toolbar and menu
        self.appendToolbar("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])
        self.appendMenu("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])

    def Activated(self):
        """Called when the workbench is activated."""
        dock = get_panel_dock()
        if dock:
            dock.show()

    def Deactivated(self):
        """Called when the workbench is deactivated."""
        dock = get_panel_dock(create=False)
        if dock:
            dock.hide()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class OpenChatCommand:
    """Command to open the NeuroCad chat panel."""

    def GetResources(self):
        return {
            "Pixmap": "neurocad.svg",  # placeholder
            "MenuText": "Open Chat",
            "ToolTip": "Open NeuroCad chat panel",
        }

    def Activated(self):
        dock = get_panel_dock()
        if dock:
            dock.show()
            dock.raise_()

    def IsActive(self):
        return True


class SettingsCommand:
    """Command to open settings dialog."""

    def GetResources(self):
        return {
            "Pixmap": "preferences-system.svg",  # placeholder
            "MenuText": "Settings",
            "ToolTip": "Configure LLM provider and API key",
        }

    def Activated(self):
        import FreeCADGui

        from neurocad.ui.settings import SettingsDialog
        parent = FreeCADGui.getMainWindow()
        dlg = SettingsDialog(parent)
        dlg.exec()

    def IsActive(self):
        return True


# Register commands and workbench
FreeCADGui.addCommand("NeuroCad_OpenChat", OpenChatCommand())
FreeCADGui.addCommand("NeuroCad_Settings", SettingsCommand())
FreeCADGui.addWorkbench(NeuroCadWorkbench())
