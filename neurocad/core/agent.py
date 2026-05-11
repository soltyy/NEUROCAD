"""Agent orchestrates LLM, execution, validation, and rollback."""

import re
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from neurocad.config.defaults import REFUSAL_KEYWORDS

from .audit import audit_log, get_correlation_id
from .code_extractor import extract_code_blocks
from .debug import log_error, log_info, log_notify, log_warn
from .executor import ExecResult, execute
from .history import History, Role
from .prompt import build_system
from .validator import validate


@dataclass
class AgentCallbacks:
    """Callbacks for agent events."""
    on_chunk: Callable[[str], None] = lambda _: None
    on_attempt: Callable[[int, int], None] = lambda _, __: None
    on_status: Callable[[str], None] = lambda _: None
    on_exec_needed: Callable[[str, int], dict] = lambda _, __: {"ok": False, "new_objects": []}


@dataclass
class AgentResult:
    """Result of an agent run."""
    ok: bool
    attempts: int
    error: str | None = None
    new_objects: list[str] | None = None
    rollback_count: int = 0

    def __post_init__(self):
        if self.new_objects is None:
            self.new_objects = []


def _categorize_error(error: str) -> str:
    """Return normalized error category."""
    if error is None:
        return "runtime"
    error_lower = error.lower()
    if "blocked token" in error_lower:
        return "blocked_token"
    unsupported_modules = ["part", "freecad", "app", "mesh", "draft", "sketcher", "partdesign"]
    if any(f"module '{mod}' has no attribute" in error_lower for mod in unsupported_modules) or "has no attribute 'make" in error_lower:
        return "unsupported_api"
    if "validation failed" in error_lower:
        return "validation"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "llm error" in error_lower or "adapter call failed" in error_lower:
        return "llm_transport"
    return "runtime"


def _re_search_invalid_name(error: str) -> str | None:
    """Extract the object name from 'Validation failed for NAME: ...' messages."""
    import re as _re
    m = _re.search(r"validation failed for (\S+?):", error, _re.IGNORECASE)
    return m.group(1) if m else None


def _is_blocked_import(error: str) -> bool:
    """Return True if the blocked token is 'import' or 'from'."""
    if error is None:
        return False
    error_lower = error.lower()
    if "blocked token" in error_lower:
        # Check for 'import' or 'from' token
        # Example: "Blocked token 'import' found at line 1"
        import_pos = error_lower.find("'import'")
        from_pos = error_lower.find("'from'")
        return import_pos != -1 or from_pos != -1
    return False


