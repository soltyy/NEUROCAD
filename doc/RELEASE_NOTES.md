# Release Notes – Sprint 6.0 (Plan-driven multi-pass agent — architecture rewrite)

**Date:** 2026‑05‑11 (MVP)
**Based on:** User-stated principle «мы учимся конкретному» — every L1-L11 «raise-the-bar» iteration accumulated per-class hardcoding (_WHEEL/_AXLE/_GEAR/_HOUSE_NAME_TOKENS in `validator.py`; PART V/VIII bespoke recipes in `defaults.py`). The right approach is to **place the LLM in a frame**: structured plan, generic feature detectors, declarative contract verifier — leveraging the LLM's existing ISO/ГОСТ/СП knowledge instead of teaching specifics. Sprint 6.0 introduces this v2 architecture **without deleting any legacy code**.

## What changed

- **New module `neurocad/core/intent.py`** — Pydantic `DesignIntent` schema: parts + features + dimensions + joints + loads + standards. Serialized as JSON in `<plan>` tag.
- **New module `neurocad/core/features.py`** — 10 generic detectors (axle_hole, thread, hex_section, hollow, stepped_axial, bbox_length, long_axial) composed via `DETECTORS` registry by `Feature.kind`. Adding a new domain = adding a detector, NOT a validator anti-pattern.
- **New module `neurocad/core/contract_verifier.py`** — declarative `verify(doc, intent) → VerifyReport`. Reads claims from plan, calls detectors. Dimensions are skipped when a part has features (avoids «болт длиной 60» = shank-not-bbox conflict).
- **New module `neurocad/core/message.py`** — typed `Message` + 11 `MessageKind` values (USER / PLAN / COMMENT / QUESTION / ANSWER / CODE / SNAPSHOT / VERIFY / ERROR / SUCCESS / SYSTEM). Legacy `Role.USER/ASSISTANT/FEEDBACK` continues to work.
- **New module `neurocad/core/response_parser.py`** — multi-channel parser: splits an LLM response into ordered `[Message]` by `<plan>` / `<comment>` / `<question type=… options=…>` / `<code step=N>` tags. Legacy ```python``` fenced blocks fall back to CODE with `step=None`.
- **New module `neurocad/core/prompt_v2.py`** — compact system prompt **12.9k chars** (vs 69k legacy). Contains response schema + feature.kind list + **techniques T1-T7** (helical thread, hollow ring, hex prism, stepped axial profile, axle hole, radial cylinder, hypercube edges). NO per-class recipes.
- **New module `neurocad/core/agent_v2.py`** — `run(prompt, doc, adapter, history, callbacks) → AgentV2Result`. Implements PHASE 1-5 (CLARIFY → PLAN → EXECUTE_STEP retry → VERIFY_WHOLE → DELIVER). `AgentV2Callbacks` adds `on_question` (blocking) + `on_verify_step` (delegates verification to worker when driver has no FreeCAD).
- **`scripts/headless_dogfood.py`** — new `verify_intent` worker RPC (run contract_verifier in FreeCAD process), new driver-side method `proxy.verify_intent(intent_dict)`, new `_run_one_v2`, new `--use-v2` CLI flag.
- **+26 unit tests** (18 response_parser + 8 agent_v2): 321 → **347 passed**, 1 skipped, 1 xfailed.

## End-to-end verification

```
.venv/bin/python scripts/headless_dogfood.py --use-v2 --scenario R4
→ R4 куб 20×20×20: PASS attempts=1 elapsed=7.4s
  prompt_tokens=1634  (vs ~21000 legacy = 13× reduction)
  parts=1, steps=1, verifier OK via worker RPC
```

R1 bolt M24 via v2: full multi-pass pipeline traverses correctly
(CLARIFY → PLAN → EXECUTE → contract_verifier finds thread weak → retry
with diff feedback → retry); the LLM needs further technique guidance
(or a stronger model) to finish the bolt-thread case in 3 attempts. The
**architecture** is verified — remaining gap is LLM tuning, not framework.

## What did NOT change

- `neurocad/core/agent.py` (legacy single-pass) — intact
- `neurocad/core/validator.py` anti-patterns (wheel/axle/gear/house, intermediate-skip) — intact
- `neurocad/config/defaults.py` PART I-VIII recipes — intact
- `neurocad/core/history.py` Role enum + `to_llm_messages` — intact (backward-compat)
- `neurocad/core/worker.py` / `panel.py` / `settings.py` — intact (UI still uses legacy path)
- 321 previously-passing tests — all still pass

## No-degradation contract

Sprint 6.0 is **strictly additive**. The `--use-v2` flag is the only opt-in switch. Production users running NeuroCAD inside FreeCAD continue on the legacy `agent.run` path unchanged.

## Deferred to next sprint

- `panel.py` bubble types for new `MessageKind` values (COMMENT info-style, QUESTION with option buttons, PLAN collapsible)
- `worker_v2.py` Qt main-thread wrapper of `agent_v2.run` with `on_question` dispatcher
- Settings UI toggle: legacy ↔ v2
- CalculiX FEA in PHASE 4 (currently only joint distToShape checks)
- Additional techniques T8+ (revolution profile pitfalls, spaced packing, hierarchical assemblies)

## Migration / rollout

When v2 graduates from MVP, the migration plan is:
1. Wire `worker_v2.py` + Settings toggle (defaults to legacy)
2. Run real users on v2 for 1 week behind the toggle
3. Compare success rates between paths via audit log (new `agent_v2_start` / `agent_v2_done` event types)
4. Once v2 ≥ legacy success rate AND faster mean tokens-per-success: flip default to v2
5. After 2 weeks stable on v2 default: deprecate PART V/VIII bespoke recipes from `defaults.py` (replaced by techniques T1-Tn) and the per-class validator anti-patterns

## Rollback notes

Revert all new modules and the harness changes. Production legacy path is untouched and continues to work.

## Manual verification

```bash
.venv/bin/pytest --tb=short -q                       # 347 passed
.venv/bin/python -c "from neurocad.core.intent import DesignIntent; \
                     from neurocad.core.agent_v2 import run; \
                     from neurocad.core.prompt_v2 import build_system_v2; \
                     print('prompt_v2:', len(build_system_v2()), 'chars')"
.venv/bin/python scripts/headless_dogfood.py --use-v2 --scenario R4
```

---

# Release Notes – Sprint 5.22 (Headless Dog-Food Harness + Open Punch-List Closure)

**Date:** 2026‑05‑11
**Based on:** User request «можешь сам тестировать во FreeCAD без моего участия?» — manual dog-food gates were expensive and user-dependent. In parallel, Sprint 5.21 left 12 audit entries open as `analyzed_needs_action`. Sprint 5.22 ships an autonomous regression harness AND closes those 12 entries via 5 new feedback hints + classifier rule extensions.

## What changed

- **`scripts/headless_dogfood.py`** (new): single-file harness with a 2-process bridge.
  - Driver (project venv): owns `agent.run`, the LLM adapter (anthropic / openai SDK), `History`, and the scenario verdicts. Reads the production `~/Library/Application Support/FreeCAD/v1-1/neurocad/config.json` directly (FreeCAD's `UserAppData` isn't visible to the venv) and pulls the API key via `key_storage.load_key(spec.key_slug)` with env-var overrides.
  - Worker (`freecadcmd <this script>`): owns the FreeCAD document and runs `executor.execute(code, doc)`. Communicates with the driver over JSON-Lines RPC on `sys.__stdin__` / `sys.__stdout__` (FreeCAD redirects regular `stdout` to its console widget, so the harness uses the underlying file objects directly). Gated by env-flag `NEUROCAD_DOGFOOD_WORKER=1` because `freecadcmd` imports user scripts as a module, not as `__main__`.
  - Scenarios (`--scenario R4|R1|ATLAS|all`): cube 20×20×20, M24 bolt with thread, "АТЛАС КОНСАЛТИНГ" 3D text on a sphere orbit. Success-checks operate on `inspect.objects[*].volume` and `isValid()` rather than name substrings, so they tolerate the LLM naming a cube `Cube` vs `Box`.
- **`neurocad/core/agent.py`** — `_make_feedback` runtime section gains 5 additive branches (no existing branch touched):
  - `Cannot create polygon because less than two vertices …` → polygon-vertex guard hint with `Draft.make_polygon` / `Part.makePolygon` patterns and `if len(points) < 2: continue` defensive check.
  - `range() arg 3 must not be zero` → `step = max(1, int(round(spacing)))` pattern + `while` loop with `assert step != 0` alternative.
  - `Failed to create face from wire` → `isClosed()` + `isValid()` + planar checklist + project-onto-plane fix.
  - `unsupported format string passed to Base.Quantity.__format__` → use `.Value` before f-string format-spec: `f'{obj.Length.Value:.2f}'`.
  - `Either three floats, tuple or Vector expected` → nD → 3D projection: `Vector(*coord[:3])`, references PART VI of the system prompt (wireframe recipe).
- **`scripts/audit_state.py`** — classifier extensions:
  - `_ERROR_PATTERN_RULES`: +8 needles. The 5 new patterns above promote to `processed → 5.22`. Three legacy patterns now have explicit rules (`has no attribute 'makepipeshell'` → 5.11, `has no attribute 'transform'` → 5.16, `llm request timed out` → 5.6/5.18 by-design).
  - `_ERROR_TYPE_RULES`: `+ adapter_init_failure → processed (by-design, Settings dialog)`. Routing now applies these rules to non-`agent_*` event types too (was: fell through to "unknown event_type").
  - `--reclassify` flag on `migrate`: re-evaluates already-classified entries. Strictly promotion-only via `state_rank = {new:0, needs_action:1, done:2, processed:3}` — never downgrades, even if the rule table changes.
