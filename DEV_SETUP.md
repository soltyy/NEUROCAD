# NeuroCad Development Setup (macOS arm64, FreeCAD 1.1.0 bundle)

## Prerequisites

- **macOS** arm64 (Apple Silicon)
- **FreeCAD 1.1.0** (or later) installed via the official bundle
- **System Python 3.11** (for creating the virtual environment; install via `brew install python@3.11` or use the system-provided one)
- **FreeCAD bundle Python 3.11** (included with FreeCAD; required for accessing FreeCAD API and PySide6)

## 1. Clone the repository

```bash
git clone https://github.com/neurocad/neurocad.git
cd neurocad
```

## 2. Create and activate virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Note:** Use the system Python 3.11 (not the FreeCAD bundle Python) for creating the virtual environment.

Verify activation:

```bash
which python   # should be .../neurocad/.venv/bin/python
python --version  # Python 3.11.x
```

## 3. Install the package in development mode

```bash
pip install -e ".[dev]"
```

This installs runtime dependencies (`pydantic>=2.7`, `keyring>=25.0`) and dev tools (`pytest`, `pytest-qt`, `ruff`, `mypy`).

**⚠️ CRITICAL:** Do **NOT** install PySide6 via pip. PySide6 is already bundled with FreeCAD and will be imported from the system path.

## 4. Set up PYTHONPATH for FreeCAD API

FreeCAD’s Python modules are located inside the application bundle. Add them to `PYTHONPATH` before running any code that uses FreeCAD API (e.g., tests, interactive development).

```bash
export PYTHONPATH="/Applications/FreeCAD.app/Contents/Resources/lib:/Applications/FreeCAD.app/Contents/Resources/lib/python3.11/site-packages:$PYTHONPATH"
```

You can add this line to your shell profile (`~/.zshrc` or `~/.bash_profile`) for convenience.

## 5. Symlink the module into FreeCAD’s Mod directory

FreeCAD loads external modules from `~/Library/Application Support/FreeCAD/Mod/` on macOS. Create a symlink there:

```bash
mkdir -p ~/Library/Application\ Support/FreeCAD/Mod/
ln -sf "$(pwd)/neurocad" ~/Library/Application\ Support/FreeCAD/Mod/neurocad
```

After restarting FreeCAD, the NeuroCad workbench should appear in the workbench dropdown.

## 6. Verifying the FreeCAD Workbench

After creating the symlink and restarting FreeCAD, you should verify that the NeuroCad workbench is correctly loaded.

### Visual verification in FreeCAD GUI

1. **Launch FreeCAD** (if not already running).
2. **Check the workbench dropdown** (top‑left corner of the main window). You should see “NeuroCad” in the list.
3. **Select “NeuroCad”** from the dropdown. This activates the workbench.
4. **Verify the Copilot panel** appears docked on the right side of the window. It should contain a chat interface labeled “NeuroCad Copilot”.

If the panel does not appear, ensure the symlink points to the correct directory and that FreeCAD has been restarted after creating the link.

### Verification via Python console

FreeCAD includes a Python console (**View → Panels → Python console**) where you can run Python commands to inspect the loaded modules.

1. Open the Python console inside FreeCAD.
2. Run the following commands to confirm that the `neurocad` module can be imported and that its workbench is registered:

```python
import neurocad
print(neurocad.__file__)  # Should point to the symlinked location

# Importing neurocad automatically registers the workbench if FreeCADGui is available.
# You can verify the registration by checking the workbench list.
import FreeCADGui
workbenches = FreeCADGui.listWorkbenches()
print("CadCopilotWorkbench" in workbenches)  # Should print True (key is the class name)

# The following call is idempotent and safe; it will not double‑register.
from neurocad.workbench import register_workbench
register_workbench()  # This will log a debug message if registration succeeds
```

If any of these commands fail with an `ImportError`, check that `PYTHONPATH` includes the FreeCAD bundle libraries (see step 4) and that the symlink is present.

## 7. Running tests

Activate the virtual environment first:

```bash
source .venv/bin/activate
```

Run linting and type checking:

```bash
ruff check .
mypy .
```

Run unit tests (with offscreen Qt platform and FreeCAD’s bundled PySide6):

Make sure `PYTHONPATH` includes FreeCAD’s library path (see step 4). You can either set it permanently in your shell profile or prefix the test command:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH="/Applications/FreeCAD.app/Contents/Resources/lib:/Applications/FreeCAD.app/Contents/Resources/lib/python3.11/site-packages:$PYTHONPATH" pytest --tb=short -v
```

If you have already exported `PYTHONPATH` in your shell session, you can omit the `PYTHONPATH=` prefix:

```bash
QT_QPA_PLATFORM=offscreen pytest --tb=short -v
```

## 8. Troubleshooting

### `ImportError: cannot import name 'QApplication' from 'PySide6'`
- You have installed PySide6 via pip. Uninstall it: `pip uninstall PySide6`.
- Ensure `PYTHONPATH` points to FreeCAD’s bundled PySide6.

### `ModuleNotFoundError: No module named 'FreeCAD'`
- `PYTHONPATH` is missing FreeCAD’s library path. Verify the export command above.

### Tests hang or open a GUI window
- Set `QT_QPA_PLATFORM=offscreen` before running pytest.

### Symlink not working
- Ensure the symlink points to the `neurocad/` subdirectory (the mod root), not the repository root.
- FreeCAD may cache workbenches; restart FreeCAD completely.

## 9. Next steps

- Read `doc/ARCH.md` for high‑level architecture.
- See `SPRINT_1.md` for the current sprint goals.
- For contributions, follow the coding style outlined in `.roo/rules/10-coding-style.md`.

## License

NeuroCad is MIT licensed. See `LICENSE` file for details.