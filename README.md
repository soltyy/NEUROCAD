# NeuroCad

AI‑powered CAD assistant for FreeCAD.

**This project is under active development.**  

For installation and development instructions, see [DEV_SETUP.md](DEV_SETUP.md).  
For architecture and sprint plans, see the `doc/` directory.

Current implementation status (Sprint 6.0, May 2026):

- Plan-driven multi-pass agent architecture (Sprint 6.0 MVP): the agent now extracts a structured `DesignIntent` from the user prompt, asks for clarification on critical missing info, plans the assembly part-by-part, executes each step independently with a per-step contract verifier, and persists the plan in history for follow-up requests. The legacy single-pass `agent.run` is preserved untouched; v2 is opt-in via `headless_dogfood.py --use-v2` (and a future Settings toggle in the UI).
- Generic feature detectors replace per-class anti-patterns: `axle_hole`, `thread`, `hex_section`, `hollow`, `stepped_axial`, `bbox_length`, `long_axial` are domain-agnostic — adding a new engineering class (I-beam, turbine blade, manifold) needs zero new validator code.
- 13× system-prompt token reduction: the v2 prompt is 12.9 k chars (≈ 1.6 k input tokens) vs the legacy 69 k chars (≈ 21 k input tokens), making each LLM call ~13× cheaper.
- Multi-channel response parser understands `<plan>`, `<comment>`, `<question type=… options=…>` and `<code step="N">` tags so the LLM can ask clarifying questions, narrate its rationale, and emit code for one step at a time.