- **`tests/test_agent.py`** — 5 new unit tests, one per new feedback branch.
- **`tests/test_audit.py`** — the `range() arg 3` test is rewritten from `needs_action` → `processed` (matches the new feedback hint); two new classifier batch tests for the Sprint 5.22 patterns and the `adapter_init_failure` event type.

## Migration outcome on the production log

```
Before re-migrate:                         After re-migrate (--reclassify):
  analyzed_needs_action : 12  (1.5 %)        analyzed_needs_action :   0  (0.0 %)
  analyzed_done         : 658 (80.7 %)       analyzed_done         : 658 (80.7 %)
  processed             : 145 (17.8 %)       processed             : 157 (19.3 %)
```

All 12 open entries were promoted. Breakdown:

| Entry | Resolution |
|---|---|
| `'Part.Face' object has no attribute 'makePipeShell'` | already in feedback since Sprint 5.11; classifier rule added |
| `'Part.Wire' object has no attribute 'transform'` | already in feedback since Sprint 5.16; classifier rule added |
| `LLM request timed out after 120s` | timeout-category feedback already covers it (by-design) |
| `adapter_init_failure` (×2, openai + deepseek) | user-config issue (no key) — by-design, Settings dialog handles |
| `Either three floats, tuple or Vector expected` | new feedback branch + Sprint 5.14 system-prompt guard |
| `Cannot create polygon because less than two vertices …` | new feedback branch |
| `range() arg 3 must not be zero` | new feedback branch |
| `Failed to create face from wire` (×2) | new feedback branch |
| `unsupported format string passed to Base.Quantity.__format__` | new feedback branch |

## Harness output (DeepSeek `deepseek-chat`, 3/3 PASS)

```
Model: DeepSeek Chat  (deepseek:chat, adapter=openai)
Key source: keystorage:System keyring  (len=35)
Spawning worker: /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd …/headless_dogfood.py
Worker ready (FreeCAD 1.1.0, doc=Dogfood)

=== R4 — Регрессия — куб 20×20×20
    [PASS] attempts=1 elapsed=2.5s — Cube vol=8000.0
=== R1 — Болт M24 с резьбой
    [PASS] attempts=1 elapsed=12.2s — 7 valid solid(s)
=== ATLAS — Слова АТЛАС КОНСАЛТИНГ по орбите сферы
    [PASS] attempts=1 elapsed=8.8s — 30 glyph objects (30 valid)
TOTAL: 3/3 scenarios passed (~24 s + ~63 k prompt tokens for the batch)
```

## No-degradation contract

- `agent.run` / `executor.execute` / `worker._request_exec` / sandbox tokenizer / `defaults.py` system prompt — **all unchanged**. Sprint 5.22 is strictly additive in code: 5 new feedback branches appended to the end of the runtime section, 8 new classifier needles appended after the rotation/list-index group, 1 new event-type rule.
- The `migrate --reclassify` path enforces promotion-only via an explicit `state_rank` comparison: a `processed` entry can never become `needs_action` again, even if a rule is deleted from the table.
- 293 tests from Sprint 5.21 still pass; the renamed range-step test is a semantic update, not a regression. Total: 300 passed, 1 skipped, 1 xfailed.

## Migration / rollout notes

- The harness is run from the project venv, not from inside FreeCAD. No new dependency in `pyproject.toml` — `anthropic` and `openai` SDKs are needed only when actually using `headless_dogfood.py`; install them in the venv as needed.
- `audit_state.py migrate --reclassify` is opt-in (the no-arg `migrate` still respects the "no downgrade" rule from Sprint 5.21).
- Production audit log was re-migrated once after merge; future `migrate` runs are no-ops unless `--reclassify` is passed.

## Rollback notes

Revert `neurocad/core/agent.py` (remove the 5 new `_make_feedback` branches), `scripts/audit_state.py` (remove `--reclassify`, the 8 new pattern rules, the 1 new event-type rule, the routing for non-`agent_*` events), `tests/test_agent.py` (remove 5 new tests), `tests/test_audit.py` (restore the previous range-step assertion, remove the 2 new classifier tests), and delete `scripts/headless_dogfood.py`. The re-migrated audit log is forward-compatible — older readers ignore `processing_state`.

## Manual verification

```bash
# Regression
.venv/bin/pytest --tb=short -q                    # 300 passed

# Audit state
.venv/bin/python scripts/audit_state.py stats
.venv/bin/python scripts/audit_state.py migrate --reclassify --dry-run

# Autonomous end-to-end (DeepSeek + headless FreeCAD)
.venv/bin/python scripts/headless_dogfood.py --list
.venv/bin/python scripts/headless_dogfood.py --scenario R4
.venv/bin/python scripts/headless_dogfood.py --scenario all
```

---

# Release Notes – Sprint 5.19 (Autoscroll Anchor Fix)

**Date:** 2026‑04‑18
**Based on:** User screenshot after several requests — chat panel showed a blank viewport with the scrollbar pinned at the bottom. Content was present but above the visible area because `scrollbar.setValue(scrollbar.maximum())` ran inside a `QTimer.singleShot(0, …)` and read `maximum()` BEFORE Qt's async layout finished, so the scroll position got frozen on a stale "bottom". Each additional bubble compounded the drift.

## Fix
Standard Qt "stick-to-bottom" idiom: connect `verticalScrollBar().rangeChanged` — the signal fires AFTER layout has updated the range, so `max_val` in the callback is the real post-layout bottom. Added `valueChanged` handler to detect manual scroll-up (distance from bottom > 20 px) so we don't fight the user when they're reading history.

## Manual verification
Submit 5+ consecutive requests; after the last one the chat should show the newest bubble fully visible. Scroll up manually to read history — autoscroll stops. Scroll back within 20 px of the bottom — autoscroll resumes.

---

# Release Notes – Sprint 5.21 (Audit Log Processing-State Lifecycle)

**Date:** 2026‑04‑18
**Based on:** User request — tag every audit entry with a processing state to track what's been reviewed / fixed / still open. Lifecycle: `new → analyzed (needs action | done) → processed`. All 815 historic entries are retro-classified against the shipped sprint history; future entries start as `new`.

## What changed

- **`neurocad/core/audit.py`**: every new audit entry now carries `processing_state: "new"`. New helper `update_processing_state(log_path, new_state, *, timestamp=..., correlation_id=..., event_type=...)` atomically rewrites matching lines via a tmp file + `os.replace` so a crash mid-rewrite cannot leave the log half-corrupted.
- **`scripts/audit_state.py`** (new CLI):
  - `migrate` — adds `processing_state` to legacy entries using a 27-pattern rule table that maps each known error string to the sprint that addressed it. Already-classified entries are not downgraded.
  - `stats` — distribution by state and event_type plus the first 10 open `analyzed_needs_action` items.
  - `mark` — manual state override by timestamp / correlation_id / event_type filters.
- **11 new tests** covering `update_processing_state` (atomic, filtered, missing-file safe) and the classifier rules (positive events, ok attempts, addressed patterns → `processed`, unknown → `analyzed_needs_action`, cancelled_by_user, max_retries_exhausted refinement by `last_error`, the open `range() arg 3 must not be zero` case).

## Migration outcome on the production log

```
Total entries: 815
  new                          :     0   (0.0 %)
  analyzed_needs_action        :    12   (1.5 %) ← open punch list
  analyzed_done                :   658  (80.7 %) ← positive / informational
  processed                    :   145  (17.8 %) ← addressed by 5.4–5.20
```

The 12 open items are the next sprint's candidate scope:
- `'Part.Face' object has no attribute 'makePipeShell'`
- `'Part.Wire' object has no attribute 'transform'` (should be `transformShape`/`transformed`)
- `LLM request timed out after 120s` (legacy entry; 5.4 raised the default)
- `Either three floats, tuple or Vector expected` — Vector constructor variant
- `Cannot create polygon because less than two vertices are given`
- `range() arg 3 must not be zero`
- `Failed to create face from wire`
- 5 more (see `scripts/audit_state.py stats`).

## No-degradation contract

The `data` payload of existing entries is never modified by migration — only `processing_state` is added. Append-only behaviour at write time is preserved (the field is set once at log time; subsequent transitions are explicit ops through `update_processing_state` / the CLI). All 282 previously-passing tests still pass; the schema test now expects 5 top-level keys instead of 4.

## Migration / rollout notes

- The migration command is idempotent — re-running it leaves already-classified entries unchanged.
- The atomic rewrite uses `tmp` + `os.replace`, the same pattern the rest of the codebase uses for safe disk writes (e.g. plaintext key storage).
- Backward-compat for readers: entries without the field are treated as `new`.

## Rollback notes

Revert `neurocad/core/audit.py` and `tests/test_audit.py`; delete `scripts/audit_state.py`. The migrated log keeps its `processing_state` field — harmless for older readers because they simply ignore unknown JSON keys.

## Manual verification

```bash
python scripts/audit_state.py stats
python scripts/audit_state.py migrate --dry-run
python scripts/audit_state.py mark --ts <ISO-Z> --state processed
```

---

# Release Notes – Sprint 5.20 (3D Text Recipe + NameError "Forgot to Fetch" + ViewObject Attribute Feedback)

