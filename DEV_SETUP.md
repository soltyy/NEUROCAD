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

## 5.1 Workbench bootstrap verification

- The workbench entry point is `neurocad/InitGui.py`. A root-level `InitGui.py` is also provided as a safety net but is not required if the mod symlink points to the `neurocad` subdirectory. The root-level file is a simple redirect that will raise any import errors immediately, preventing silent workbench disappearance.
- Icons are located in `neurocad/resources/icons/`. The workbench icon path is `resources/icons/neurocad.svg`. If the icon fails to load, FreeCAD will show a placeholder icon; the workbench will still appear.
- To verify that the workbench loads correctly, open FreeCAD and check that **NeuroCad** appears in the workbench dropdown. If it's missing, verify the symlink target and ensure `neurocad/InitGui.py` is present.

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
4. The NeuroCad workbench now includes full LLM‑powered geometry generation, multi‑step execution, secure key management, and audit logging. For a detailed list of features, see the sprint plans in `doc/SPRINT_PLANS.md`.

## 8. Configuration

NeuroCad stores its configuration in a JSON file located at `<FreeCAD user data>/neurocad/config.json`. The configuration can be edited manually or via the Settings dialog inside FreeCAD.

### Key configuration keys

- `provider` – LLM provider (`"openai"` or `"anthropic"`).
- `model` – model identifier (e.g., `"gpt-4o-mini"`, `"claude-3-haiku-20240307"`).
- `base_url` – optional base URL for OpenAI‑compatible endpoints.
- **`timeout`** – LLM request timeout in seconds (default: `180.0`).
- `max_created_objects` – maximum number of geometry objects that can be created in a single request (default: `1000`).
- `audit_log_enabled` – whether to write audit logs (default: `true`).
- `snapshot_max_chars` – maximum number of characters sent in the document snapshot (default: `1500`).

### Changing the timeout

The timeout can be adjusted in two ways:

1. **Via the Settings UI** – open the NeuroCad workbench, click the settings icon, and modify the “LLM timeout (s)” field.
2. **Via the config file** – edit `config.json` and set the `"timeout"` value (floating‑point number).

Example `config.json`:
```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "timeout": 240.0,
  "max_created_objects": 1000,
  "audit_log_enabled": true,
  "snapshot_max_chars": 1500
}
```

### Default values

If a key is missing from the config file, the following defaults are used (defined in `neurocad/config/config.py` and `neurocad/config/defaults.py`):

- `DEFAULT_TIMEOUT` = 180.0
- `DEFAULT_SNAPSHOT_MAX_CHARS` = 1500
- `DEFAULT_MAX_CREATED_OBJECTS` = 1000
- `DEFAULT_AUDIT_LOG_ENABLED` = true

## 9. Development workflow

- All UI imports must go through `neurocad.ui.compat.py` (PySide2/PySide6 shim).
- Never call `addDockWidget` inside `Initialize()`; use `get_panel_dock()` singleton.
- Use `get_active_document()` (GUI‑aligned) instead of raw `FreeCAD.ActiveDocument`.
- Config path is determined by `_get_config_dir()` with fallback (FreeCAD.ConfigGet, XDG, legacy).
- Transaction name is always `"NeuroCAD"`.

## 10. Troubleshooting

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

*Last updated: 2026-04-14*
