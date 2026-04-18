"""Sprint 5.7 — static recipe verifier.

Parses DEFAULT_SYSTEM_PROMPT and verifies that every FreeCAD object type used
in doc.addObject(...) / body.newObject(...) constructors refers to a real
FreeCAD 1.x type. Catches typos, hallucinated types, and accidental
regressions like 'Part::LinearPattern' (which does NOT exist in Part WB).
"""

import re

import pytest

from neurocad.config.defaults import DEFAULT_SYSTEM_PROMPT

# FreeCAD 1.x document object types actually present in the bundled workbenches.
# Keep sorted alphabetically within each workbench for readability.
VALID_OBJECT_TYPES: frozenset[str] = frozenset({
    # Part WB ----------------------------------------------------------------
    "Part::Box",
    "Part::Chamfer",
    "Part::Circle",
    "Part::Common",
    "Part::Compound",
    "Part::Cone",
    "Part::Cut",
    "Part::Cylinder",
    "Part::Ellipse",
    "Part::Ellipsoid",
    "Part::Extrusion",
    "Part::Feature",
    "Part::Fillet",
    "Part::Fuse",
    "Part::Helix",
    "Part::Line",
    "Part::Loft",
    "Part::Mirror",
    "Part::Mirroring",
    "Part::MultiCommon",
    "Part::MultiFuse",
    "Part::Offset",
    "Part::Plane",
    "Part::Prism",
    "Part::Revolution",
    "Part::Sphere",
    "Part::Sweep",
    "Part::Thickness",
    "Part::Torus",
    "Part::Wedge",
    # PartDesign WB ----------------------------------------------------------
    "PartDesign::AdditiveLoft",
    "PartDesign::AdditivePipe",
    "PartDesign::Body",
    "PartDesign::Chamfer",
    "PartDesign::Draft",
    "PartDesign::Fillet",
    "PartDesign::Groove",
    "PartDesign::LinearPattern",
    "PartDesign::Mirrored",
    "PartDesign::MultiTransform",
    "PartDesign::Pad",
    "PartDesign::Pocket",
    "PartDesign::PolarPattern",
    "PartDesign::Revolution",
    "PartDesign::SubtractiveLoft",
    "PartDesign::SubtractivePipe",
    # Sketcher WB ------------------------------------------------------------
    "Sketcher::SketchObject",
    # Draft WB (for completeness — Draft WB uses Draft.make_* factories, but
    # the prompt may reference Draft::Wire etc. in examples)
    "Draft::Wire",
})


# Types that are explicitly blocked / non-existent. If any of these appears
# as a constructor argument inside a code-like region, the prompt is broken.
BLOCKED_OBJECT_TYPES: frozenset[str] = frozenset({
    "Part::LinearPattern",
    "Part::PolarPattern",
    "Part::MultiTransform",
    "Part::Array",
    # Sprint 5.8: InvoluteGear is NOT a stock FreeCAD 1.1 object type
    # (requires Gears Workbench addon). Recipes must use the Part WB gear
    # approximation (trapezoidal teeth + loop + makeCompound) instead.
    "PartDesign::InvoluteGear",
})


# Regexes for constructor arguments.
_ADDOBJECT_RE = re.compile(
    r'(?:doc|body|\w+)\.(?:addObject|newObject)\s*\(\s*["\']([A-Za-z]+::\w+)["\']'
)


def _extract_types(text: str) -> list[tuple[str, int]]:
    """Return list of (type_name, line_number) for every addObject/newObject call."""
    results: list[tuple[str, int]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in _ADDOBJECT_RE.finditer(line):
            results.append((m.group(1), idx))
    return results


def test_default_prompt_has_addobject_calls():
    """Sanity: the prompt contains a sensible number of constructor examples."""
    types = _extract_types(DEFAULT_SYSTEM_PROMPT)
    assert len(types) > 20, (
        f"Expected >20 addObject/newObject examples in the prompt, got {len(types)}. "
        "Either the regex is wrong or the prompt lost its code examples."
    )


def test_default_prompt_uses_only_valid_freecad_types():
    """Every doc.addObject(TYPE) / body.newObject(TYPE) in the prompt must use
    a real FreeCAD 1.x object type. Catches hallucinated types like
    Part::LinearPattern (which does NOT exist in Part WB).
    """
    unknown: list[tuple[str, int]] = []
    for type_name, line_num in _extract_types(DEFAULT_SYSTEM_PROMPT):
        if type_name not in VALID_OBJECT_TYPES:
            unknown.append((type_name, line_num))

    if unknown:
        formatted = "\n".join(f"  line {ln}: {t}" for t, ln in unknown)
        pytest.fail(
            "DEFAULT_SYSTEM_PROMPT contains unknown FreeCAD object types:\n"
            + formatted
            + "\n\nEither the type really exists and should be added to "
            "VALID_OBJECT_TYPES, or the prompt is recommending a "
            "hallucinated / non-existent type and must be fixed."
        )


def test_default_prompt_does_not_use_blocked_types_as_positive_examples():
    """BLOCKED_OBJECT_TYPES (Part::LinearPattern etc.) must not appear as a
    constructor argument anywhere in the prompt — not even as 'example' code.
    The LLM copies these literally and fails at runtime.
    """
    offenders: list[tuple[str, int]] = []
    for type_name, line_num in _extract_types(DEFAULT_SYSTEM_PROMPT):
        if type_name in BLOCKED_OBJECT_TYPES:
            offenders.append((type_name, line_num))

    if offenders:
        formatted = "\n".join(f"  line {ln}: {t}" for t, ln in offenders)
        pytest.fail(
            "DEFAULT_SYSTEM_PROMPT uses blocked/non-existent types as "
            "addObject/newObject arguments:\n"
            + formatted
            + "\n\nThese do NOT exist in the corresponding workbench. "
            "Replace with a Python loop + Part.makeCompound pattern."
        )


def test_default_prompt_mentions_blocked_types_as_warnings_only():
    """Blocked types should still appear in the prompt as 'does NOT exist'
    warnings (so the LLM knows why it failed) — just not as constructor args.
    """
    warning_mentions = dict.fromkeys(BLOCKED_OBJECT_TYPES, False)
    for t in BLOCKED_OBJECT_TYPES:
        if t in DEFAULT_SYSTEM_PROMPT:
            warning_mentions[t] = True

    # At least Part::LinearPattern should be mentioned as a warning.
    assert warning_mentions["Part::LinearPattern"], (
        "Part::LinearPattern should be mentioned in the prompt as a 'does NOT "
        "exist' warning, so the LLM knows why it fails and what to do instead."
    )


def test_default_prompt_includes_multi_block_protocol():
    """Sprint 5.7: the prompt must document the multi-block protocol for
    complex assemblies, otherwise the LLM keeps emitting 9000-char monoliths.
    """
    assert "Multi-block protocol" in DEFAULT_SYSTEM_PROMPT
    # Must explicitly reference fenced blocks.
    assert "```python" in DEFAULT_SYSTEM_PROMPT
    # Must mention handoff timeout to motivate the split.
    assert (
        "handoff" in DEFAULT_SYSTEM_PROMPT.lower()
        or "≤ 80 lines" in DEFAULT_SYSTEM_PROMPT
    )
    # Must mention that variables do not persist across blocks.
    assert "doc.getObject" in DEFAULT_SYSTEM_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
