# NeuroCad

AI‑powered CAD assistant for FreeCAD.

**This project is under active development.**  

For installation and development instructions, see [DEV_SETUP.md](DEV_SETUP.md).  
For architecture and sprint plans, see the `doc/` directory.

Current implementation status (Sprint 5.14, April 2026):
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

## License

MIT
