# NeuroCad Development Setup

## Prerequisites

- Python 3.11 (matches FreeCAD 1.0+ bundle)
- FreeCAD 1.0.2 (macOS arm64) or later
- Git

## 1. Clone the repository

```bash
git clone https://github.com/neurocad/neurocad.git
cd neurocad
```

## 2. Create and activate virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
# On Windows: .venv\Scripts\activate
```

Verify activation:

```bash
which python   # should point to .venv/bin/python
python --version  # Python 3.11.x
```

## 3. Install NeuroCad in editable mode with dev dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- `pydantic>=2.7`
- `keyring>=25.0`
- dev tools: `pytest`, `pytest-qt`, `ruff`, `mypy`

## 4. Set up FreeCAD Python path (macOS arm64)

FreeCAD bundles its own Python and Qt libraries. To import FreeCAD modules outside the FreeCAD GUI, add the bundle’s library path to `PYTHONPATH`:

```bash
export PYTHONPATH="/Applications/FreeCAD.app/Contents/Resources/lib:$PYTHONPATH"
```

**Note:** PySide6 is taken from the FreeCAD bundle; do not install it via pip.

## 5. Link the mod for FreeCAD (macOS)

Do not hardcode the mod directory to the legacy unversioned path.
FreeCAD 1.1 may use a versioned user data directory such as
`~/Library/Application Support/FreeCAD/v1-1/`.

The reliable rule is: install the mod under `FreeCAD.ConfigGet("UserAppData")/Mod/`.

Typical paths:
- FreeCAD 1.0.x: `~/Library/Application Support/FreeCAD/Mod/`
- FreeCAD 1.1.x: `~/Library/Application Support/FreeCAD/v1-1/Mod/`

If you already know your FreeCAD user data directory, create a symlink there:

```bash
mkdir -p "$HOME/Library/Application Support/FreeCAD/v1-1/Mod"
ln -sf "$(pwd)/neurocad" "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/neurocad"
```

If `NeuroCad` does not appear in the workbench dropdown, check the actual path from the
FreeCAD Python console:

```python
import FreeCAD
print(FreeCAD.ConfigGet("UserAppData"))
```

Then link `$(pwd)/neurocad` into `<UserAppData>/Mod/neurocad`.

On Linux, the user dir may also be versioned; use the same `UserAppData` rule instead of
guessing the path.

## 6. Running tests

Activate the virtual environment first, then run:

```bash
ruff check .      # linting
mypy .           # type checking
pytest --tb=short -v   # unit tests
```

For tests that need a QApplication (UI), `pytest-qt` provides a `qapp` fixture.

## 7. Running the workbench

1. Launch FreeCAD (`open /Applications/FreeCAD.app` or start from command line).
2. Switch to the **NeuroCad** workbench (should appear in the workbench dropdown).
3. The NeuroCad panel will appear as a dock widget on the right side (lazy‑initialized when the workbench is activated).
4. Sprint 1 only provides the workbench, dock panel, and snapshot/debug path. Geometry
   generation and model execution are Sprint 2 functionality.

## 8. Development workflow

- All UI imports must go through `neurocad.ui.compat.py` (PySide2/PySide6 shim).
- Never call `addDockWidget` inside `Initialize()`; use `get_panel_dock()` singleton.
- Use `get_active_document()` (GUI‑aligned) instead of raw `FreeCAD.ActiveDocument`.
- Config path is determined by `_get_config_dir()` with fallback (FreeCAD.ConfigGet, XDG, legacy).
- Transaction name is always `"NeuroCad"`.

## 9. Troubleshooting

**`ModuleNotFoundError: No module named 'FreeCAD'`**  
Ensure `PYTHONPATH` includes the FreeCAD bundle library path.

**`ImportError: cannot import name 'QtWidgets' from 'PySide6'`**  
FreeCAD’s bundled PySide may be PySide2. The `compat.py` shim handles this automatically.

**Dock widget not appearing**  
Check that `get_panel_dock()` is called in `Activated()` (not `Initialize()`).
Verify that the symlink points to `<FreeCAD.ConfigGet("UserAppData")>/Mod/neurocad`.
On FreeCAD 1.1 this is often `~/Library/Application Support/FreeCAD/v1-1/Mod/neurocad`,
not the legacy unversioned path.

**Tests fail with `QApplication` errors**  
Run tests with `QT_QPA_PLATFORM=offscreen pytest ...` or ensure a virtual display is available.

---

*Last updated: 2026-04-08*