def _make_feedback(
    error: str,
    category: str,
    block_idx: int = 1,
    total_blocks: int = 1,
) -> str:
    """Return a concise user-facing feedback message.

    block_idx / total_blocks describe the failed block's position in the LLM
    response (1-based). Used to specialize the NameError branch: in a
    multi-block response, most NameErrors after block 1 come from naming
    drift — the LLM renamed a variable between blocks (major_d → major_diameter,
    shank_h → shank_length, etc.). The specialized branch gives the LLM a
    concrete corrective.
    """
    if category == "blocked_token":
        error_lower = error.lower()
        # Extract the blocked token name from the error message, e.g. "Blocked token 'os' found at line 3"
        import re as _re
        m = _re.search(r"blocked token '(\w+)'", error_lower)
        token = m.group(1) if m else ""
        if token in ("os", "sys", "subprocess", "socket", "urllib", "http",
                     "requests", "shutil", "tempfile", "pathlib",
                     "ctypes", "cffi", "pickle", "shelve", "importlib"):
            return (
                f"Module '{token}' is blocked — file system, process, and network access "
                f"are not permitted. Use FreeCAD's built-in Part/PartDesign/Draft/Mesh APIs only."
            )
        if token == "freecadgui":
            return "FreeCADGui is not available in the headless execution context. Do not use it."
        if token in ("eval", "exec", "__import__"):
            return f"'{token}' is forbidden. Do not use dynamic code execution."
        return f"Blocked token '{token}' is not allowed. Remove it."
    if category == "unsupported_api":
        error_lower = error.lower()
        math_keywords = ["cos", "sin", "tan", "sqrt", "pi", "atan"]
        if any(kw in error_lower for kw in math_keywords):
            return (
                "FreeCAD modules have no math functions. Use `math.cos()`, `math.sin()` etc. — "
                "`math` is pre‑loaded in the namespace."
            )
        if "makepipeshell" in error_lower:
            return (
                "makePipeShell must be called on a Wire (the path), not on a Face. "
                "Correct pattern: helix = Part.makeHelix(pitch, height, radius); "
                "profile = Part.Wire([Part.makeCircle(r, center, normal)]); "
                "shape = helix.makePipeShell([profile], makeSolid=True, isFrenet=True); "
                "feat = doc.addObject('Part::Feature', 'Name'); feat.Shape = shape; doc.recompute()"
            )
        if "has no attribute 'transform'" in error_lower:
            return (
                "Part.Shape has no .transform() method. "
                "Use shape.transformShape(matrix) to modify in-place, or "
                "new_shape = shape.transformed(matrix) to get a copy. "
                "Build a rotation matrix with: m = FreeCAD.Matrix(); m.rotateZ(angle_rad). "
                "Alternatively compute rotated coordinates directly with math.cos/sin."
            )
        return (
            "Unsupported FreeCAD API used. Available: Part primitives (makeBox, makeCylinder, "
            "makeSphere, makeCone, makeHelix, makePolygon, makeCircle), "
            "wire.makePipeShell(), Part::Feature for raw shapes, "
            "PartDesign::InvoluteGear for gears."
        )
    if category == "validation":
        error_lower = error.lower()
        if "shape is invalid" in error_lower:
            # If the invalid object is a Part::Revolution / its profile /
            # its wire — give revolution-specific hints (self-intersecting
            # profile wire is a far more common root cause than OCCT sweep
            # / boolean issues in this case).
            name_re = _re_search_invalid_name(error)
            is_revolution_object = (
                name_re
                and any(token in name_re.lower()
                        for token in ("revolution", "revolved", "axis",
                                      "profile", "wire", "ring"))
            )
            if is_revolution_object:
                return (
                    "Validation failed: shape is invalid on a Part::Revolution "
                    "or its 2D profile. OCCT rejects the revolved result because "
                    "the input wire is malformed. Checklist: "
                    "(1) Call `profile_wire.isValid()` BEFORE `Part.Face(wire)` — "
                    "catch self-intersection early; "
                    "(2) The polygon must be CLOSED (last vertex == first vertex), "
                    "with vertices ordered consistently (all CCW or all CW); "
                    "(3) All points MUST lie on ONE side of the rotation axis — "
                    "if your profile is in the XZ plane revolving around Z, every "
                    "vertex must have `x >= 0`; crossing the axis produces a "
                    "self-intersecting solid; "
                    "(4) Fillet/galtel approximations via arc points often place "
                    "the first point OFF the adjacent segment (wrong arc centre) — "
                    "double-check that each arc's START equals the previous "
                    "straight segment's END, exactly, to the last decimal. When "
                    "in doubt, use a linear bevel (see `fillet_arc_points` helper "
                    "in the prompt's PART V); it never self-intersects; "
                    "(5) Avoid touching the rotation axis with a horizontal run "
                    "(a vertex exactly at `x==0` on Z-axis creates a degenerate "
                    "cone apex); offset by ≥ 1e-4 or close the profile to the axis "
                    "via a single radial move only at the extremes."
                )
            return (
                "Validation failed: shape is invalid — geometry was computed but "
                "OCCT flagged it as malformed (self-intersection, zero-area face, "
                "non-manifold edge). Most common source: boolean Fuse/Cut of two "
                "shapes that share a degenerate face, or sweeping along a path "
                "with a tight turn. Fix: call shape.fix() or shape.removeSplitter() "
                "on the problematic intermediate; verify each input with "
                "shape.isValid() before the next boolean."
            )
        if "shape is null" in error_lower:
            return (
                "Validation failed: shape is null — an upstream object failed to compute its shape. "
                "Ensure every object has doc.recompute() called after setting its properties, "
                "and that boolean inputs (Base/Tool) are valid solids before use. "
                "Avoid mixing PartDesign::Body features with Part WB boolean operations outside the Body."
            )
        if "touched" in error_lower and "invalid" in error_lower:
            # If the invalid object name looks thread-related, give the
            # thread-specific diagnosis (far more common in dog-food than
            # fillet issues). Otherwise fall back to the fillet diagnosis.
            name_re = _re_search_invalid_name(error)
            is_thread_object = (
                name_re
                and any(token in name_re.lower()
                        for token in ("thread", "bolt", "sweep", "helix", "cut"))
            )
            if is_thread_object:
                return (
                    "Validation failed: object state ['Touched', 'Invalid'] on a "
                    "thread-related object. OCCT rejected the Part::Cut of the "
                    "helical sweep from the bolt shank. Checklist: "
                    "(1) `sweep.Shape.isValid()` must be True before Cut — if not, "
                    "rebuild the profile (closed, radial, INTERSECTS the shank — "
                    "not tangent); "
                    "(2) helix must STRICTLY fit inside the shank length along Z "
                    "— `helix.Height < shank.Height`; "
                    "(3) keep thread ≤ 10 turns (`thread_h ≤ 10 * pitch`) — OCCT "
                    "boolean fails on long helices; "
                    "(4) use `sw.Frenet = True`; "
                    "(5) cut directly from shank or body: `Cut.Base = body; "
                    "Cut.Tool = sweep` — NEVER fuse a cylinder with the sweep before "
                    "cutting (that swallows the thread profile); "
                    "(6) if it still fails, retry with a shorter thread_h and "
                    "smaller thread_depth (e.g. depth = 0.6 × canonical)."
                )
            return (
                "Validation failed: object state ['Touched', 'Invalid'] — the geometry could not be computed. "
                "Most common cause: Part::Fillet or Part::Chamfer applied to an object that contains helical "
                "sweep or complex boolean cut results — OCCT cannot reliably fillet such edges. "
                "Fix: remove the Fillet entirely, OR apply fillets only to individual simple primitives "
                "(e.g. the hex head prism, the shank cylinder) BEFORE the thread Cut operation. "
                "Never fillet the final assembled+threaded body. "
                "If no fillet is involved: check that all upstream shapes are valid with shape.isValid()."
            )
        return f"Validation failed: {error}"
    if category == "timeout":
        if "handoff" in error.lower():
            return (
                "Execution handoff timed out — the generated code took longer than the "
                "handoff window to execute on the main thread. The code is likely too "
                "large or does too many heavy boolean operations in one block. "
                "Split the script into 2–3 smaller fenced blocks (each ≤ 80 lines) "
                "and keep each boolean/cut operation isolated, so the executor can "
                "recompute incrementally."
            )
        return "Execution timed out."
    if category == "llm_transport":
        return f"LLM error: {error}"
    # Runtime: check for known patterns
    error_lower = error.lower()
    if error_lower.strip().startswith("cancelled"):
        return "Cancelled by user."
    if "is not a document object type" in error_lower:
        import re as _re
        m = _re.search(r"'([^']+)' is not a document object type", error)
        bad_type = m.group(1) if m else ""
        if bad_type in ("Part::LinearPattern", "Part::PolarPattern",
                        "Part::MultiTransform", "Part::Array"):
            return (
                f"'{bad_type}' does not exist in Part WB. "
                "Part workbench has no pattern/transform objects. "
                "For linear arrays: use a Python loop + Part.makeCompound([...copies...]). "
                "For polar arrays: use a Python loop with FreeCAD.Rotation to copy shapes. "
                "Example: copies = []; shape.rotate(center, axis, angle_deg) in loop; "
                "Part::Compound with Links = [...] for grouping without fusion."
            )
        if bad_type == "PartDesign::InvoluteGear":
            return (
                "'PartDesign::InvoluteGear' is NOT available in stock FreeCAD 1.1 — "
                "it requires the external Gears Workbench addon. "
                "Use the Part WB gear approximation instead: "
                "(1) parameterize teeth_n, module_m, pitch_r, root_r, tip_r; "
                "(2) build a base Part::Revolution disc of radius root_r; "
                "(3) create one trapezoidal tooth as Part::Box placed at (root_r, -w/2, 0); "
                "(4) replicate with a Python loop `for i in range(teeth_n): c = tooth.Shape.copy(); "
                "c.rotate(center, Z_axis, i*360/teeth_n); copies.append(c)`; "
                "(5) wrap via `feat.Shape = Part.makeCompound(copies)`; "
                "(6) fuse disc + teeth compound via Part::MultiFuse."
            )
        return f"Unknown object type '{bad_type}'. Check the exact type string."
    if "is not defined" in error_lower:
        import re as _re
        m = _re.search(r"name '(\w+)' is not defined", error)
        varname = m.group(1) if m else ""

        # Cross-block naming drift — dominant failure mode in multi-block
        # responses (14+ cases in 2026-04-18 dog-food). If this is NOT the
        # first block, the LLM almost certainly renamed a variable between
        # blocks instead of re-declaring it identically.
        if total_blocks > 1 and block_idx > 1:
            return (
                f"NameError in Block {block_idx}/{total_blocks}: '{varname}' is not defined. "
                f"CRITICAL: each ```python``` block runs in a FRESH namespace — "
                f"variables from Block 1 are NOT visible here. You MUST re-declare "
                f"EVERY parameter at the top of EVERY block using IDENTICAL names "
                f"from the canonical naming table. Common drift patterns to avoid: "
                f"major_d vs major_diameter / diameter / d; "
                f"shank_h vs shank_length / length / L; "
                f"pitch vs thread_pitch / p; "
                f"head_h vs head_height / hh; "
                f"thread_h vs thread_length / tl; "
                f"teeth_n vs num_teeth / n_teeth. "
                f"Regenerate keeping variable names CONSISTENT across all blocks. "
                f"If '{varname}' refers to a FreeCAD object created earlier, re-fetch it: "
                f"{varname} = doc.getObject('ObjectName')."
            )

        # Single-block "forgot to fetch" heuristic — if the undefined name
        # looks like a document object (capitalized, Cyrillic, or contains
        # object-ish tokens) the LLM probably assumed it was "in scope" from
        # the current document state and never fetched it. Prompt with the
        # concrete corrective.
        _obj_tokens = (
            "sphere", "cube", "box", "cylinder", "cone", "torus", "prism",
            "wedge", "shank", "head", "bolt", "gear", "wheel", "hub", "rim",
            "shaft", "axis", "body", "fuse", "cut",
            # common Russian object names the LLM tends to use:
            "сфер", "куб", "шайб", "гайк", "болт", "колес", "обод",
            "шкаф", "дверь", "ручк", "столешн",
        )
        _looks_like_object = (
            varname and (
                varname[0].isupper()
                or not varname.isascii()                   # Cyrillic etc.
                or any(tok in varname.lower() for tok in _obj_tokens)
            )
        )
        if _looks_like_object:
            return (
                f"NameError: '{varname}' is not defined. This name looks like a "
                f"document object the user expects to already exist — but you "
                f"never fetched it into a Python variable. FreeCAD objects in "
                f"the current document are NOT auto-bound to Python names; you "
                f"must explicitly do: "
                f"`{varname} = doc.getObject('<NameInDocument>')` at the top of "
                f"your block. The name in the document's object tree may differ "
                f"from your Python variable — check the exact label. If the "
                f"object does not exist yet, create it first via "
                f"`doc.addObject('Part::Sphere', '<Name>')` (or the appropriate "
                f"type) before assigning properties."
            )

        # Otherwise — generic scoping / carry-over diagnosis.
        return (
            f"NameError: '{varname}' is not defined. Common causes: "
            f"(1) Variable defined inside an 'if' / 'for' block but used outside its scope — "
            f"move declarations unconditionally to the top of the script; "
            f"(2) Variable from a previous user request — re-declare it here, "
            f"or retrieve the existing FreeCAD object via obj = doc.getObject('ObjectName'); "
            f"(3) Typo — check spelling against your own earlier definitions."
        )
    if "unit mismatch" in error_lower or "quantity::operator" in error_lower:
        return (
            "Arithmetic failed: FreeCAD Quantity unit mismatch. "
            "Reading object properties (e.g. box.Height, cyl.Radius) returns a Quantity, not a float. "
            "Use your own numeric variables for calculations instead of reading properties back, "
            "or wrap with float(): e.g. float(box.Height)."
        )
    if "'partdesign.feature' object has no attribute" in error_lower:
        return (
            "'PartDesign::Feature' is not a valid FreeCAD object type. "
            "For a raw shape container use doc.addObject('Part::Feature', 'Name'). "
            "For PartDesign operations use body.newObject('PartDesign::Pad', ...) etc."
        )
    # Sprint 5.20: common ViewObject attribute errors — LLM confusing display-
    # side providers (ViewProviderDraftText, ViewProviderAnnotation) with
    # Part-shape providers (ViewProviderPartExt).
    if "viewprovider" in error_lower and "has no attribute" in error_lower:
        import re as _re
        m = _re.search(r"has no attribute '(\w+)'", error)
        bad_attr = m.group(1) if m else ""
        if bad_attr in ("FontSize", "FontName", "TextSize", "TextColor",
                        "LabelText", "Justification"):
            return (
                f"ViewObject AttributeError: Part/PartDesign shape ViewProviders "
                f"do NOT expose text properties like '{bad_attr}'. "
                "You cannot 'print' a letter by setting FontSize on a Part::Box. "
                "For 3D text use the PART VII recipe: "
                "Draft.make_shapestring(String=char, FontFile=neurocad_default_font(), "
                "Size=N) → Part::Extrusion of the returned wire into a solid. "
                "The resulting extrusion's ViewObject has ShapeColor, Transparency, "
                "LineWidth — but NO FontSize (font is baked into the outline)."
            )
        return (
            f"ViewObject AttributeError: the property '{bad_attr}' does not "
            f"exist on this object's ViewProvider. Common valid Part/PartDesign "
            f"ViewObject properties: ShapeColor (tuple of 3 floats 0..1), "
            f"Transparency (0..100 int), LineWidth (float), Visibility (bool), "
            f"DisplayMode ('Flat Lines'/'Shaded'/'Wireframe'). "
            f"In headless execution, some ViewObject changes may silently no-op."
        )
    if "rotation constructor" in error_lower:
        return (
            "Wrong FreeCAD.Rotation() constructor arguments. Valid forms: "
            "Rotation(FreeCAD.Vector(axis), degrees), "
            "Rotation(yaw_deg, pitch_deg, roll_deg), "
            "Rotation(x, y, z, w) for quaternion. "
            "Do NOT pass a plain tuple or a single float."
        )
    if "list index out of range" in error_lower:
        return (
            "IndexError: list index out of range. Common FreeCAD causes: "
            "(1) edge.Vertexes[1] on a closed circular/arc edge — circular edges "
            "have only 1 vertex; iterate with `for v in edge.Vertexes` or check "
            "`len(edge.Vertexes) >= 2` first. "
            "(2) shape.Faces[0] on a wire or compound without faces. "
            "(3) doc.Objects[i] when the document is empty. "
            "Always validate collection length before index access."
        )
    if "sketchobject" in error_lower and "has no attribute 'support'" in error_lower:
        return (
            "Sketch attachment failed: 'Sketcher.SketchObject' has no attribute 'Support'. "
            "In FreeCAD 1.x the property was RENAMED: use sk.AttachmentSupport, NOT sk.Support. "
            "Correct sequence: "
            "(1) body = doc.addObject('PartDesign::Body', ...); doc.recompute(); "
            "(2) sk = doc.addObject('Sketcher::SketchObject', ...); body.addObject(sk); "
            "(3) sk.AttachmentSupport = (body.Origin, ['XY_Plane']); "
            "(4) sk.MapMode = 'FlatFace'. "
            "Alternatively, avoid PartDesign::Body entirely and use Part WB "
            "(Part::Revolution, Part::Extrusion) — more reliable in headless scripts."
        )
    if "must be bool, not int" in error_lower or "argument 2 must be bool" in error_lower:
        return (
            "TypeError: a boolean argument received an integer. "
            "FreeCAD C++ bindings require Python True/False, not 1/0. "
            "Common cases: "
            "makePipeShell(sections, makeSolid=True, isFrenet=True) — both flags must be bool; "
            "Part::Revolution/Extrusion Solid property: feat.Solid = True (not 1); "
            "makePipeShell positional form: wire.makePipeShell([profile], True, True). "
            "Replace every integer 1/0 used as a boolean flag with True/False."
        )
    if "cannot create polygon" in error_lower and "vertices" in error_lower:
        return (
            "Polygon creation failed: a polygon needs at least 2 (open) or 3 "
            "(closed) vertices. Common causes: "
            "(1) the vertex list was filtered down to 0/1 points by a `if`/`continue` "
            "in the construction loop; "
            "(2) Draft.make_polygon([pt]) — must be a list of ≥ 2 Vectors; "
            "(3) Part.makePolygon([]) — empty list; "
            "(4) Part.makeWireFromVertices used on a single vertex. "
            "Guard the build with `if len(points) < 2: continue` and assert the "
            "length BEFORE the constructor call."
        )
    if "range() arg 3 must not be zero" in error_lower:
        return (
            "ValueError: range() step must not be zero. The step argument was "
            "computed as 0 — typically from rounding or `int(small_float)`. "
            "Defensive pattern: `step = max(1, int(round(spacing)))` before "
            "the range call. If you need a non-integer step, use a `while` "
            "loop or `numpy.arange` semantics: "
            "`x = start; while x < stop: ...; x += step` with `assert step != 0`."
        )
    if "failed to create face from wire" in error_lower:
        return (
            "Part.Face(wire) failed: OCCT could not build a face from the wire. "
            "Common causes: "
            "(1) wire is NOT closed — call `wire.isClosed()` (must be True); "
            "(2) wire has self-intersections — `wire.isValid()` returns False; "
            "(3) wire is non-planar — all vertices must lie in one plane "
            "(use `Part.Plane().toShape().fix(0.01, 0.01)` to test); "
            "(4) duplicate consecutive points — Part.Wire treats them as "
            "degenerate edges. "
            "Fix: ensure last vertex == first vertex (close the polygon), "
            "drop duplicates, and project all points onto a single plane "
            "before Part.Face(wire)."
        )
    if (
        "unsupported format string passed to base.quantity" in error_lower
        or "quantity.__format__" in error_lower
    ):
        return (
            "TypeError: FreeCAD Quantity does not implement Python format-specs "
            "(no `f'{q:.2f}'`). Use `.Value` first: `f'{obj.Length.Value:.2f}'` "
            "or `f'{float(obj.Length.Value):.2f}'`. "
            "Whole-string formatting also breaks: `str(obj.Length)` works but "
            "yields `'24.0 mm'` (units included). Prefer the numeric path "
            "when computing geometry; reserve string formatting for "
            "human-readable logs only."
        )
    if "assertionerror" in error_lower or error_lower.strip().startswith("assert"):
        return (
            "AssertionError raised by an assertion in the generated code. "
            "Read the error message — it tells you exactly which invariant "
            "was violated (e.g. 'edge count: got 48 expected 80' or "
            "'Wheel is too solid: density=1.02 (max 0.30)'). Re-emit the "
            "code with the underlying logic fixed: iterate the correct "
            "number of dimensions, build hollow rims via Part::Cut(outer, "
            "inner) instead of solid Part::Cylinder, etc. Do NOT delete the "
            "assertion — it is a contract."
        )
    if (
        "either three floats" in error_lower
        or ("vector" in error_lower and "expected" in error_lower)
    ):
        return (
            "FreeCAD.Vector accepts exactly 3 scalars (x, y, z) — higher- or "
            "lower-dimensional coordinates raise this TypeError. For nD math "
            "visualizations: project to 3D first (drop extra dims or apply a "
            "3×nD projection matrix). Pattern: "
            "`v = FreeCAD.Vector(*coord[:3])` if you only need the first three "
            "components. See PART VI of the system prompt (wireframe / "
            "math-visualization recipe) for a worked nD → 3D example."
        )
    return f"Execution failed: {error}"


