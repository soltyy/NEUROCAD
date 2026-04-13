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

*These notes are intended for developers, QA, and deployment teams. For end‑user documentation, see the updated `README.md` and `DEV_SETUP.md`.*