Previous status (Sprint 5.22, May 2026):
- LLM integration (OpenAI, Anthropic) with configurable provider, model, and API key management
- Multi‑step Python code execution from LLM responses with rollback on error
- Secure API key storage via system keyring, environment variables, or session‑only use
- Structured audit logging (JSONL) with redaction, rotation, and config toggle
- Modern UI with Claude‑style layout, adaptive input, and panel‑side diagnostics
- Full geometry generation, validation, and export (STEP/STL)
- Settings dialog for provider configuration and persistent vs. session‑only auth
- Stop button with fast-exit cancellation (no wasted retries)
- Configurable execution handoff timeout (default 60s) with actionable feedback
- Expanded runtime error hints: `list index out of range`, `Shape is invalid`, `Cancelled`
- Fixed system-prompt recipe: no more `Part::LinearPattern` hallucinations (Sprint 5.7)
- Multi-block protocol for complex assemblies (bolt+thread+washer split across 2–3 blocks)
- Static recipe verifier protects the prompt from hallucinated FreeCAD object types
- Parametric bolt recipe (major_d / pitch / minor_d = major_d - 1.226·pitch) — scales to M8…M48 (Sprint 5.8)
- Parameter header rule: every fenced block re-declares its numeric constants
- Stock-FreeCAD-1.1 gear recipe (Part WB approximation, no Gears Workbench addon required)
- Thread-aware Touched/Invalid feedback with sweep/helix/Cut diagnostics
- Realistic part detail by default: canonical bolt carries chamfers on hex head + shank (thread-entry) — no more bare prism+cylinder look (Sprint 5.9)
- Reframed fillet guidance: chamfers/fillets on individual primitives BEFORE the Fuse chain are ENCOURAGED, not forbidden
- Thread placed at the free end of the shank (ISO convention — smooth shoulder under the head) (Sprint 5.10)
- Fully parametric canonical recipe: only `major_d` is hand-set; `pitch` derives from an ISO 261 lookup table, `thread_h` from `shank_h` and `pitch` (no arbitrary constants)
- Thread cut actually happens: wire-level `helix_wire.makePipeShell(...)` replaces the silent-failing `Part::Sweep` document object; an explicit `isValid() + Volume > 0` assertion catches degenerate sweeps before the Cut (Sprint 5.11)
- Truly parametric canonical template: `<MAJOR_D_FROM_REQUEST>` / `<SHANK_H_FROM_REQUEST>` / `<ISO_STANDARD_FROM_REQUEST>` placeholders are syntactically invalid Python — the LLM is forced to substitute from the actual user request instead of copying `24.0` verbatim (Sprint 5.12)
- ISO 4014 / ISO 4017 thread-length derivation: partial-thread length per the three shank-length bands (`2d+6` / `2d+12` / `2d+25`), full-thread = shank_h minus a half-d shoulder
- Washer block is conditional: emitted only when the user explicitly asks for a washer / шайба / flange
- Canonical naming contract (bolt / gear / wheel tables with explicit "NEVER use" aliases) eliminates cross-block variable drift that caused 14+ NameError failures per dog-food session (Sprint 5.13)
- Block-aware NameError feedback: failures in Block ≥ 2 receive a fresh-namespace + canonical-names diagnosis instead of a generic message
- Narrower REFUSAL_KEYWORDS (only download / fetch url / wget / curl) — legitimate "импорт STEP" / "export to file" requests no longer triaged away before the LLM sees them
- Wireframe / math-visualization canonical recipe (PART VI): sphere-per-vertex + cylinder-per-edge with `make_edge_cylinder` helper, `math.acos` clamp, degenerate-edge skip — covers hypercubes, graphs, polytopes, knots, fractals (Sprint 5.14)
- Explicit `FreeCAD.Vector is always 3D` warning with nD → 3D projection example — no more `Vector(x1, x2, x3, x4, x5)` TypeErrors on higher-dimensional requests
- Cross-platform tiered API-key storage (Sprint 5.15): Python `keyring` → macOS `security` CLI → Linux `secret-tool` CLI → plaintext-0600 file. No more modal "could not save securely" — the Settings dialog has radio buttons (Automatic / Plaintext / Session only) and shows where the key ended up inline.
- Revolution-specific `shape is invalid` feedback + `fillet_arc_points` bevel helper for stepped-shaft profiles — no more self-intersecting wires from hand-rolled arc math (Sprint 5.16)
- `no_code_generated` is now retriable with a stronger "emit a fenced python block, do not apologize" feedback — previously the LLM could deadlock the agent on a single prose response
- Concrete-model registry (Sprint 5.17): the user picks a specific LLM by name ("DeepSeek Chat", "Claude 3.5 Sonnet") in a single dropdown. Adapter class, base URL, context window, file-handling strategy and per-model API-key slug are all auto-configured from `neurocad/llm/models.py`. DeepSeek's inline file-embed template is pre-wired.
- Per-slug API keys: DeepSeek's key is stored separately from OpenAI's even though both use the OpenAI-compatible adapter — no more overwriting one with the other.
- Truncation detection (Sprint 5.18): when the LLM hits its `max_tokens` ceiling, the agent shows a concrete split-into-blocks feedback instead of a bogus SyntaxError on the truncated code; default `max_tokens` bumped to 8192.
- Tightened Quantity anti-pattern guidance: `obj.Length.Value` is now the only recommended path; `float(obj.Length)` is flagged as fragile.
- Export button removed from the panel (feature was unused); `core/exporter.py` remains for programmatic use.
- Chat panel autoscroll anchored via `verticalScrollBar.rangeChanged` (Sprint 5.19) — no more "chat went blank after N requests" drift; respects user scroll-up.
- 3D-text canonical recipe (PART VII, Sprint 5.20): cross-platform `neurocad_default_font()` + `Draft.make_shapestring + Part::Extrusion` + `place_word_on_orbit` helper. Executor exposes `platform_name` and `file_exists` in the sandbox.
- Smarter NameError feedback: if the undefined name looks like a FreeCAD document object (Capitalized / Cyrillic / contains `sphere`, `куб`, `bolt`, `шайб`, …), the suggestion is `varname = doc.getObject('...')` instead of the generic scoping message.
- ViewObject attribute-error feedback: `FontSize / TextSize / LabelText / …` on a Part ViewProvider redirects the LLM to the PART VII 3D-text recipe.
- Audit log processing-state lifecycle (Sprint 5.21): every entry carries `processing_state` (`new` / `analyzed_needs_action` / `analyzed_done` / `processed`). `scripts/audit_state.py` provides `migrate` (retro-classify by sprint-mapped rules), `stats`, and `mark` sub-commands. 815 historic entries were classified — 145 processed, 658 closed without action, 12 open for follow-up.
- Autonomous end-to-end harness `scripts/headless_dogfood.py` (Sprint 5.22): 2-process bridge — driver (project venv with `anthropic`/`openai` SDK) ↔ worker (`freecadcmd` subprocess with real FreeCAD 1.1) over JSON-Lines RPC. Curated scenarios (cube, M24 bolt with thread, "АТЛАС КОНСАЛТИНГ" 3D text on a sphere orbit) run the full LLM → code → exec → validate loop without manual UI clicks; success is verified against `Shape.Volume` / `isValid()` instead of fragile name substrings.
- Five new `_make_feedback` runtime branches (Sprint 5.22): `Cannot create polygon (too few vertices)`, `range() arg 3 must not be zero`, `Failed to create face from wire`, `unsupported format string passed to Base.Quantity.__format__`, `Either three floats … Vector expected`. All branches are strictly additive (no existing feedback changed).
- Audit classifier extended (Sprint 5.22): +8 needles in `_ERROR_PATTERN_RULES`, `adapter_init_failure → processed` event-type rule, routing applied to non-`agent_*` event types, and a new `migrate --reclassify` flag that promotes-only (never downgrades). Production log re-migrated: `analyzed_needs_action` 12 → 0.

## License

MIT