def _contains_refusal_intent(text: str) -> bool:
    """Return True if the user prompt contains unsupported file/import/resource keywords."""
    lower = text.lower()
    return any(re.search(rf'\b{re.escape(kw)}\b', lower) for kw in REFUSAL_KEYWORDS)


def _log_status(msg: str, notifications: list[str], callbacks: AgentCallbacks) -> None:
    """Emit status to Report View, collect it for per-attempt audit, and call UI callback."""
    log_notify(msg)
    notifications.append(msg)
    callbacks.on_status(msg)


def _complete_with_timeout(adapter, messages, system: str, timeout_s: float | None = None):
    """Run adapter.complete() with a hard timeout guard."""
    if timeout_s is None:
        timeout_s = float(getattr(adapter, "timeout", 120.0))
    payload: dict[str, object] = {"response": None, "error": None}

    def _target():
        try:
            payload["response"] = adapter.complete(messages, system=system)
        except Exception as exc:  # pragma: no cover - exercised through caller
            payload["error"] = exc

    thread = threading.Thread(target=_target, daemon=True, name="NeuroCad-LLMCall")
    thread.start()
    thread.join(timeout=timeout_s)
    if thread.is_alive():
        raise TimeoutError(f"LLM request timed out after {timeout_s:.0f}s")
    if payload["error"] is not None:
        raise payload["error"]  # type: ignore[misc]
    return payload["response"]


