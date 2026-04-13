# Release Notes – Sprint 5.4 (LLM Integration, Auth UX, Multi‑Step Execution, Audit Logging)

**Date:** 2026-04-12  
**Based on:** Sprint 5.4 completion (reviewed)

---

## PR Summary
Sprint 5.4 finalizes the LLM integration, authentication UX, multi‑step execution, and audit logging features. The changes formalize API key precedence, redesign the Settings dialog, add panel‑side adapter diagnostics, implement sequential execution of multiple Python code blocks, and introduce structured audit logging with redaction and rotation.

## User‑visible changes
- **API key precedence contract**: session key → environment variable → keyring → clear error.
- **SettingsDialog UX redesigned**: provider/model/base‑url/timeout/object‑limit fields, keyring‑availability warnings, explicit “Save” vs “Use once” paths.
- **Panel‑side adapter diagnostics**: status bar shows user‑friendly messages for missing key, missing keyring, unknown provider, etc.
- **Multi‑step LLM Python response execution**: agent extracts and executes multiple fenced code blocks sequentially, stopping on the first block‑level error.
- **Structured audit logging**: JSONL sink with redaction, preview caps, rotation (5×5 MiB), toggle via `audit_log_enabled` config key.
- **Configurable object limit**: `max_created_objects` default raised from 5 to 1000; adjustable via Settings.

## Migration / rollout notes
- No breaking changes to existing API contracts.
- Existing keyring‑stored keys continue to work; environment variables take precedence over keyring.
- The `max_created_objects` config key now defaults to 1000 (previously hard‑coded 5); adjust if needed.
- Audit logging is disabled by default (`audit_log_enabled = false`). Enable via config file or Settings UI.

## Rollback notes
No special rollback needed beyond reverting the code changes. If you have changed the `max_created_objects` config value, revert to previous value.

## Manual verification checklist
- [ ] Open FreeCAD, activate NeuroCad workbench, open Settings.
- [ ] Verify that “Save” stores a key in system keyring (if keyring installed) and “Use once” creates a temporary adapter without writing to keyring.
- [ ] Submit a simple prompt (`create a 10 mm cube`) and confirm geometry appears.
- [ ] Submit a prompt that intentionally contains multiple Python blocks (e.g., two separate `Part.makeBox` calls in distinct fenced code blocks) and verify both are executed.
- [ ] Check the audit log file (`<UserAppData>/neurocad/logs/llm-audit.jsonl`) after enabling `audit_log_enabled` in config; confirm entries are written and contain no plain‑text API keys.
- [ ] Simulate missing keyring (uninstall keyring package) and verify Settings UI shows appropriate warning and “Use once” still works.

---

# Release Notes – Sprint 5.5 (Math Namespace, Geometry Context, Placement Grounding)

**Date:** 2026‑04‑13  
**Based on:** Sprint 5.5 completion (reviewed)

---

## PR Summary
Sprint 5.5 injects the `math` module into the execution namespace, enriches document snapshot with geometric dimensions, adds FreeCAD placement conventions to the system prompt, and improves error categorization for missing attributes. These changes eliminate three systematic failure classes observed in real dog‑food sessions: missing trigonometry, lack of dimensional context, and misinterpretation of Box.Placement.

## User‑visible changes
- **Math module pre‑loaded**: LLM can use `math.cos()`, `math.sin()`, `math.pi` etc. directly; no need for `import math` (which remains blocked).
- **Geometric properties in context**: The active‑document snapshot now includes object‑specific dimensions (`Length`, `Width`, `Height`, `Radius`, `Radius1`, `Radius2`, `Angle`, `Pitch`) when available.
- **Placement conventions clarified**: System prompt explains that `Part::Box.Placement` sets the corner (not the center) of the box, while `Cylinder`/`Cone` placement sets the center of the base circle.
- **Better error feedback**: Missing‑attribute errors on `FreeCAD`, `App`, `Part`, `Mesh`, `Draft`, `Sketcher`, `PartDesign` modules are categorized as `unsupported_api` and receive targeted hints (e.g., “use `math.cos()` instead of `App.cos()`”).

## Migration / rollout notes
- No breaking changes; the `properties` field added to `ObjectInfo` is additive.
- Existing prompts that already use `math` functions will now work without modification.
- No new environment variables or configuration keys are required.
- **None**

## Rollback notes
No special rollback needed. If a revert is required, revert the five changed files (`neurocad/core/executor.py`, `neurocad/config/defaults.py`, `neurocad/core/agent.py`, `neurocad/core/context.py`, `neurocad/core/prompt.py`).

## Manual verification checklist
- [ ] Open FreeCAD, activate NeuroCad workbench, open the chat panel.
- [ ] Submit a prompt that uses trigonometry: `create a gear‑like pattern of 10 cylinders around a central cylinder` – verify that the geometry appears without `module 'FreeCAD' has no attribute 'cos'` errors.
- [ ] Create a Box (`Part.makeBox(50, 50, 50)`) and a Cone (`Part.makeCone(10, 5, 20)`) with explicit placements; verify the prompt’s placement‑convention hints match the actual FreeCAD behavior.
- [ ] Use the “Show Snapshot” button; check that the printed snapshot includes geometric properties (e.g., `props=Length=50.0 Width=50.0 Height=50.0`).
- [ ] Submit an unsupported request that triggers a missing‑attribute error (e.g., `App.cos(0)`); verify that the error is classified as `unsupported_api` and the feedback suggests using `math.cos()`.

---

*These notes are intended for developers, QA, and deployment teams. For end‑user documentation, see the updated `README.md` and `DEV_SETUP.md`.*