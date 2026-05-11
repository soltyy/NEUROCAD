"""Validate geometry after execution."""

import math
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of geometry validation."""
    ok: bool
    error: str | None = None


_WHEEL_NAME_TOKENS = ("wheel", "колес", "велосип")
_AXLE_NAME_TOKENS = ("axle", "ось_", "ось ", "axleru", "wheelset")
_GEAR_NAME_TOKENS = ("gear", "шестер", "шестрен", "зубч")
_HOUSE_NAME_TOKENS = ("house", "дом_", "дом ", "building", "здани", "коттедж")


def _is_intermediate(obj) -> bool:
    """An object is an INTERMEDIATE if another object in the doc consumes it
    (it appears in some sibling's `InList`). Cut/Fuse/Compound inputs always
    fall here. Anti-pattern checks must skip intermediates — only the FINAL
    object in a build chain should be validated as a finished part.

    Example: a gear is built as
        GearDiscProf → GearDisc → GearFused → Gear  (Part::Cut adds bore)
    GearDisc and GearFused are intermediates (each appears in the next one's
    InList). Only `Gear` should be checked for "has central axle hole".
    """
    try:
        in_list = getattr(obj, "InList", None)
        if in_list is None:
            return False
        return any(getattr(o, "Name", None) for o in in_list)
    except Exception:
        return False


def _check_axle_anti_pattern(obj, shape) -> ValidationResult | None:
    """If an object looks like a wheelset axle (named "axle"/"ось"/etc), the
    final solid must NOT be a plain cylinder — it must have stepped diameters
    along Z (per ГОСТ 33200-2014). Detected by comparing the solid's actual
    volume to the equivalent plain cylinder of bbox xy × z. If the ratio
    is ≥ 0.95, the solid is essentially a uniform cylinder.

    Returns ValidationResult on FAIL, None if not applicable.
    """
    name = getattr(obj, "Name", "") or ""
    label = getattr(obj, "Label", "") or ""
    text = (name + " " + label).lower()
    if not any(tok in text for tok in _AXLE_NAME_TOKENS):
        return None
    bb = getattr(shape, "BoundBox", None)
    vol = getattr(shape, "Volume", None)
    if bb is None or vol is None:
        return None
    try:
        x_len = float(bb.XLength)
        y_len = float(bb.YLength)
        z_len = float(bb.ZLength)
        vol_f = float(vol)
    except Exception:
        return None
    # Need a long Z-axial profile: z_len ≥ 5 × max(x_len, y_len).
    xy_len = max(x_len, y_len)
    if xy_len < 10 or z_len < 5 * xy_len:
        return None
    v_plain = math.pi * (xy_len / 2.0) ** 2 * z_len
    if v_plain <= 0:
        return None
    ratio = vol_f / v_plain
    if ratio >= 0.95:
        return ValidationResult(
            ok=False,
            error=(
                f"Axle anti-pattern: '{name}' is a plain cylinder "
                f"(vol={vol_f:.0f} ≈ {ratio*100:.0f}% of plain cylinder "
                f"{v_plain:.0f} mm³). A real wheelset axle (ГОСТ РУ1-Ш) has "
                f"stepped diameters along Z (journals 130, pre-hub 165, hub 194, "
                f"middle 165). Build as Part::Revolution from a stepped 2D "
                f"profile wire. See PART VIII of the system prompt."
            ),
        )
    return None


def _check_house_anti_pattern(obj, shape) -> ValidationResult | None:
    """If an object is named like a house/building (`house`/`дом`/`здание`/
    etc.), the Z-extent must be physically plausible. A 2-storey residential
    building is typically 5-7 m tall; the absolute upper bound for any
    house-like prompt (including steep gabled roof, attic, porch step) is
    ~9 m. Anything above is the LLM piling up 4+ storey-heights, which is
    NOT what «дом 2 этажа» asks for.

    Returns ValidationResult on FAIL, None if not applicable.
    """
    name = getattr(obj, "Name", "") or ""
    label = getattr(obj, "Label", "") or ""
    text = (name + " " + label).lower()
    if not any(tok in text for tok in _HOUSE_NAME_TOKENS):
        return None
    bb = getattr(shape, "BoundBox", None)
    if bb is None:
        return None
    try:
        z_len = float(bb.ZLength)
    except Exception:
        return None
    # 9000 mm hard cap. Below 3000 mm is not really a house (single storey).
    if z_len > 9000.0:
        return ValidationResult(
            ok=False,
            error=(
                f"House anti-pattern: '{name}' is {z_len:.0f} mm tall — too "
                f"tall for any realistic 2-storey building (max ~9000 mm "
                f"including a steep gabled roof). Reduce ceiling heights to "
                f"≤ 3000 mm each, keep roof to 1000-1500 mm. See PART VIII "
                f"architectural defaults."
            ),
        )
    return None


def _check_gear_anti_pattern(obj, shape) -> ValidationResult | None:
    """If an object looks like a gear (named «gear»/«шестер»/«зубч»), the
    final solid must have a CENTRAL AXLE HOLE — real gears mount on a shaft.
    Detected by sampling `shape.isInside()` at small radii near the geometric
    centre (XY centroid, mid-Z). If the centre is inside the solid, the gear
    has no shaft hole.

    Returns ValidationResult on FAIL, None if not applicable.
    """
    name = getattr(obj, "Name", "") or ""
    label = getattr(obj, "Label", "") or ""
    text = (name + " " + label).lower()
    if not any(tok in text for tok in _GEAR_NAME_TOKENS):
        return None
    bb = getattr(shape, "BoundBox", None)
    if bb is None or not hasattr(shape, "isInside"):
        return None
    try:
        x_len = float(bb.XLength)
        y_len = float(bb.YLength)
        z_len = float(bb.ZLength)
        cx = (float(bb.XMin) + float(bb.XMax)) / 2.0
        cy = (float(bb.YMin) + float(bb.YMax)) / 2.0
        cz = (float(bb.ZMin) + float(bb.ZMax)) / 2.0
    except Exception:
        return None
    # Need a disc-like gear (xy ≈ yz, z << xy). Tall solids aren't gears.
    if x_len < 20 or y_len < 20:
        return None
    if abs(x_len - y_len) / max(x_len, y_len) > 0.25:
        return None
    if z_len > min(x_len, y_len) * 0.8:
        return None  # too tall to be a gear disc
    # Sample 8 points on a small circle around centre. If all are inside →
    # no axle hole.
    try:
        import FreeCAD  # type: ignore
    except Exception:
        return None
    outer_r = max(x_len, y_len) / 2.0
    test_r = max(1.0, outer_r * 0.05)
    inside = 0
    n = 8
    for i in range(n):
        ang = 2.0 * math.pi * i / n
        pt = FreeCAD.Vector(cx + test_r * math.cos(ang),
                            cy + test_r * math.sin(ang), cz)
        try:
            if shape.isInside(pt, 0.01, True):
                inside += 1
        except Exception:
            return None
    frac = inside / n
    if frac > 0.5:
        return ValidationResult(
            ok=False,
            error=(
                f"Gear anti-pattern: '{name}' has NO central axle hole "
                f"(at r≈{test_r:.1f} mm from centre, {inside}/{n} sample points "
                f"are inside the solid). Real gears mount on a shaft — build the "
                f"final gear as Part::Cut(toothed_disc, axle_cylinder) where "
                f"axle_cylinder.Radius = bore_d/2 (typically 0.20–0.35 of the "
                f"pitch diameter). See PART V / PART VIII recipes."
            ),
        )
    return None


def _check_wheel_anti_pattern(obj, shape) -> ValidationResult | None:
    """If an object looks like an assembled wheel (named "wheel"/"колес"/
    "велосип"), the final solid must NOT be a flat disc — its volume must be
    < 50 % of the equivalent solid cylinder of the same outer diameter and
    Z thickness. Catches the common LLM failure of building a wheel from
    overlapping Part::Cylinder primitives instead of a Part::Cut hollow rim.

    Returns ValidationResult on FAIL, None if not applicable.
    """
    name = getattr(obj, "Name", "") or ""
    label = getattr(obj, "Label", "") or ""
    text = (name + " " + label).lower()
    if not any(tok in text for tok in _WHEEL_NAME_TOKENS):
        return None
    bb = getattr(shape, "BoundBox", None)
    vol = getattr(shape, "Volume", None)
    if bb is None or vol is None:
        return None
    try:
        x_len = float(bb.XLength)
        y_len = float(bb.YLength)
        z_len = float(bb.ZLength)
        vol_f = float(vol)
    except Exception:
        return None
    # Need a plausibly disc-shaped bbox: xLen ≈ yLen, both ≥ 10 mm.
    if x_len < 10 or y_len < 10 or z_len <= 0:
        return None
    if abs(x_len - y_len) / max(x_len, y_len) > 0.20:
        return None
    # A wheel-shaped solid: long axis is X or Y, not Z. (z_len << xy_len.)
    xy_len = max(x_len, y_len)
    if z_len > xy_len * 0.50:
        return None  # this is a tall solid, not a wheel disc
    v_solid = math.pi * (xy_len / 2.0) ** 2 * z_len
    if v_solid <= 0:
        return None
    density = vol_f / v_solid
    if density >= 0.50:
        return ValidationResult(
            ok=False,
            error=(
                f"Wheel anti-pattern: '{name}' has density={density:.2f} "
                f"(vol={vol_f:.0f} mm³, equivalent solid cylinder "
                f"={v_solid:.0f} mm³). A real wheel is HOLLOW — build the "
                f"rim as Part::Cut(outer_cylinder, inner_cylinder), then "
                f"add a small hub + thin spokes. See PART VIII of the "
                f"system prompt for the canonical recipe."
            ),
        )
    return None


def validate(obj) -> ValidationResult:
    """Two‑stage validation: State then Shape, plus anti-pattern checks."""
    # Stage 1: check obj.State for error/invalid flags
    if hasattr(obj, "State"):
        state = obj.State
        # State can be a list of strings or a single string
        if isinstance(state, list):
            if any("error" in s.lower() or "invalid" in s.lower() for s in state):
                return ValidationResult(
                    ok=False,
                    error=f"Object state indicates error: {state}"
                )
        elif isinstance(state, str) and ("error" in state.lower() or "invalid" in state.lower()):
            return ValidationResult(
                ok=False,
                error=f"Object state indicates error: {state}"
            )

    # Stage 2: check Shape
    # Determine which shape to validate
    shape_to_check = None
    # For PartDesign::Body, use Tip.Shape if available
    is_partdesign_body = hasattr(obj, "TypeId") and isinstance(obj.TypeId, str) and "PartDesign::Body" in obj.TypeId
    if is_partdesign_body and hasattr(obj, "Tip") and obj.Tip is not None and hasattr(obj.Tip, "Shape") and obj.Tip.Shape is not None:
        shape_to_check = obj.Tip.Shape
    elif hasattr(obj, "Shape") and obj.Shape is not None:
        shape_to_check = obj.Shape

    if shape_to_check is None:
        return ValidationResult(ok=True)  # no shape to validate

    if shape_to_check.isNull():
        return ValidationResult(ok=False, error="Shape is null")
    if not shape_to_check.isValid():
        return ValidationResult(ok=False, error="Shape is invalid")

    # Stage 3: anti-pattern checks. Skip intermediates (objects consumed by
    # another) — they are mid-pipeline constructions, not finished parts.
    if _is_intermediate(obj):
        return ValidationResult(ok=True)
    wheel_anti = _check_wheel_anti_pattern(obj, shape_to_check)
    if wheel_anti is not None:
        return wheel_anti
    axle_anti = _check_axle_anti_pattern(obj, shape_to_check)
    if axle_anti is not None:
        return axle_anti
    gear_anti = _check_gear_anti_pattern(obj, shape_to_check)
    if gear_anti is not None:
        return gear_anti
    house_anti = _check_house_anti_pattern(obj, shape_to_check)
    if house_anti is not None:
        return house_anti

    return ValidationResult(ok=True)