def _execute_with_rollback(code: str, doc) -> ExecResult:
    """Execute code inside a FreeCAD transaction named 'NeuroCAD'.

    Rolls back the transaction if execution fails or geometry is invalid.
    """
    log_info("agent.exec", "opening FreeCAD transaction", document=getattr(doc, "Name", None))
    doc.openTransaction("NeuroCAD")  # type: ignore
    try:
        result = execute(code, doc)
        if not result.ok:
            log_warn("agent.exec", "execution failed, aborting transaction", error=result.error)
            doc.abortTransaction()  # type: ignore
            # Increment rollback count because transaction was aborted
            return ExecResult(
                ok=False,
                new_objects=result.new_objects,
                error=result.error,
                rollback_count=result.rollback_count + 1
            )

        # Validate each new object
        for obj_name in result.new_objects:
            obj = doc.getObject(obj_name)
            if obj is None:
                continue
            validation = validate(obj)
            if not validation.ok:
                log_warn(
                    "agent.exec",
                    "validation failed, aborting transaction",
                    object_name=obj_name,
                    error=validation.error,
                )
                doc.abortTransaction()  # type: ignore
                return ExecResult(
                    ok=False,
                    new_objects=[],
                    error=f"Validation failed for {obj_name}: {validation.error}",
                    rollback_count=1
                )

        # Everything OK – commit
        log_info(
            "agent.exec",
            "execution and validation succeeded, committing transaction",
            new_objects=result.new_objects,
        )
        doc.commitTransaction()  # type: ignore
        return result
    except Exception as e:
        log_error(
            "agent.exec",
            "unexpected exception during execution, aborting transaction",
            error=e,
            traceback=traceback.format_exc(),
        )
        doc.abortTransaction()  # type: ignore
        return ExecResult(ok=False, new_objects=[], error=f"Unexpected error: {e}")