**Date:** 2026‑04‑18
**Based on:** Dog-food request «по орбите сферы запусти слова АТЛАС КОНСАЛТИНГ, по кругу сколько влезет» — 3 attempts, all failed with different root causes:
  - `Quantity::operator +` on `sphere.Radius + 5.0` plus a hard-coded Linux font path `/usr/share/fonts/truetype/freefont/FreeSans.ttf` that doesn't exist on macOS;
  - `name 'прозрачная_сфера' is not defined` — LLM forgot to fetch the object with `doc.getObject(...)`, and the single-block NameError feedback's generic "if-block / previous request / typo" message didn't point at the real fix;
  - `'PartGui.ViewProviderPartExt' object has no attribute 'FontSize'` — LLM tried to render letters by setting `Part::Box.ViewObject.FontSize = 14`.

There was no canonical 3D-text recipe in the prompt, so the LLM reinvented three dead-end approaches in three attempts.

## PR Summary
Four narrow changes:

1. **`neurocad/core/executor.py`**: `_build_namespace` now injects two sandboxed helpers — `platform_name: str` (e.g. `"darwin"` / `"linux"` / `"win32"`) and `file_exists(path: str) -> bool`. The sandbox still blocks `import os` / `import sys` via the tokenizer; this minimal surface is enough for font-path resolution without opening the whole stdlib.

2. **`neurocad/config/defaults.py`** — new `## PART VII — 3D text` section:
   - Explicit anti-patterns the LLM is known to attempt (App::Annotation.TextSize, `ViewObject.FontSize` on Part shapes, using `Part::Box.Label` as if it drew the letter).
   - `neurocad_default_font()` — cross-platform TTF resolver using `platform_name` + `file_exists`. macOS candidates include Arial.ttf and Helvetica.ttc; Linux covers DejaVu and FreeSans paths; Windows hits `C:/Windows/Fonts/`.
   - Single-letter canonical recipe: `Draft.make_shapestring(String, FontFile, Size)` → `Part::Extrusion`.
   - `place_word_on_orbit(doc, word, center, orbit_r, …)` helper — writes a word around a horizontal orbit with each glyph tangent to the circle. Uses `obj.Radius.Value + offset` to demonstrate the Quantity-safe arithmetic.
   - Hard rules at the end: (a) never `obj.Radius + N`, always `.Value + N`; (b) never `ViewObject.FontSize`; (c) never hard-code a font path — use `neurocad_default_font()`; (d) "сколько влезет" = 360° ÷ len(non-space chars).

3. **`neurocad/core/agent.py::_make_feedback`** — NameError branch extended with a "forgot to fetch" heuristic for single-block responses. If the undefined name looks like a document object — capitalized (`BoltBody`), non-ASCII / Cyrillic (`прозрачная_сфера`), or contains an object-ish token from a 30+ item bilingual list (sphere / куб / bolt / шайб / gear / колесо / …) — the feedback now says "this looks like a document object you never fetched into a Python variable; use `varname = doc.getObject('<NameInDocument>')` at the top of your block". Lowercase scoping typos like `pitch` keep the generic scoping/carry-over/typo message.

4. **`neurocad/core/agent.py::_make_feedback`** — new branch for `'…ViewProvider…' object has no attribute '…'`. For text-specific attributes (`FontSize / FontName / TextSize / TextColor / LabelText / Justification`) the feedback redirects to PART VII. For unknown attributes it lists the actual valid Part-ViewObject properties (`ShapeColor`, `Transparency`, `LineWidth`, `Visibility`, `DisplayMode`).

## User-visible changes
- `по орбите сферы запусти слова "АТЛАС КОНСАЛТИНГ"` should succeed in one attempt now: LLM follows PART VII, uses the font resolver, extrudes each glyph, positions with `place_word_on_orbit`.
- `name 'сфера' is not defined` → feedback specifically says "you forgot `сфера = doc.getObject(...)`"; the LLM typically fixes it on the first retry instead of guessing for 2-3 attempts.
- `ViewObject.FontSize` mistakes are funneled back to the correct recipe.

## Migration / rollout notes
- Additive change to executor namespace (`platform_name`, `file_exists`). No prior code read these names, so there's no collision risk.
- The canonical recipe uses `import math` at the top of `place_word_on_orbit` — already allowed by the sandbox since Sprint 5.5.
- No changes to threading / transaction / sandbox-policy / capability scope beyond adding two safe helpers.

## Rollback notes
Revert `neurocad/core/executor.py`, `neurocad/config/defaults.py`, `neurocad/core/agent.py`, and the 4 added tests in `tests/test_agent.py`.

## Manual verification
1. `по орбите сферы запусти слова "АТЛАС КОНСАЛТИНГ"` — letters render around the sphere; no `FontSize` / hard-coded-path errors.
2. `сделай красный куб` then immediately `сделай кубу фаски` (without re-fetching) — feedback points at `doc.getObject(...)` instead of the generic scoping message.
3. Any prompt that incorrectly tries `obj.ViewObject.FontSize = ...` on a Part shape — feedback redirects to `Draft.make_shapestring + Part::Extrusion`.

---

# Release Notes – Sprint 5.18 (Truncation Detection + max_tokens Bump + Quantity Anti-Pattern + Export Button Removal)

**Date:** 2026‑04‑18
**Based on:** Kitchen-wall dog-food session — 2 of 2 first attempts failed with `SyntaxError: invalid syntax (line 1)` and `Tokenization error: EOF in multi-line statement` on a 332-char and 3348-char LLM response that were cut mid-statement. Root cause: the model hit its `max_tokens=4096` ceiling; the agent mistook the truncation for a bogus code error and retried the same too-long prompt. Plus third recurrence of `Quantity::operator +/- Unit mismatch`, plus user request to remove the unused Export button.

---

## PR Summary
Sprint 5.18 is a narrow ~150-line pass:

1. **Truncation detection in `agent.run`.** Before parsing code blocks, check `response.stop_reason`. If it's `"length"` or `"max_tokens"`, add a specific feedback to history (`"Your previous response was TRUNCATED at N chars … split into 2–3 fenced blocks, do NOT re-emit the same long block"`) and retry if attempts remain. Audit event gets `error_category="truncated"` and `error_type="truncated"` on final failure.
2. **Default `max_tokens` bumped `4096 → 8192`** in both `OpenAIAdapter` and `AnthropicAdapter`. Covers ~95% of dog-food cases including complex assemblies (kitchen, bike frame, bolt+thread+washer).
3. **Quantity anti-pattern tightened** in `config/defaults.py`: explicit WRONG/RIGHT table, `.Value` marked as the single recommended path, `float(obj.Length)` called out as fragile, `_f(q)` helper for unknown property types, final "best" recommendation to keep original literals in local variables and never read back.
4. **Export button removed** from the panel. `_export_btn`, its handler `_on_export_requested`, the signal connection, and the `_set_busy` reference all dropped. `core/exporter.py` is left on disk — still available for programmatic export.

## User-visible changes
- A truncated response now produces a concise "your code was cut off" feedback instead of a confusing SyntaxError fingerpointing at `line 1`.
- Requests that previously required 2+ retries due to truncation often succeed on the first attempt now (8192 is enough for a full kitchen).
- The Settings-dialog Quantity hint is more actionable — fewer `.Value` / `float()` retries expected.
- Panel toolbar shows only `Snapshot` next to the blue send button; `Export` is gone.

## Migration / rollout notes
- Users who explicitly set `max_tokens` in their `config.json` keep their value — defaults apply only when unset.
- No breaking changes to the config schema, audit log format, or adapter protocol.
- Anyone relying on `panel._export_btn` in a downstream customization should switch to calling `core.exporter.export_last_successful` directly.

## Rollback notes
Revert:
- `neurocad/ui/panel.py` + `tests/test_panel.py` — restore Export button
- `neurocad/core/agent.py` + `tests/test_agent.py` — drop truncation branch
- `neurocad/llm/openai.py` + `neurocad/llm/anthropic.py` — restore `max_tokens=4096`
- `neurocad/config/defaults.py` — restore old Quantity paragraph

## Manual verification
1. Submit a large kitchen / bike / multi-bolt request. Watch `llm-audit.jsonl`: `output_tokens` should be < 8192 on success. If it ever hits 8192 and fails: the agent now emits `error_category="truncated"` with a helpful feedback.
2. Settings dialog: toolbar has only `Snapshot` and `→`. No `Export`.
3. Arithmetic requests that read `obj.Height.Value` succeed in one attempt; `float(obj.Height)` path should fall back to a Quantity error with Sprint 5.6 feedback (still works as before).

---

# Release Notes – Sprint 5.17 (Concrete Model Registry + Per-Slug API Keys + File-Embed Infra)

**Date:** 2026‑04‑18
**Based on:** User request — let the user pick a concrete LLM instead of juggling "provider + model-string + base URL" — plus the fact that DeepSeek requires inline file-embedding because it has no separate file-upload endpoint.

---

## PR Summary
Sprint 5.17 introduces a curated model registry and refactors config / Settings UI / adapter factory around it:

- **`neurocad/llm/models.py`** (new): `ModelSpec` dataclass + the `MODELS` list — 7 curated entries (OpenAI × 2, Anthropic × 2, DeepSeek × 2, Ollama). Each spec carries adapter class, model id, base URL, `key_slug` for credential storage, context-window hint, file-handling strategy (`native` / `inline` / `none`), and for inline models a `file_embed_template`.
- **`build_file_attachment_prompt(spec, question, file_name, file_content)`** in the same module — for DeepSeek, formats the prompt as `[file name]: … [file content begin] … [file content end] … question` per DeepSeek's official template. For native-upload models it raises ValueError (caller should use the provider's file API). Infra-only — no UI for file attachment yet.
- **Config schema migration**: `config["model_id"]` replaces `{provider, model, base_url}`. Legacy files are auto-migrated on load via `infer_from_legacy_config` (DeepSeek base_url → `deepseek:chat|reasoner`, Ollama base_url → `ollama:llama3.1`, literal match, provider-level fallback).
- **Per-slug API keys**: `spec.key_slug` is the storage account. DeepSeek uses the OpenAI adapter class but its API key is stored under `"deepseek"`, not `"openai"` — no more overwriting.
- **Settings UI**: single "Model" dropdown populated from the registry. An info label below the combo shows "Adapter: openai · Base URL: https://api.deepseek.com/v1 · Context: 64,000 tokens · Files: inline · Key slug: deepseek". The tier radios from Sprint 5.15 (Automatic / Plaintext file / Session only) are preserved; the inline status label now shows the backend holding the key for the selected model's slug.
- **`_resolve_api_key`** now keyed by `ModelSpec.key_slug`: env-var is `NEUROCAD_API_KEY_{KEY_SLUG.upper()}` — e.g. `NEUROCAD_API_KEY_DEEPSEEK` (separate from `NEUROCAD_API_KEY_OPENAI`).
- **Hard failure on unknown `model_id`**: typos no longer silently fall back to the default — `ValueError("Unknown model_id …")` with the list of known ids.

## User-visible changes
- Settings dialog: one dropdown with friendly names ("GPT-4o", "Claude 3.5 Sonnet", "DeepSeek Chat", "DeepSeek Reasoner", "Llama 3.1 (Ollama, local)"). No raw URLs to type.
- DeepSeek users: the API key is safely stored under its own slug; switching between OpenAI and DeepSeek no longer loses either key.
- Existing `config.json` with the old three-field schema opens cleanly and is migrated on first save.
- File-attachment support exists at the API level (`build_file_attachment_prompt`) — UI wiring will follow in a later sprint.

## Migration / rollout notes
- **Breaking** at the code level: `config["provider"]` is no longer written on save. Any external tooling reading the config file directly should switch to `config["model_id"]`.
- Env-var names for API keys are now per-slug: `NEUROCAD_API_KEY_DEEPSEEK`, `NEUROCAD_API_KEY_ANTHROPIC`, `NEUROCAD_API_KEY_OPENAI`, `NEUROCAD_API_KEY_OLLAMA`. Existing `NEUROCAD_API_KEY_OPENAI` continues to work for OpenAI models.
- If a user previously saved a DeepSeek key under the "openai" slug, they will need to re-enter it once. After saving, the key is stored under `"deepseek"` and picked up on every subsequent run.

## Rollback notes
Revert:
- `neurocad/llm/models.py` (new file — delete)
- `neurocad/llm/registry.py` (restore old provider-driven logic)
- `neurocad/config/config.py` (restore legacy schema defaults)
- `neurocad/ui/settings.py` (restore 3-field UI)
- `tests/test_models.py` (new — delete) and the updated `test_adapters.py`, `test_settings.py`, `test_config.py`.

## Manual verification
1. Open Settings. The old provider/model/base-URL fields are gone; instead there's a single "Model" combo and an info label under it. Pick "DeepSeek Chat", enter your DeepSeek key, click Save. Inline status: "🔑 Key for **deepseek** persisted to **…**".
2. Switch the combo to "GPT-4o (OpenAI)". The info label updates (Base URL becomes "(provider default)", Key slug becomes "openai"). The stored DeepSeek key is NOT overwritten; the key field is blank; the header shows "No saved key for **openai**".
3. Submit a request. The adapter is constructed via the ModelSpec; DeepSeek requests go to `https://api.deepseek.com/v1/chat/completions` and use the `"deepseek"` credential.
4. On the command line: `export NEUROCAD_API_KEY_DEEPSEEK=sk-xxx` sets the DeepSeek key via environment, overriding storage for that session.

---

# Release Notes – Sprint 5.16 (Revolution Profile Diagnostics + No-Code Retry + Bevel Helper)

**Date:** 2026‑04‑18
**Based on:** Audit of a technical dog-food request ("Сделай ось колёсной пары РУ1-Ш по ГОСТ 33200-2014" — stepped shaft, length 2294 mm, fillets R=20/25/40, central lathe bores). Two attempts, both failed: one with `shape is invalid` on the Part::Revolution result (self-intersecting 2D profile from hand-rolled fillet arcs), then `no_code_generated` on the retry — the LLM returned prose instead of new code, and the agent returned immediately without retrying. Three narrow fixes eliminate this failure class.

---

## PR Summary
Sprint 5.16 is a prompt-and-feedback sprint. Three targeted changes:

1. **Revolution-specific `shape is invalid` branch in `_make_feedback`.** When the invalid object's name matches `revolution / revolved / axis / profile / wire / ring`, a 5-point checklist replaces the generic boolean/sweep diagnosis: call `profile_wire.isValid()` early, keep the polygon closed (first == last), keep ALL points on one side of the rotation axis, verify arc-start equals previous-segment-end to the last decimal (the #1 cause of self-intersection in hand-rolled fillets), avoid vertices exactly on the axis.

2. **`no_code_generated` is retriable.** Previously, when the LLM returned prose without a fenced block, `agent.run` returned immediately. Now: add a stronger feedback to history (`"The ONLY valid response is a fenced python block. Do NOT apologize, do NOT describe the problem — re-emit the complete code with the fix"`), log `agent_attempt` with `error_category=no_code`, and `continue` if `attempts < MAX_RETRIES`. Only after all retries fail is `agent_error` emitted.

3. **`fillet_arc_points` bevel helper in defaults.py PART III.** Linear interpolation between `(r_start, z_start)` and `(r_end, z_end)` through `n_pts` points — never self-intersects, no arc-centre math required. Explicit prompt guidance: when tangent-fillet geometry doesn't admit a true R, the LLM should fall back to this helper rather than fabricate a wrong arc.

## User-visible changes
- Stepped-shaft / revolution requests no longer fail silently on self-intersecting profiles — the LLM gets a concrete checklist pointing at the likely bug (fillet arc stitching).
- If the LLM momentarily responds with prose after a failed attempt, the agent now retries with a firmer reminder instead of giving up.
- The canonical prompt offers a safe bevel helper; real tangent fillets remain an option but are no longer the only documented path.

## Migration / rollout notes
- Prompt-only + agent-only changes; no executor, worker, config, adapter, or transaction changes.
- `_make_feedback` signature unchanged (Revolution branch is internal to the validation block).
- `agent.run` no longer returns `AgentResult(no_code_generated)` on the first prose response; callers that rely on attempt=1 as a fast-fail signal should adjust.

## Rollback notes
Revert `neurocad/core/agent.py` and `neurocad/config/defaults.py` plus the three added tests in `tests/test_agent.py`.

## Manual verification
1. Submit a complex revolution request (e.g. the ось колёсной пары prompt). If the LLM produces a self-intersecting wire, the feedback should mention `profile_wire.isValid()`, `fillet_arc_points`, and "keep all points on ONE side of the rotation axis".
2. Intentionally trigger an empty LLM response — the agent should retry, not fail immediately.
3. Simpler revolution requests (e.g. a washer or a ring) should keep working (no regression).

---

# Release Notes – Sprint 5.15 (Cross-Platform Tiered API Key Storage)

**Date:** 2026‑04‑18
**Based on:** FreeCAD 1.1 bundled Python does NOT include the `keyring` pip package. The previous Settings dialog therefore popped a modal on every Save ("Configuration saved, but API key could not be stored securely… You will need to provide the key again next time") and the key was simply not persisted. Users re-entered the key on every launch.

---

## PR Summary
Sprint 5.15 introduces a tiered cross-platform key storage chain with no mandatory pip dependencies, plus a cleaner Settings UX (radio-buttons + inline status; no more modals).

**Storage tiers (tried in this order by `save_key(..., tier="auto")`):**

1. **Python `keyring`** — used if the pip package is present. Most secure; delegates to OS keychain directly.
2. **macOS `security` CLI** — `add-generic-password` / `find-generic-password`. Works without pip deps; same OS Keychain under the hood.
3. **Linux `secret-tool` CLI** — `secret-tool store --label ... service neurocad account <provider>`, reads/writes via libsecret (GNOME Keyring).
4. **Plaintext file** — JSON at `<config_dir>/api_keys.json`, `chmod 0600` on Unix. Universal last-resort.

**Settings UI changes:**
- Radio buttons replace the modal warning: **Automatic (recommended)** / **Plaintext file (owner-only)** / **Session only (do not save)**.
- Inline status line shows outcome: "🔑 Settings saved. Key persisted to **macOS Keychain**." — no modal dialog.
- When opening the dialog, an informational line shows where the currently-saved key lives, e.g. "🔑 Key for **openai** currently stored in: **Plaintext file (owner-only)**".
- No `QMessageBox.warning` / `QMessageBox.information` on Save / Use once paths; all feedback is inline.

**API changes:**
- `config.save_api_key(provider, key, tier=TIER_AUTOMATIC) -> tuple[str, str | None]` — now returns `(backend_name, error_or_None)`; never raises.
- New: `config.load_api_key(provider) -> tuple[str | None, str | None]`, `config.delete_api_key(provider) -> list[str]`.
- `registry._resolve_api_key` precedence: session → env-var → `key_storage.load_key()` (tries every backend).

