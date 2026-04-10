"""FreeCAD workbench entry point (root)."""

from neurocad.InitGui import *  # noqa: F403

# Import the actual workbench definition from the neurocad package and
# re-export it for backward compatibility with FreeCAD mod layouts.
__all__ = ["NeuroCadWorkbench", "OpenChatCommand", "SettingsCommand"]  # noqa: F405
