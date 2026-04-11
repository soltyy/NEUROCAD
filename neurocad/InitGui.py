"""FreeCAD workbench entry point (ghbalf pattern)."""

import inspect
import os

import FreeCADGui  # type: ignore

frame = inspect.currentframe()
if frame is None:
    _wb_dir = os.path.dirname(os.path.abspath(__file__))
else:
    _wb_dir = os.path.dirname(inspect.getfile(frame))
FreeCADGui.addIconPath(os.path.join(_wb_dir, "resources", "icons"))


class NeuroCadWorkbench(FreeCADGui.Workbench):
    """NeuroCad workbench."""

    MenuText = "NeuroCad"
    ToolTip = "AI‑powered CAD assistant"
    Icon = "neurocad.svg"

    def Initialize(self):
        """Called when workbench is loaded. Do NOT create dock widgets here."""
        # Create toolbar and menu
        self.appendToolbar("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])
        self.appendMenu("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])

    def Activated(self):
        """Called when the workbench is activated."""
        from neurocad.ui.panel import get_panel_dock

        dock = get_panel_dock()
        if dock:
            dock.show()

    def Deactivated(self):
        """Called when the workbench is deactivated."""
        from neurocad.ui.panel import get_panel_dock

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
        from neurocad.ui.panel import get_panel_dock

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
        import FreeCADGui  # type: ignore

        from neurocad.ui.panel import get_panel_dock
        from neurocad.ui.settings import SettingsDialog
        parent = FreeCADGui.getMainWindow()
        dlg = SettingsDialog(parent)
        result = dlg.exec()
        # If dialog was accepted, update panel's adapter if needed
        if result == SettingsDialog.Accepted:
            adapter = dlg.get_adapter()
            panel = get_panel_dock(create=False)
            if adapter is not None:
                # Use once session adapter
                if panel is not None:
                    panel.set_adapter(adapter)
            else:
                # Saved to keyring; panel should reload config
                if panel is not None:
                    panel._init_adapter()

    def IsActive(self):
        return True


# Register commands and workbench
FreeCADGui.addCommand("NeuroCad_OpenChat", OpenChatCommand())
FreeCADGui.addCommand("NeuroCad_Settings", SettingsCommand())
FreeCADGui.addWorkbench(NeuroCadWorkbench())