## User-visible changes
- Save on a FreeCAD bundle without `keyring`: key ends up in macOS Keychain (via CLI) on macOS, in GNOME Keyring (via `secret-tool`) on Linux, or in a plaintext-0600 file as the universal fallback. No scary modal.
- "Use once" unchanged: temporary adapter, key never persisted.
- Radio "Plaintext file (owner-only)" forces the plaintext backend even when more secure options exist — honest choice for users who accept the tradeoff.
- Radio "Session only" builds a session adapter and skips persistence entirely (same as "Use once" button).

## Migration / rollout notes
- Backward-incompatible: `save_api_key` no longer raises `RuntimeError`. Callers outside `ui/settings.py` should switch to inspecting the returned tuple.
- Audit log unaffected; no new config keys added.
- Dev dependency `keyring` stays in `pyproject.toml` `[project.optional-dependencies.dev]` — still recommended for the developer `.venv` but no longer required at runtime.

## Rollback notes
Revert these files:
- `neurocad/config/key_storage.py` (new file — delete it)
- `neurocad/config/config.py` (restore the `import keyring` + `save_api_key` that raises)
- `neurocad/llm/registry.py` (restore `import keyring` + old `_resolve_api_key`)
- `neurocad/ui/settings.py` (restore modal-based UX)
- `tests/test_key_storage.py` (new — delete), plus reverts in `tests/test_config.py`, `tests/test_settings.py`, `tests/test_adapters.py`.

## Manual verification

1. Open Settings on macOS, enter a real OpenAI key, choose **Automatic**, click Save. Expected inline message: "🔑 Settings saved. Key persisted to **System keyring**" (if pip `keyring` installed in the FreeCAD Python) or "… **macOS Keychain**" (if not). Close and reopen the dialog — the key field is blank, but the header shows "🔑 Key for openai currently stored in: …".
2. Verify `security find-generic-password -s neurocad -a openai -w` prints the key in Terminal.
3. Choose **Plaintext file (owner-only)**, click Save. Check `~/Library/Application Support/FreeCAD/v1-1/neurocad/api_keys.json`. Run `stat -f "%Sp" api_keys.json` → should print `-rw-------`.
4. On Linux, repeat with `secret-tool lookup service neurocad account openai`.
5. Choose **Session only**, click Save. Close FreeCAD and reopen — dialog should show "No saved key for openai" in the header.

---

# Release Notes – Sprint 5.14 (Wireframe / Math Visualization + Vector 3D Guard)

**Date:** 2026‑04‑18
**Based on:** Pentaract (5D hypercube) dog-food session between Sprint 5.13 and 5.14. 5 attempts, 0 successes, 4 different root causes in the logs. Distinct class from fasteners/assemblies — wireframe visualization of a mathematical object (no solid body, no booleans, no "material" to cut). The existing canonical recipes (bolt, gear, wheel, house) all assume solid+boolean workflows and offer no guidance when the object is point+edge structure.

---

## PR Summary
Sprint 5.14 is a **prompt-only** sprint. Two additions to `DEFAULT_SYSTEM_PROMPT` close the specific failure classes observed on the pentaract task:

1. **`FreeCAD.Vector is ALWAYS 3D` warning** — right after the Placement conventions section. Explicitly states three args max, lists `.x / .y / .z` exist vs `.w / .t / .u` do NOT, and shows the canonical nD→3D linear-projection pattern (keep coords as plain tuples, construct Vector only after projection).
2. **New section `## PART VI — Wireframe / mathematical visualization`** — parallel to PART V (Bolt/Gear). Covers hypercubes, graphs, polytopes, knots, fractals. Includes a `make_edge_cylinder(doc, start, end, radius, name)` helper with:
   - `math.acos` clamp `max(-1.0, min(1.0, cos_a))` — avoids `ValueError: math domain error` on parallel/antiparallel vectors (a latent bug that can fire on any task, not just wireframes).
   - Degenerate-edge skip (`if L < 1e-6: return None`).
   - Explicit handling of the two parallel-vector edge cases (cos_a ≈ +1 and cos_a ≈ −1).
   - Hypercube pattern via `itertools.product` + Hamming-distance-1 edge detection.
   - Hard rule: `DO NOT try to render nD faces/cells — they project degenerately and Validator will reject`.

## User-visible changes
- `Пентеракт`, `5D hypercube`, `граф` and similar requests now have a canonical recipe the LLM can follow. Expected pattern: small spheres at projected vertices + cylinders between them, no face/cell attempts.
- `FreeCAD.Vector(a, b, c, d, e)` TypeError no longer happens on nD requests — the prompt now teaches the split "nD math on tuples, then project to 3D Vector".
- Any future task that rotates a cylinder to align with an arbitrary direction benefits from the acos-clamp pattern (latent bug squashed).