def run(
    text: str,
    doc,
    adapter,
    history: History,
    callbacks: AgentCallbacks | None = None,
) -> AgentResult:
    """Run the agent loop: LLM → code extraction → execution → validation.

    If callbacks is None, the agent runs synchronously (no streaming).
    Otherwise, callbacks are invoked as appropriate.
    """
    use_callbacks = callbacks is not None
    if callbacks is None:
        callbacks = AgentCallbacks()

    # Add user message to history
    history.add(Role.USER, text)
    log_info("agent.run", "history updated with user prompt", text=text)
    log_notify("history updated")
    callbacks.on_status("history updated")
    # Audit log
    audit_log(
        "agent_start",
        {
            "user_prompt_preview": text,
            "provider": getattr(adapter, "provider", type(adapter).__name__),
            "model": getattr(adapter, "model", "unknown"),
            "document_name": getattr(doc, "Name", None),
        },
        correlation_id=get_correlation_id(),
    )

    # Early refusal for file/import/external-resource intents
    if _contains_refusal_intent(text):
        log_info("agent.run", "early refusal for file/import/external-resource intent", text=text)
        log_notify("unsupported file/import/external-resource operation")
        callbacks.on_status("unsupported file/import/external-resource operation")
        # Audit log
        audit_log(
            "agent_error",
            {
                "error_type": "early_refusal",
                "user_prompt_preview": text,
                "provider": getattr(adapter, "provider", type(adapter).__name__),
                "model": getattr(adapter, "model", "unknown"),
                "document_name": getattr(doc, "Name", None),
                "attempts": 0,
                "error": (
                    "Unsupported operation: file/import/external-resource "
                    "operations are not supported."
                ),
            },
            correlation_id=get_correlation_id(),
        )
        return AgentResult(
            ok=False,
            attempts=0,
            error=(
                "Unsupported operation: file/import/external-resource operations are not supported."
            ),
            new_objects=[],
            rollback_count=0,
        )

    # Build system prompt from document snapshot
    from .context import capture
    snap = capture(doc)
    system = build_system(snap)
    log_info(
        "agent.run",
        "system prompt built",
        system_chars=len(system),
        object_count=len(snap.objects),
    )
    log_notify("system prompt ready", objects=len(snap.objects))
    callbacks.on_status(f"system prompt ready, objects={len(snap.objects)}")

    MAX_RETRIES = 3
    attempts = 0
    last_error = None
    total_rollback_count = 0

    while attempts < MAX_RETRIES:
        attempts += 1
        attempt_notifications: list[str] = []
        log_info("agent.run", "starting attempt", attempt=attempts, max_retries=MAX_RETRIES)
        callbacks.on_attempt(attempts, MAX_RETRIES)
        _log_status(f"attempt {attempts}/{MAX_RETRIES}", attempt_notifications, callbacks)

        # Get LLM response
        try:
            messages = history.to_llm_messages()
            log_info(
                "agent.run",
                "sending request to adapter.complete",
                message_count=len(messages),
                provider=type(adapter).__name__,
            )
            _log_status("sending request to LLM", attempt_notifications, callbacks)
            # Sprint 2 uses a single complete() call. Streaming is deferred.
            response = _complete_with_timeout(adapter, messages, system=system)
            llm_text = response.content
            log_info(
                "agent.run",
                "received LLM response",
                chars=len(llm_text),
                stop_reason=response.stop_reason,
                output_tokens=response.output_tokens,
            )
            _log_status(f"LLM response received, chars={len(llm_text)}", attempt_notifications, callbacks)
            if use_callbacks:
                callbacks.on_chunk(llm_text)
        except Exception as e:
            log_error("agent.run", "adapter call failed", error=e)
            _log_status(f"LLM call failed: {e}", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "ok": False,
                    "error": str(e),
                    "error_category": "llm_transport",
                    "new_object_names": [],
                    "block_count": 0,
                    "rollback_count": 0,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Final error audit log
            audit_log(
                "agent_error",
                {
                    "error_type": "llm_call_failed",
                    "user_prompt_preview": text,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "error": str(e),
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=False,
                attempts=attempts,
                error=f"LLM error: {e}",
                new_objects=[],
                rollback_count=0,
            )

        # Extract code blocks
        # Sprint 5.18: detect truncation BEFORE trying to parse blocks. If the
        # provider reports stop_reason == "length" the code is almost certainly
        # cut mid-statement, and the downstream SyntaxError is unhelpful —
        # surface the real cause to the LLM so it can split / shorten next time.
        _stop = (response.stop_reason or "").lower()
        if _stop in ("length", "max_tokens"):
            truncation_note = (
                f"Your previous response was TRUNCATED at {len(llm_text)} chars "
                f"because it hit the max_tokens ceiling (stop_reason={_stop!r}). "
                "The tail of your code is missing, which is why any syntax "
                "error you may see next is bogus. Fix options: "
                "(1) split the work into 2–3 fenced ```python``` blocks per the "
                "Multi-block protocol — each block is sent in a SEPARATE "
                "response, so the token budget resets; "
                "(2) drop comments and repetitive placement boilerplate; "
                "(3) parameterize + loop instead of repeating similar boxes. "
                "Do NOT just re-emit the same long block — it will truncate again."
            )
            history.add(Role.FEEDBACK, truncation_note)
            log_warn(
                "agent.run",
                "LLM response truncated at max_tokens",
                attempt=attempts,
                chars=len(llm_text),
            )
            _log_status(
                f"LLM response truncated ({len(llm_text)} chars) — retrying",
                attempt_notifications, callbacks,
            )
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text,
                    "ok": False,
                    "error": f"LLM response truncated (stop_reason={_stop})",
                    "error_category": "truncated",
                    "new_object_names": [],
                    "block_count": 0,
                    "rollback_count": 0,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            if attempts < MAX_RETRIES:
                continue
            audit_log(
                "agent_error",
                {
                    "error_type": "truncated",
                    "user_prompt_preview": text,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "error": f"LLM response truncated (stop_reason={_stop})",
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=False,
                attempts=attempts,
                error=f"LLM response truncated at max_tokens (stop_reason={_stop})",
                new_objects=[],
                rollback_count=0,
            )

        blocks = extract_code_blocks(llm_text)
        log_info("agent.run", "code blocks extracted", block_count=len(blocks))
        _log_status(f"code extracted, blocks={len(blocks)}", attempt_notifications, callbacks)
        if not blocks:
            # Sprint 5.16: treat "no code generated" as a RETRIABLE failure,
            # not a fatal dead-end. When a previous attempt failed (e.g.
            # shape-invalid), the LLM sometimes returns prose explaining
            # the problem instead of new code. A stronger feedback + retry
            # usually recovers.
            last_error = "No code generated"
            history.add(
                Role.FEEDBACK,
                "No executable Python code was found in your last response. "
                "The ONLY valid response is a fenced ```python``` block. "
                "Do NOT apologize, do NOT describe the problem, do NOT ask "
                "for clarification — re-emit the complete code with the fix "
                "applied. If the previous attempt failed validation, fix the "
                "specific line the feedback pointed at and emit the whole "
                "program again.",
            )
            log_warn("agent.run", "LLM returned no executable code",
                     attempt=attempts, max_retries=MAX_RETRIES)
            _log_status("LLM returned no executable code — retrying",
                        attempt_notifications, callbacks)
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text,
                    "ok": False,
                    "error": "No code generated",
                    "error_category": "no_code",
                    "new_object_names": [],
                    "block_count": 0,
                    "rollback_count": 0,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            if attempts < MAX_RETRIES:
                # Retry — do NOT emit final agent_error yet, loop continues.
                continue
            # Retries exhausted — fall through to the max_retries_exhausted
            # audit at the end of the function.
            audit_log(
                "agent_error",
                {
                    "error_type": "no_code_generated",
                    "user_prompt_preview": text,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "block_count": 0,
                    "error": "No code generated",
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=False,
                attempts=attempts,
                error="No code generated",
                new_objects=[],
                rollback_count=0,
            )

        # Execute each block sequentially
        all_new_objects: list[str] = []
        block_rollback_count = 0
        overall_ok = True
        block_error = None
        block_category = None
        block_feedback = None
        failed_block_idx: int | None = None

        for idx, block in enumerate(blocks, start=1):
            log_info(
                "agent.run",
                "executing block",
                block_idx=idx,
                total_blocks=len(blocks),
                preview=block[:200],
            )
            _log_status(f"executing block {idx}/{len(blocks)}", attempt_notifications, callbacks)

            if use_callbacks:
                # Delegate execution to UI thread
                log_info("agent.run", "delegating block execution to UI thread", attempt=attempts)
                exec_result_dict = callbacks.on_exec_needed(block, attempts)
                exec_result = ExecResult(
                    ok=exec_result_dict.get("ok", False),
                    new_objects=exec_result_dict.get("new_objects", []),
                    error=exec_result_dict.get("error"),
                    rollback_count=exec_result_dict.get("rollback_count", 0),
                )
            else:
                # Direct execution
                exec_result = _execute_with_rollback(block, doc)

            block_rollback_count += exec_result.rollback_count

            if exec_result.ok:
                # Block succeeded – accumulate new objects
                all_new_objects.extend(exec_result.new_objects)
                continue
            else:
                # Block failed – stop execution of subsequent blocks
                overall_ok = False
                block_error = exec_result.error
                if block_error is None:
                    block_error = "Unknown error"
                block_category = _categorize_error(block_error)
                block_feedback = _make_feedback(
                    block_error,
                    block_category,
                    block_idx=idx,
                    total_blocks=len(blocks),
                )
                failed_block_idx = idx
                log_warn(
                    "agent.run",
                    "block execution failed",
                    block_idx=idx,
                    error=block_error,
                    category=block_category,
                )
                _log_status(f"block {idx} failed: {block_feedback}", attempt_notifications, callbacks)
                break

        total_rollback_count += block_rollback_count

        if overall_ok:
            # All blocks succeeded – add assistant response to history
            history.add(Role.ASSISTANT, llm_text)
            log_info(
                "agent.run",
                "attempt succeeded",
                attempt=attempts,
                new_objects=all_new_objects,
                block_count=len(blocks),
            )
            _log_status("execution succeeded", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text,
                    "code_preview": blocks[0] if blocks else "",
                    "ok": True,
                    "error": None,
                    "error_category": None,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "rollback_count": block_rollback_count,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Final success audit log
            audit_log(
                "agent_success",
                {
                    "user_prompt_preview": text,
                    "llm_response_preview": llm_text,
                    "code_preview": blocks[0] if blocks else "",
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "rollback_count": total_rollback_count,
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=True,
                attempts=attempts,
                new_objects=all_new_objects,
                rollback_count=total_rollback_count,
            )
        else:
            # At least one block failed
            last_error = block_error
            category = block_category
            feedback = block_feedback
            assert feedback is not None
            assert last_error is not None
            assert category is not None

            # Fast-exit: user cancellation — do not retry.
            if last_error.strip().lower().startswith("cancelled"):
                log_info(
                    "agent.run",
                    "cancelled by user — exiting retry loop",
                    attempt=attempts,
                )
                audit_log(
                    "agent_error",
                    {
                        "error_type": "cancelled_by_user",
                        "user_prompt_preview": text,
                        "provider": getattr(adapter, "provider", type(adapter).__name__),
                        "model": getattr(adapter, "model", "unknown"),
                        "document_name": getattr(doc, "Name", None),
                        "attempts": attempts,
                        "error": "Cancelled by user",
                        "rollback_count": total_rollback_count,
                    },
                    correlation_id=get_correlation_id(),
                )
                return AgentResult(
                    ok=False,
                    attempts=attempts,
                    error="Cancelled by user",
                    new_objects=[],
                    rollback_count=total_rollback_count,
                )

            # Fast-exit: handoff timeout — the same heavy code will just time
            # out again on retry, so do not waste tokens.
            if category == "timeout" and "handoff" in last_error.lower():
                log_info(
                    "agent.run",
                    "handoff timeout — exiting retry loop",
                    attempt=attempts,
                )
                audit_log(
                    "agent_error",
                    {
                        "error_type": "handoff_timeout",
                        "user_prompt_preview": text,
                        "provider": getattr(adapter, "provider", type(adapter).__name__),
                        "model": getattr(adapter, "model", "unknown"),
                        "document_name": getattr(doc, "Name", None),
                        "attempts": attempts,
                        "error": last_error,
                        "rollback_count": total_rollback_count,
                    },
                    correlation_id=get_correlation_id(),
                )
                return AgentResult(
                    ok=False,
                    attempts=attempts,
                    error=feedback,
                    new_objects=[],
                    rollback_count=total_rollback_count,
                )

            history.add(Role.FEEDBACK, feedback)
            log_warn(
                "agent.run",
                "attempt failed",
                attempt=attempts,
                error=last_error,
                category=category,
            )
            _log_status(f"execution failed: {feedback}", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text,
                    "code_preview": blocks[0] if blocks else "",
                    "ok": False,
                    "error": last_error,
                    "error_category": category,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "failed_block_idx": failed_block_idx,
                    "rollback_count": block_rollback_count,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Retry loop continues — blocked_token and unsupported_api are
            # self-correctable: feedback is already in history, LLM can fix on next attempt.

    # All retries exhausted
    error_msg = f"Max retries exceeded: {last_error}" if last_error else "Max retries exceeded"
    # Audit log
    audit_log(
        "agent_error",
        {
            "error_type": "max_retries_exhausted",
            "user_prompt_preview": text,
            "llm_response_preview": llm_text if 'llm_text' in locals() else "",
            "code_preview": (blocks[0] if blocks else "") if 'blocks' in locals() else "",
            "provider": getattr(adapter, "provider", type(adapter).__name__),
            "model": getattr(adapter, "model", "unknown"),
            "document_name": getattr(doc, "Name", None),
            "attempts": attempts,
            "error": error_msg,
            "last_error": last_error,
            "rollback_count": total_rollback_count,
        },
        correlation_id=get_correlation_id(),
    )
    return AgentResult(
        ok=False,
        attempts=attempts,
        error=error_msg,
        new_objects=[],
        rollback_count=total_rollback_count,
    )
