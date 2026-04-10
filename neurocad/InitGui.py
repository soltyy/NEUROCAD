"""FreeCAD workbench entry point."""

import os
import FreeCADGui as Gui

_MOD_DIR = os.path.dirname(os.path.abspath(__file__))


class NeuroCadWorkbench(Gui.Workbench):
    """NeuroCad workbench."""

    MenuText = "NeuroCad"
    ToolTip  = "AI-powered CAD assistant"
    Icon     = os.path.join(_MOD_DIR, "resources", "icons", "neurocad.svg")

    def Initialize(self):
        Gui.addCommand("NeuroCad_OpenChat", OpenChatCommand())
        Gui.addCommand("NeuroCad_Settings", SettingsCommand())
        self.appendToolbar("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])
        self.appendMenu("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])

    def Activated(self):
        from neurocad.ui.panel import get_panel_dock
        dock = get_panel_dock()
        if dock:
            dock.show()

    def Deactivated(self):
        from neurocad.ui.panel import get_panel_dock
        dock = get_panel_dock(create=False)
        if dock:
            dock.hide()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class OpenChatCommand:
    def GetResources(self):
        return {
            "Pixmap": os.path.join(_MOD_DIR, "resources", "icons", "neurocad.svg"),
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
    def GetResources(self):
        return {
            "Pixmap": "preferences-system.svg",
            "MenuText": "Settings",
            "ToolTip": "Configure LLM provider and API key",
        }

    def Activated(self):
        from neurocad.ui.panel import get_panel_dock
        from neurocad.ui.settings import SettingsDialog
        parent = Gui.getMainWindow()
        dlg = SettingsDialog(parent)
        result = dlg.exec()
        if result == SettingsDialog.Accepted:
            adapter = dlg.get_adapter()
            panel = get_panel_dock(create=False)
            if adapter is not None:
                if panel is not None:
                    panel.set_adapter(adapter)
            else:
                if panel is not None:
                    panel._init_adapter()

    def IsActive(self):
        return True


Gui.addWorkbench(NeuroCadWorkbench())