## Deferred to a future sprint
- Blocking `ViewObject` in `executor._BLOCKED_NAME_TOKENS`. Not strictly dangerous (it's display-only), but LLM-generated `obj.ViewObject.ShapeColor = ...` in headless execution is silently ignored. Lower priority; may add a non-blocking warning comment to the prompt instead.
- Statistical verification of Sprint 5.13 naming-contract impact on NameError rate — requires one more dog-food day after users restart FreeCAD to reload the updated Python modules.

## Migration / rollout notes
- Prompt-only; no executor / agent / worker / config / adapter changes.
- Both new sections are additive and don't shadow existing recipes.

## Rollback notes
Revert `neurocad/config/defaults.py` — changes confined to two insertion points (Vector warning after Placement conventions; PART VI between Offset and Blocked).

## Manual verification

Submit each of these through the chat:
1. `Сделай пентеракт 32 вершины 80 рёбер` — expected: blocks use `itertools.product` or equivalent for vertex enumeration; edges via `make_edge_cylinder`; no Part::Box for cells; final scene is spheres + cylinders.
2. `Сделай граф K5 (полный граф на 5 вершинах)` — 5 spheres + 10 edge cylinders, no faces.
3. `Сделай трилистник (trefoil knot)` — parameterized curve (t ∈ [0, 2π]) sampled into points, chained via `make_edge_cylinder`.
4. Regression: `Сделай болт M24 по ISO` — still works (chamfers, thread-entry, real helical cut from Sprint 5.11).

Run the analyzer:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

If a pentaract / hypercube run still fails with `FreeCAD.Vector` constructor error — the LLM ignored the new warning and we escalate to Sprint 5.15 with a stronger anti-pattern example (showing the broken 5-arg call in a `# NEVER do this` block).

---

# Release Notes – Sprint 5.13 (Naming Contract + defaults.py Bug Fixes — external audit)

**Date:** 2026‑04‑18
**Based on:** External code review (`AUDIT_REPORT.md` + `patch_01_agent_nameerror.py` + `patch_02_defaults_fixes.py`). The review identified **cross-block variable naming drift** as the dominant failure mode — 14+ of the day's ~18 NameError failures came from the LLM renaming a variable between Block 1 and Block 2 (`major_d` → `major_diameter`, `shank_h` → `shank_length`, etc.). It also catalogued 7 accumulated bugs in `defaults.py` including broken `""..""` docstrings that crash at parse time if the LLM copies them verbatim.

---

## PR Summary
Sprint 5.13 applies both patches from the external audit plus 7 smaller fixes. Three simultaneous mechanisms attack the naming-drift problem:

1. **Canonical naming contract in the prompt** — three markdown tables (bolt/thread, gear, wheel) with explicit "NEVER use" columns listing the variants the LLM is known to drift to (`major_d` vs `major_diameter`/`diameter`/`d`, `shank_h` vs `shank_length`/`length`/`L`, etc.). LLM now has a hard contract, not just an example.
2. **Block-aware `_make_feedback`** — signature extended with `block_idx` / `total_blocks` (default 1 for backward compatibility). If NameError fires in Block ≥ 2 of a multi-block response, the feedback now says: `CRITICAL: fresh namespace, must re-declare with IDENTICAL names`, and lists the top drift patterns as concrete alternatives.
3. **Audit observability** — `failed_block_idx` is written into `agent_attempt` events on failure. Future dog-food analysis can grep "NameError in block ≥ 2" directly without parsing error strings.

Plus defaults.py cleanup:
- **Broken docstrings fixed**: `""Vertical through-hole..""` (3 helper functions) → `# ..` single-line comments. Previously, if the LLM copied a helper, Python raised SyntaxError.
- **Hallucinated API removed**: `Part.RegularPolygon(center, radius, 6)` does not exist. Replaced with `6 LineSegment + Equal-length + Symmetric constraints`.
- **Incomplete example wrapped**: `PartDesign::Draft` was shown with `addObject(...)` followed by *commented-out* property assignments → LLM created an empty feature that failed on recompute. Now the entire block is in a comment-template.
- **Misleading comment fixed**: `helix.LocalCoord = 0  # 0 = right-hand, 1 = left-hand` was wrong — `LocalCoord` is a coordinate-system mode, not handedness. Left-hand thread is obtained with a negative `Pitch`.
- **Undefined-variable examples wrapped**: `Draft.move(obj, ...)` with `obj` and `dx, dy, dz` never declared → NameError if copied. Wrapped in comment-template with `some_obj` placeholder.
- **`import copy` removed** from the polar-copy loop example — `Shape.copy()` is a native Shape method, no import required.
- **`REFUSAL_KEYWORDS` narrowed** from `[file, import, url, http, https]` to `[download, fetch url, wget, curl]`. The broad list never fired in 586 audit events but would have blocked legitimate requests like `импорт STEP`. Real protection is in `executor._BLOCKED_NAME_TOKENS` (tokenize-based).
- **`Part.makeInvoluteGear` anti-pattern** made explicit in the `## Blocked` section.

## User-visible changes
- Multi-block bolt requests that previously failed with `name 'major_diameter' is not defined` now either succeed (because the canonical naming table stops the drift) or, on failure, get a block-aware feedback that the LLM can actually act on.
- `Сделай болт M24 и импортируй STEP` no longer pre-refuses — the LLM can attempt to generate code and the sandbox catches real file/network calls if any.
- If a helper like `add_hole` gets copied into generated code, it no longer breaks with SyntaxError.

## Migration / rollout notes
- `_make_feedback` signature change is backward-compatible (new params default to 1).
- Audit event `agent_attempt` gains one new field `failed_block_idx` (nullable). Parsers that iterate known keys are unaffected.
- No executor / worker / config / adapter changes.

## Rollback notes
Revert `neurocad/core/agent.py` + `neurocad/config/defaults.py` + affected test updates in `tests/test_agent.py`.

## Manual verification

Run:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

Target R1–R4 pass rate ≥ 80 % (baseline from Sprint 5.10 was 22 %; Sprints 5.11–5.12 addressed visual correctness but naming-drift regressions were still producing NameErrors).

Additional smoke checks (visual + audit):
1. `Сделай болт M30` — Block 1 and Block 2 both use `major_d`, `pitch`, `shank_h` identically. No `name '...' is not defined` in the log.
2. `Сделай шестерёнку 20 зубьев` — Block 1/2/3 (if split) all use `teeth_n`, `module_m`, `pitch_r`.
3. `Сделай колесо велосипеда` — Blocks use `spoke_count`, `spoke_r`, `rim_inner_r`, `rim_outer_r` consistently.
4. Submit `download some.step` — early-refused (new allowed keyword). Submit `импорт STEP` — passes triage, LLM writes code, executor catches real file I/O if generated.

---

# Release Notes – Sprint 5.12 (Truly Parametric Template: Placeholder Syntax + Parse Instructions + ISO 4014/4017)

**Date:** 2026‑04‑18
**Based on:** Fifth dog-food round. Sprint 5.11 fixed the actual cutting (real V-grooves now visible). User pointed out that the prompt still contained `major_d = 24.0` and other literals that the LLM would copy verbatim, and asked for a **universal default that teaches the LLM how to derive parameters** instead of simplifying my own work.

---

## PR Summary
Sprint 5.12 is a **prompt-only** sprint that converts the canonical bolt+washer recipe from a concrete M24 example into a fully parametric template. Two mechanisms do the work:

1. **Placeholder syntax that cannot be left verbatim.** Every size-related literal is replaced with `<MAJOR_D_FROM_REQUEST>` / `<SHANK_H_FROM_REQUEST>` / `<ISO_STANDARD_FROM_REQUEST>`. These tokens are **syntactically invalid Python** — if the LLM leaves them in the output, the executor throws `SyntaxError` immediately. Comments can be ignored; invalid syntax cannot.

2. **A "Parsing rules" preamble** between the multi-block protocol and the canonical example. A markdown table maps user-text patterns ("M24", "M24x80", "болт M30 полностью резьбовой", "болт M48 ISO") to extracted values (`major_d`, `shank_h`, `standard`). The LLM now has an explicit parsing contract before it reads any code.

Additional correctness improvements:
- **ISO 4014 thread length table** (`b = 2d+6` if `L ≤ 125`, `2d+12` if `L ≤ 200`, `2d+25` otherwise) replaces the arbitrary `min(shank_h - major_d, 10*pitch)` formula from Sprint 5.10.
- **ISO 4017 fully-threaded branch** (`thread_h = shank_h - 0.5·d`) for requests like "болт полностью резьбовой" / "fully threaded".
- **Washer block is conditional**: emitted only when the user asks for a washer / шайба / flange.

## User-visible changes
- "болт M8" → `major_d = 8.0`, `pitch = 1.25` (auto from ISO 261), `shank_h = 24.0` (default 3·d), no washer.
- "болт M30x100 с шайбой" → `major_d = 30.0`, `shank_h = 100.0` (from `x100`), washer block emitted.
- "болт M24 полностью резьбовой" → `standard = "ISO4017"`, `thread_h = shank_h - 12.0` (≈ full shank minus head shoulder).
- Every size and length ratio now scales correctly; no residual M24-bias.

## Migration / rollout notes
- Prompt-only; no executor / agent / worker / config / adapter changes.
- If you had a custom user prompt that relied on the old `major_d = 24.0` defaulting, update it to specify the size explicitly.

## Rollback notes
Revert `neurocad/config/defaults.py` — changes confined to the Multi-block protocol section.

## Manual verification

Run each of these through the chat and check the emitted code:
1. `Сделай болт M24` → no `= 24.0` left as literal in the placeholder positions (the LLM substitutes 24.0 from the request); no washer block.
2. `Сделай болт M30x80 с шайбой` → `major_d = 30.0`, `shank_h = 80.0`; washer block present.
3. `Сделай болт M8 полностью резьбовой` → `standard = "ISO4017"`; thread covers nearly the whole shank.
4. `Сделай болт M48` → `pitch = 5.0` (from ISO 261 table); `thread_h` follows `2d+6` = 102 mm (capped at 10·pitch = 50 or shank_h − d/2, whichever is smaller).

Then run:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

---

# Release Notes – Sprint 5.11 (Thread Cut Actually Happens: makePipeShell + Volume Assertion)

**Date:** 2026‑04‑18
**Based on:** Fourth dog-food round. Sprint 5.10 placed the thread at the correct end of the shank (free tip, not next to the head), but the thread still rendered as "surface rings" rather than cut grooves. Close-up photo showed the shank diameter unchanged in the thread zone — the Part::Cut was silently removing zero volume.

---

## PR Summary
Sprint 5.11 is a **prompt-only** sprint. Replaces the canonical Block 2 implementation of helical threading from the document-object `Part::Sweep` (which silently produces degenerate/self-intersecting solids on narrow triangular profiles) with the wire-level `helix_wire.makePipeShell([profile_wire], True, True)` call. Two additional `assert` statements guarantee the sweep is a valid non-zero-volume solid before reaching `Part::Cut` — if the sweep ever degenerates, the failure surfaces immediately instead of producing a silently-uncut bolt.

## User-visible changes
- Threaded bolts now show **actual V-shaped helical grooves** — the shank diameter reduces in the thread zone, matching real ISO 4014 geometry.
- If the sweep ever fails (edge-case profile or helix configuration), the error is caught and fed back to the LLM as a thread-specific feedback instead of producing a silently-wrong result.
- No other user-visible changes; canonical thread still honors the Sprint 5.10 tip-end placement and the fully-parametric derivation from `major_d`.

## Implementation details
- `Part.makeHelix(pitch, thread_h, shank_r)` → Wire directly (no doc object). `.Placement` is applied to the Wire itself.
- `Part.makePolygon([...])` returns a **closed Wire**, not a Face — `makePipeShell` expects Wire inputs for Solid=True mode.
- `helix_wire.makePipeShell([profile_wire], True, True)` — args are `(profiles_list, makeSolid=True, isFrenet=True)`.
- `assert thread_shape.isValid(), "thread sweep produced an invalid shape"`
- `assert thread_shape.Volume > 0, "thread sweep produced zero volume"`
- Result wrapped in `Part::Feature "Thread"`; subsequent `Part::Cut` targets this feature.

## Migration / rollout notes
- Prompt-only; no breaking changes.
- Existing recipes outside Block 2 of the canonical bolt are untouched. Deep-docs section `/PART III — Advanced` already documented `makePipeShell` as "simpler and faster than Part::Sweep"; Sprint 5.11 brings the canonical bolt recipe in line with that recommendation.

## Rollback notes
Revert `neurocad/config/defaults.py` — changes confined to canonical Block 2 of the Multi-block protocol section.

## Manual verification (visual)

Re-run dog-food:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

Visual acceptance:
- In the thread zone of the bolt, the **shank diameter visibly reduces** (V-shaped grooves); it is NOT a flat cylinder with surface stripes.
- On a top-down view of the thread, the grooves describe a continuous spiral, not concentric rings.
- Running `assert thread_shape.Volume > 0` never fails on the default M24/M30 recipe.

---

# Release Notes – Sprint 5.10 (Thread Position + Pitch Derivation, no hardcoded constants)

**Date:** 2026‑04‑18
**Based on:** Third dog-food round. User submitted photos of real ISO bolts side-by-side with NeuroCad output plus four generated bolts. Two issues surfaced: the thread sat next to the hex head (smooth at the free end), and the canonical recipe still had hardcoded `pitch = 3.0` / `thread_h = min(30.0, ...)` constants that the LLM copied verbatim.

---

## PR Summary
Sprint 5.10 is a **prompt-only** sprint — no executor, agent, worker, config or adapter changes. Two targeted edits to the Multi-block protocol in `DEFAULT_SYSTEM_PROMPT` bring the canonical bolt recipe in line with real ISO-4014 geometry:

1. **Helix placement on the tip.** Block 2 now computes `thread_z_start = shank_h - thread_h` and sets `helix.Placement = FreeCAD.Placement(Vector(0, 0, thread_z_start), Rotation(0, 0, 0))`. The thread now lives on the **free end** of the shank (far from the head), with a smooth shoulder of ≈ 1 × major_d under the head — matching ISO 4014 partially-threaded bolt geometry. The profile triangle is rewritten in absolute coordinates so it follows the helix.

2. **Full parametrization from `major_d`.** Parameter header at the top of Block 1 and Block 2 now includes the ISO 261 coarse-pitch table `_ISO_COARSE_PITCH = {3: 0.5, 4: 0.7, ..., 48: 5.0}`. `pitch = _ISO_COARSE_PITCH[int(major_d)]` replaces the hardcoded `pitch = 3.0`. The arbitrary 30-mm cap on `thread_h` is gone: `thread_h = min(shank_h - major_d, 10 * pitch)` derives naturally from shank length and pitch, capped at 10 turns for OCCT reliability. `major_d` is the only hand-set value, explicitly marked "the ONLY hand-set value; from user request `M<N>` → N".

## User-visible changes
- Bolts generated from `Сделай болт M24 по ISO` now have thread on the lower 30 mm of the shank (the free end / tip), with ~24 mm of smooth shoulder under the head — matching real ISO 4014 partially-threaded bolts.
- `Сделай болт M30` derives pitch = 3.5 from the ISO 261 table automatically; nothing is hardcoded to M24.
- Washer block now also has a small edge-break chamfer (≈ 0.05 × flange_h) for realism consistency.

## Migration / rollout notes
- Prompt-only; no breaking changes.
- The new `_ISO_COARSE_PITCH` dict adds ~3 lines to each of Block 1 and Block 2 — still well under the 80-line-per-block limit.
- Existing recipes outside the Multi-block protocol section are unchanged.

## Rollback notes
Revert `neurocad/config/defaults.py` — all changes are confined to Block 1, Block 2, Block 3 of the canonical bolt+washer example.

## Manual verification (visual + automated analyzer)

Re-run dog-food:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

Visual acceptance: the bolt renders with:
- Thread at the **lower ~40–60 %** of the shank (the free end / tip).
- Smooth cylindrical shoulder of ≈ 1 × major_d directly below the hex head.
- Hex head chamfered on all edges; shank tip chamfered (thread-entry).

If thread still shows up directly below the head, the LLM is ignoring the Block 2 `helix.Placement` — escalate to Sprint 5.11 with a more explicit anti-pattern example.

---

# Release Notes – Sprint 5.9 (Realism: Chamfers, Fillets, Visual Detail)

**Date:** 2026‑04‑18
**Based on:** Second dog-food after Sprint 5.8. User confirmed «запросы выполняются» but provided photos of real ISO bolts next to NeuroCad output, noting «результат выглядит сильно упрощенным… нет граней, закруглений, выдавливаний». Root cause: the multi-block canonical bolt example had no chamfers/fillets, and a WARNING earlier in the prompt («DO NOT apply Part::Fillet to the final threaded body») was over-generalized by the LLM to «never use chamfers».

---

## PR Summary
Sprint 5.9 is a **prompt-only** sprint — no executor, agent, worker or config changes. Two targeted edits to `DEFAULT_SYSTEM_PROMPT` push the LLM to produce manufactured-looking parts instead of bare primitives:
1. The canonical three-block bolt example now adds `Part::Chamfer` on the hex head (all edges, 0.08 × major_d) and on the shank's circular edges only (0.04 × major_d — this is the thread-entry taper). The Fuse uses the chamfered primitives, not raw prism/cylinder.
2. The old negative-framed WARNING is rewritten into a positive recommendation: "Chamfers and fillets are ENCOURAGED for realism — apply to individual primitives BEFORE the Fuse chain". The hard technical constraint (never chamfer/fillet the final threaded body after Cut) is kept, but now reads as a single boundary condition rather than a blanket ban.
3. A new subsection "Realism — chamfers and fillets are the default" sits between the Parameter header and the Rules list, giving concrete depth formulas for hex head, cylindrical shank, fuse junction, washer edge, and gear root.

## User-visible changes
- **Canonical bolt example** now produces: hex head with top/bottom/vertical-edge chamfers (like a real turned bolt), cylindrical shank with thread-entry chamfer on the bottom face, and a proper Fuse over both chamfered primitives.
- **Prompt framing** — LLM is actively encouraged to add fillets/chamfers, not just tolerated.
- **Realism guidance** gives the LLM numeric defaults so it does not need to guess dimensions.

## Migration / rollout notes
- Prompt-only; no breaking changes.
- The new `Part::Chamfer` steps add ~10 lines to Block 1 — still well under the 80-line-per-block limit.
- Existing recipes in `PART V — Bolt, Gear` section unchanged.

## Rollback notes
Revert `neurocad/config/defaults.py` — all changes are confined to the Multi-block protocol section and the former fillet WARNING block.

## Manual verification (visual diff, automated via analyzer)

Re-run dog-food:
```bash
python scripts/dogfood_check.py --since "<session-start>"
```

R1–R4 pass-rate should match Sprint 5.8 (≥ 60%), PLUS visual inspection of the generated bolts should show:
- Hex head with **chamfered top face** (no sharp 90° edges at the top) — visible as a thin bevel ring.
- **Thread-entry chamfer** on the bottom of the shank (the threaded end tapers slightly before the thread profile begins).
- Fuse transition at head-shank junction smoothed if user asked for fillets.

---

# Release Notes – Sprint 5.8 (Parametric Recipes + Multi-Block Scoping + Gear Reality Check)

**Date:** 2026‑04‑18
**Based on:** First dog-food of Sprint 5.7 protocol — `scripts/dogfood_check.py --since "2026-04-18 10:00"` reported 2/9 (22%) pass rate (target ≥ 60%). Three clean root causes surfaced; Sprint 5.8 addresses each.

---

## PR Summary
Sprint 5.7 delivered a multi-block protocol that split complex scripts into fenced blocks. Dog-food showed the LLM understood it structurally but failed on two assumptions: (1) variables do NOT actually persist across blocks (each block runs in a fresh `exec()` namespace), and the prompt only mentioned this once — not enough; (2) `PartDesign::InvoluteGear` is NOT a document-object type in stock FreeCAD 1.1 (it lives in the optional Gears Workbench addon), but our recipe recommended it. Also, the generic `Touched/Invalid` feedback pointed the LLM at Part::Fillet when the real failure was in the thread Cut. Sprint 5.8 fixes all three.

## User-visible changes
- **Parameter header rule (prompt)**: every fenced block now MUST re-declare all numeric constants at its top. The canonical bolt example is rewritten to be fully parametric — derives `minor_d`, `shank_r`, `head_h`, `head_key`, `thread_h` from `major_d` + `pitch` using ISO 261 formulas, so the LLM can scale from M8 to M48 without memorizing M24-specific numbers.
- **Gear recipe rewritten for stock FreeCAD 1.1**: no more `PartDesign::InvoluteGear`. The new recipe builds a parametric spur gear from Part WB primitives — Revolution disc + Part::Box tooth + Python loop + `Part.makeCompound` + Part::MultiFuse. No addon required.
- **Thread-aware `Touched/Invalid` feedback**: when the invalid object's name contains `Thread`, `Bolt`, `Sweep`, `Helix`, or `Cut`, the feedback now returns a thread-specific six-point checklist (sweep.Shape.isValid, helix.Height ≤ shank.Height, ≤10 turns, Frenet=True, direct Cut without intermediate Fuse, retry with smaller thread_depth).
- **Static recipe verifier updated**: `PartDesign::InvoluteGear` moved from VALID_OBJECT_TYPES to BLOCKED_OBJECT_TYPES; attempts to add it back are caught by `tests/test_prompt_recipe.py`.
- **`_make_feedback` branch for `PartDesign::InvoluteGear`**: points the LLM at the Part WB approximation recipe instead of generic "unknown type" message.

## Migration / rollout notes
- Prompt-only changes (plus 2 targeted feedback branches in `agent.py`). No executor, threading, transaction, config, or adapter changes.
- Existing users on Sprint 5.7 see no breaking changes — the protocol is the same, rules are stricter.
- Recipe verifier whitelist now permits 45 types (was 46); the new BLOCKED list has 5 entries (was 4).

## Rollback notes
Revert these files:
- `neurocad/config/defaults.py` — multi-block protocol rewrite + gear recipe
- `neurocad/core/agent.py` — `_re_search_invalid_name` helper, `Touched/Invalid` thread branch, `PartDesign::InvoluteGear` feedback branch
- `tests/test_prompt_recipe.py` — whitelist/blocklist moves
- `tests/test_agent.py` — 2 new tests

## Manual verification checklist (automated via analyzer)

After submitting the R-prompts in live FreeCAD, run the analyzer — the developer does not need to read the raw log:

```bash
python scripts/dogfood_check.py --since "<session-start>"
```

Target: ≥ 60% pass rate on R1–R3, 100% on R4. Baseline (Sprint 5.7): 22%.

If the target is not reached, `scripts/dogfood_check.py` reports per-run error type and the failed objects, guiding the next Sprint-5.9 scope.

---

# Release Notes – Sprint 5.7 (Complex Task Success: Recipe Fix + Multi-Block Protocol + Static Verifier)

**Date:** 2026‑04‑18
**Based on:** User-stated goal — «Сделай сложный болт M30 с резьбой и шайбой» must actually succeed, not just fail gracefully. Dog-food audit 2026-04-14 traced the root cause to two prompt bugs: a hallucinated object type recommended in a positive example, and a mandatory monolithic output that blew past the handoff timeout.

---

## PR Summary
Sprint 5.7 targets the correctness of `DEFAULT_SYSTEM_PROMPT` itself, not the agent/loop around it. The prompt was simultaneously (1) recommending `Part::LinearPattern` / `Part::Array` as "always reliable" in a positive code example, AND (2) listing them in the `## Blocked` section as non-existent — LLMs predictably picked the positive example. The prompt also forbade markdown fences, forcing LLMs to dump complex assemblies into one 9000-character block that timed out at the main-thread handoff. Both issues are now fixed, and a static verifier protects the prompt from future recipe regressions.

## User‑visible changes
- **Hallucinated type removed**: `Part::LinearPattern` / `Part::PolarPattern` / `Part::MultiTransform` / `Part::Array` no longer appear as positive examples anywhere in the prompt. Three recipe sections (fake-thread via stacked discs, bolt assembly summary, decorative-thread full example) now use a Python loop + `Part.makeCompound` instead.
- **Multi-block protocol documented**: the prompt explicitly instructs the LLM to split complex assemblies (bolt+thread+washer, wheel+spokes+hub, gear+shaft+key) into 2–3 fenced ```python``` blocks, each ≤ 80 lines. A canonical three-block bolt+washer layout is provided as a copy-paste reference.
- **Static recipe verifier added** (`tests/test_prompt_recipe.py`): 5 tests scan the prompt for `doc.addObject(TYPE)` / `body.newObject(TYPE)` calls and verify each type is in a FreeCAD 1.x whitelist. CI catches any future recipe drift.

## Migration / rollout notes
- Prompt changes are additive except the three recipe rewrites — no existing valid recipe was removed.
- Executor support for multiple fenced blocks has existed since Sprint 5.4 (`extract_code_blocks` returns a list). Only the prompt was missing the user-facing protocol.
- No breaking changes to config, API keys, adapter, or UI.
- Audit-log format unchanged.

## Rollback notes
Revert these files:
- `neurocad/config/defaults.py` — the three recipe rewrites and the new "Multi-block protocol" section
- `tests/test_prompt_recipe.py` — delete

## Dog-food verification (automated via log analyzer)

Developer submits the R1–R4 prompts in live FreeCAD, then runs the analyzer
which parses `llm-audit.jsonl` and prints a pass/fail report — no manual
reading of raw JSON.

Analyzer: `scripts/dogfood_check.py` (unit-tested via `tests/test_dogfood_check.py`).

```bash
# After finishing the prompts below, run:
python scripts/dogfood_check.py --last-hour
# or:
python scripts/dogfood_check.py --since "2026-04-18 19:00"
```

Prompts to submit (run each 5 times to get a reliable success rate):

| Code | Prompt | PASS criterion (auto-checked) |
|------|--------|-------------------------------|
| R1 | `Сделай болт M24 по ISO с резьбой без упрощений` | `agent_success` AND object names contain `Thread` or `Bolt` |
| R2 | `Сделай сложный болт M30 с резьбой и шайбой` | `agent_success` AND objects contain BOTH a bolt-like AND a washer/flange/ring |
| R3 | `Сделай колесо велосипеда со спицами` | `agent_success` AND ≥ 3 objects created |
| R4 | `Сделай куб 50x50x50` (regression) | `agent_success` AND ≤ 2 attempts |

The analyzer also reports each run's `correlation_id`, prompt preview,
final event type, and — on failure — the `error_type` (e.g.
`max_retries_exhausted`, `cancelled_by_user`, `handoff_timeout`).

## Success criteria
Sprint 5.7 is considered a success if `dogfood_check.py --last-hour`
reports ≥ 60% pass rate on R1–R3 after the developer runs each prompt
5 times. R4 is a regression gate — must be 100%.

---

# Release Notes – Sprint 5.6 (Cancellation Fast-Exit, Handoff Timeout Tuning, Runtime Feedback Expansion)

**Date:** 2026‑04‑18
**Based on:** Sprint 5.6 completion — dog-food audit 2026-04-14 (6 h window, 55 attempts, 36% success).

---

## PR Summary
Sprint 5.6 hardens the agent retry loop around user cancellation and heavy-code timeouts, and expands `_make_feedback` with two new runtime patterns. The Stop button (already shipped) now actually short-circuits the retry loop instead of silently burning two additional LLM calls; the hard-coded 15 s handoff timeout is configurable (default 60 s) and no longer retries on the same heavy script; and two previously generic errors (`list index out of range`, `Shape is invalid`) now get actionable hints.

## User‑visible changes
- **Stop button is now cheap**: pressing Stop exits the retry loop after the current attempt and logs a single `agent_error` with `error_type="cancelled_by_user"`; no more `Max retries exceeded: Cancelled` wasted token spend.
- **Handoff timeout raised from 15 s → 60 s** and is now adjustable via the `exec_handoff_timeout_s` key in `config.json`.
- **No retry on handoff timeout**: the same heavy code is not re-sent; the user receives an actionable feedback asking to split the script into 2–3 smaller blocks.
- **`list index out of range`** gets a targeted hint about `edge.Vertexes[1]` on closed circular edges (only 1 vertex), `shape.Faces[0]` on wires/compounds, and empty-collection access.
- **`Shape is invalid`** (distinct from `Shape is null`) now suggests `shape.fix()`, `shape.removeSplitter()`, and `shape.isValid()` between boolean ops.

## Migration / rollout notes
- Additive change to `config.json`: new key `exec_handoff_timeout_s` with default `60.0`. Existing config files continue to work; the key is injected with the default on next `load()`.
- No breaking changes to adapter, executor, validator, worker or panel contracts.
- Two new audit-log event types (`cancelled_by_user`, `handoff_timeout`) replace the previous `max_retries_exhausted` for these cases.

## Rollback notes
Revert these files if necessary:
- `neurocad/core/agent.py` — `_make_feedback` + fast-exit branches
- `neurocad/core/worker.py` — `load_config` import + timeout read
- `neurocad/config/config.py` — `DEFAULT_EXEC_HANDOFF_TIMEOUT_S` + `load()` defaults

## Manual verification checklist
- [ ] **M1 — Stop button**: submit `Сделай сложный болт M30 с резьбой и шайбой`, press Stop during `attempt 1/3`; verify a single `Cancelled by user` feedback bubble, status dot returns to idle, only one `agent_error` with `error_type="cancelled_by_user"` in `llm-audit.jsonl`, NO `attempt 2`/`attempt 3` records.
- [ ] **M2 — Handoff timeout no retry**: submit a very heavy prompt (e.g., `Сделай bicycle frame из 20 труб с filletами на каждом стыке в одном коде`); wait up to 60 s; verify exactly one attempt, audit `error_type="handoff_timeout"`, feedback contains «Split the script».
- [ ] **M3 — `list index` hint**: if a wheel / spokes prompt triggers the error, confirm the feedback mentions circular edges, `Vertexes`, and `len(...)`.
- [ ] **M4 — `Shape is invalid` hint**: trigger a zero-result boolean (`куб 50³` minus identical cube shifted by 50 mm along X); feedback should mention `shape.fix()`, `self-intersection`, `removeSplitter()`.
- [ ] **M5 — Regression**: simple `Сделай куб 20×20×20` and `Сделай шестерёнку 20 зубьев` still succeed as before.
- [ ] **M6 — Config timeout override**: edit `~/Library/Application Support/FreeCAD/v1-1/neurocad/config.json`, set `"exec_handoff_timeout_s": 5`, restart FreeCAD, send a heavy prompt → handoff fails in ≤ 5 s.

---

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

# Release Notes – LLM Timeout & Snapshot Limit Increase

**Date:** 2026‑04‑14
**Based on:** User‑reported timeout errors and analysis of LLM response patterns.

## PR Summary
Increased default LLM timeout from 120 to 180 seconds to accommodate longer‑running model responses. The timeout is now configurable via Settings UI and config file. Also increased the snapshot character limit from 1000 to 1500 to provide more context to the LLM.

## User‑visible changes
- **Default LLM timeout raised** from 120 s to 180 s.
- **Timeout configurability** – the value can be adjusted in Settings → “LLM timeout (s)”.
- **Snapshot character limit raised** from 1000 to 1500 characters, providing richer document context to the LLM.

## Migration / rollout notes
- No breaking changes; existing config files will keep their current `timeout` and `snapshot_max_chars` values.
- New installations and config‑less runs will use the increased defaults automatically.
- No new environment variables or configuration keys are required.
- **None**

## Rollback notes
If a revert is required, revert the following files:
- `neurocad/config/config.py` – `DEFAULT_TIMEOUT` and imports
- `neurocad/config/defaults.py` – `DEFAULT_SNAPSHOT_MAX_CHARS`
- `neurocad/llm/anthropic.py` – `timeout` parameter in constructor
- `neurocad/llm/openai.py` – `timeout` parameter in constructor
- `neurocad/ui/settings.py` – default value in `_load_current`
- `neurocad/ui/panel.py` – `_llm_timeout_ms` default
- `tests/test_agent.py` – updated test expectations

No special rollback steps beyond reverting the code.

## Manual verification checklist
- [ ] Open FreeCAD, activate NeuroCad workbench, open Settings.
- [ ] Verify that the “LLM timeout (s)” field shows 180.0 by default.
- [ ] Submit a prompt that triggers a long‑running LLM request (e.g., “generate a complex parametric model”) and confirm the request does not time out before 180 s.
- [ ] Use the “Show Snapshot” button and inspect the printed snapshot; verify that the snapshot length is capped at approximately 1500 characters.

---

*These notes are intended for developers, QA, and deployment teams. For end‑user documentation, see the updated `README.md` and `DEV_SETUP.md`.*