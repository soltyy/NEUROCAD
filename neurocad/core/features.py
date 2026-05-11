"""Generic geometric feature detectors.

Each detector takes a FreeCAD `Shape` (+ optional params) and returns a
`DetectionResult`. They are pure — no doc state, no LLM, no recipe-specific
knowledge. The `contract_verifier` composes them based on the `DesignIntent`.

Adding a new detector ≠ adding domain knowledge to the agent — only to the
detector library. Compare against the OLD approach where every new object
class required new code in `validator.py` AND `defaults.py` AND tests AND
harness.

Detector signature contract:
    def detect_<kind>(shape, **params) -> DetectionResult

Result fields:
    ok       — does the shape satisfy the claim?
    measured — what was actually measured (dict for diagnostics)
    reason   — short explanation when `ok` is False
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    ok: bool
    measured: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


def _bbox(shape):
    """Return (xLen, yLen, zLen, cx, cy, cz) from a shape. Caller is
    responsible for passing a real FreeCAD.Shape."""
    bb = shape.BoundBox
    return (float(bb.XLength), float(bb.YLength), float(bb.ZLength),
            float((bb.XMin + bb.XMax) / 2), float((bb.YMin + bb.YMax) / 2),
            float((bb.ZMin + bb.ZMax) / 2))


# ---------------------------------------------------------------------------
# 1. Dimensions
# ---------------------------------------------------------------------------

def detect_bbox_extent(shape, *, axis: str, value_mm: float,
                       tol_mm: float = 0.5) -> DetectionResult:
    """Confirm the shape's bbox extent along `axis` matches `value_mm`."""
    xLen, yLen, zLen, *_ = _bbox(shape)
    measured = {"x": xLen, "y": yLen, "z": zLen}[axis.lower()]
    return DetectionResult(
        ok=abs(measured - value_mm) <= tol_mm,
        measured={"axis": axis, "measured_mm": measured, "expected_mm": value_mm,
                  "tol_mm": tol_mm},
        reason=(None if abs(measured - value_mm) <= tol_mm
                else f"{axis}-extent {measured:.1f} ≠ {value_mm:.1f} ± {tol_mm:.1f} mm"),
    )


def detect_aspect_ratio(shape, *, axis_long: str, ratio_min: float = 5.0
                        ) -> DetectionResult:
    """Confirm shape is elongated along `axis_long` (e.g. axles, columns)."""
    xLen, yLen, zLen, *_ = _bbox(shape)
    lens = {"x": xLen, "y": yLen, "z": zLen}
    long_len = lens[axis_long.lower()]
    perp = max(v for k, v in lens.items() if k != axis_long.lower())
    if perp <= 0:
        return DetectionResult(ok=False, reason="degenerate bbox")
    r = long_len / perp
    return DetectionResult(
        ok=r >= ratio_min,
        measured={"long": long_len, "perp": perp, "ratio": r},
        reason=(None if r >= ratio_min
                else f"aspect ratio {r:.2f} < {ratio_min} along {axis_long}"),
    )


# ---------------------------------------------------------------------------
# 2. Holes / cutouts
# ---------------------------------------------------------------------------

def detect_axial_hole(shape, *, axis: str = "Z",
                      radius_min_mm: float = 1.0,
                      sample_n_angles: int = 8) -> DetectionResult:
    """Confirm a hole exists along `axis` through the centroid.

    Samples `sample_n_angles` points on a small circle of radius
    `radius_min_mm` around the centroid at mid-axis depth; if all are
    OUTSIDE the solid, the hole is present.
    """
    try:
        import FreeCAD  # type: ignore[import-not-found]
    except Exception:
        return DetectionResult(ok=False, reason="FreeCAD module unavailable")
    xLen, yLen, zLen, cx, cy, cz = _bbox(shape)
    inside_count = 0
    for i in range(sample_n_angles):
        ang = 2.0 * math.pi * i / sample_n_angles
        if axis.lower() == "z":
            pt = FreeCAD.Vector(cx + radius_min_mm * math.cos(ang),
                                cy + radius_min_mm * math.sin(ang), cz)
        elif axis.lower() == "x":
            pt = FreeCAD.Vector(cx, cy + radius_min_mm * math.cos(ang),
                                cz + radius_min_mm * math.sin(ang))
        else:                                            # y
            pt = FreeCAD.Vector(cx + radius_min_mm * math.cos(ang), cy,
                                cz + radius_min_mm * math.sin(ang))
        try:
            if shape.isInside(pt, 0.01, True):
                inside_count += 1
        except Exception:
            return DetectionResult(ok=False, reason="isInside raised")
    frac = inside_count / sample_n_angles
    return DetectionResult(
        ok=frac < 0.20,
        measured={"axis": axis, "inside_fraction": frac,
                  "test_radius_mm": radius_min_mm},
        reason=(None if frac < 0.20
                else f"no through-hole on {axis} axis: {inside_count}/"
                     f"{sample_n_angles} sample points inside at r={radius_min_mm:.1f} mm"),
    )


# ---------------------------------------------------------------------------
# 3. Thread (helical groove on a cylindrical surface)
# ---------------------------------------------------------------------------

def detect_thread(shape, *, axis: str = "Z", pitch_mm: float = 1.0,
                  length_mm: float = 20.0,
                  major_d_mm: float = 10.0,
                  near_z_max: bool = True) -> DetectionResult:
    """Detect a helical thread along an axis.

    Samples a line of points parallel to `axis` at radius slightly less than
    `major_d_mm/2`. A threaded surface alternates inside/outside as the
    helix passes through. Expected runs ≈ length_mm / pitch_mm.

    `near_z_max=True` places the probe near the free end of the shank
    (Sprint 5.10 ISO convention).
    """
    try:
        import FreeCAD  # type: ignore[import-not-found]
    except Exception:
        return DetectionResult(ok=False, reason="FreeCAD module unavailable")
    bb = shape.BoundBox
    cx = (bb.XMin + bb.XMax) / 2.0
    cy = (bb.YMin + bb.YMax) / 2.0
    # Sample line: walk along axis at r = 0.95 * major_d/2 (= 0.475 * major_d)
    r_probe = 0.475 * major_d_mm
    if axis.lower() == "z":
        z_start = bb.ZMax - length_mm if near_z_max else bb.ZMin
        z_end = bb.ZMax if near_z_max else bb.ZMin + length_mm
        sample_n = max(8, int(length_mm / pitch_mm * 8))   # ≥ 8 samples per turn
        inside_pattern = []
        for i in range(sample_n):
            z = z_start + (z_end - z_start) * (i / max(1, sample_n - 1))
            # probe at angle 0 — thread crosses any radial line ≈ length/pitch times
            pt = FreeCAD.Vector(cx + r_probe, cy, z)
            try:
                inside_pattern.append(shape.isInside(pt, 0.01, True))
            except Exception:
                return DetectionResult(ok=False, reason="isInside raised")
    else:
        return DetectionResult(ok=False, reason=f"axis {axis!r} not yet supported")
    # Count rising edges (False→True transitions)
    runs = sum(
        1 for i in range(1, len(inside_pattern))
        if inside_pattern[i] and not inside_pattern[i - 1]
    )
    expected = length_mm / pitch_mm
    return DetectionResult(
        ok=runs >= expected * 0.5,                         # ≥ half the expected turns
        measured={"runs": runs, "expected_turns": expected,
                  "probe_radius_mm": r_probe},
        reason=(None if runs >= expected * 0.5
                else f"thread weak: {runs} axial inside-runs at r={r_probe:.1f} "
                     f"(expected ~{expected:.0f} for L={length_mm:.0f}, pitch={pitch_mm:.2f})"),
    )


# ---------------------------------------------------------------------------
# 4. Hex prism (e.g. bolt head)
# ---------------------------------------------------------------------------

def detect_hex_section(shape, *, axis: str = "Z",
                       across_flats_mm: float | None = None,
                       tol_mm: float = 0.5) -> DetectionResult:
    """Detect a hexagonal cross-section perpendicular to `axis`.

    A hex prism has a rectangular bbox with aspect ratio
    `across_corners / across_flats = 2/√3 ≈ 1.155`. A round cylinder has
    1.00. Tolerance band 1.08 < ratio < 1.30 catches hex (with chamfers /
    fillets perturbing slightly).
    """
    xLen, yLen, zLen, *_ = _bbox(shape)
    if axis.lower() == "z":
        a, b = xLen, yLen
    elif axis.lower() == "x":
        a, b = yLen, zLen
    else:
        a, b = xLen, zLen
    if a <= 0 or b <= 0:
        return DetectionResult(ok=False, reason="degenerate bbox")
    ratio = max(a, b) / min(a, b)
    flats_min = min(a, b)
    hex_aspect = 1.08 <= ratio <= 1.30
    if across_flats_mm is not None:
        flats_ok = abs(flats_min - across_flats_mm) <= tol_mm
    else:
        flats_ok = True
    return DetectionResult(
        ok=hex_aspect and flats_ok,
        measured={"aspect_ratio": ratio, "flats_min_mm": flats_min,
                  "axis": axis},
        reason=(None if (hex_aspect and flats_ok)
                else f"not hex: aspect={ratio:.2f} (need 1.08-1.30), "
                     f"flats={flats_min:.1f} (need {across_flats_mm} ± {tol_mm})")
                if across_flats_mm
                else f"not hex: aspect={ratio:.2f} (need 1.08-1.30)",
    )


# ---------------------------------------------------------------------------
# 5. Hollowness — what fraction of the bbox-equivalent solid is actually filled
# ---------------------------------------------------------------------------

def detect_hollow(shape, *, max_density: float = 0.30) -> DetectionResult:
    """Confirm shape is mostly empty inside its bbox-equivalent cylinder.

    Generic — works for wheels, tubes, hollow shells, picture frames.
    Equivalent solid cylinder = π · (max(xLen,yLen)/2)² · zLen.
    """
    xLen, yLen, zLen, *_ = _bbox(shape)
    xy = max(xLen, yLen)
    if xy <= 0 or zLen <= 0:
        return DetectionResult(ok=False, reason="degenerate bbox")
    v_solid = math.pi * (xy / 2.0) ** 2 * zLen
    if v_solid <= 0:
        return DetectionResult(ok=False, reason="zero v_solid")
    vol = float(shape.Volume)
    density = vol / v_solid
    return DetectionResult(
        ok=density <= max_density,
        measured={"volume_mm3": vol, "v_equiv_solid_mm3": v_solid,
                  "density": density, "max_density": max_density},
        reason=(None if density <= max_density
                else f"density={density:.2f} > {max_density} (too solid for hollow part)"),
    )


# ---------------------------------------------------------------------------
# 6. Stepped axial profile (e.g. ГОСТ axle with multiple diameters)
# ---------------------------------------------------------------------------

def detect_stepped_axial(shape, *, axis: str = "Z",
                          distinct_radii_mm: list[float] | None = None,
                          tol_mm: float = 3.0,
                          sample_n: int = 80,
                          n_angles: int = 16) -> DetectionResult:
    """Confirm the shape has multiple distinct radii along `axis`.

    If `distinct_radii_mm` is provided, each must appear at some Z level
    within `tol_mm`. Otherwise, just count distinct radius bands.
    """
    try:
        import FreeCAD  # type: ignore[import-not-found]
    except Exception:
        return DetectionResult(ok=False, reason="FreeCAD module unavailable")
    if axis.lower() != "z":
        return DetectionResult(ok=False, reason=f"axis {axis!r} not yet supported")
    bb = shape.BoundBox
    cx, cy = (bb.XMin + bb.XMax) / 2.0, (bb.YMin + bb.YMax) / 2.0
    r_max = max(bb.XLength, bb.YLength) / 2.0 * 1.05
    # Build a log-spaced radial grid (~30 levels):
    r_grid = []
    r = 0.5
    while r <= r_max:
        r_grid.append(r)
        r *= 1.05 if r > 5.0 else 1.10
    measured_radii = []
    for iz in range(sample_n):
        z = bb.ZMin + bb.ZLength * (iz / max(1, sample_n - 1))
        max_r_here = 0.0
        for r in r_grid:
            inside = False
            for ia in range(n_angles):
                ang = 2.0 * math.pi * ia / n_angles
                pt = FreeCAD.Vector(cx + r * math.cos(ang),
                                    cy + r * math.sin(ang), z)
                try:
                    if shape.isInside(pt, 0.01, True):
                        inside = True
                        break
                except Exception:
                    return DetectionResult(ok=False, reason="isInside raised")
            if inside:
                max_r_here = r
            else:
                if max_r_here > 0:
                    break
        if max_r_here > 0:
            measured_radii.append(max_r_here)
    # Bin radii into 5-mm bands
    bands: dict[float, int] = {}
    for r in measured_radii:
        b = round(r / 5.0) * 5.0
        bands[b] = bands.get(b, 0) + 1
    distinct = sorted(b for b, count in bands.items() if count >= 2)
    if distinct_radii_mm:
        missing = []
        for want in distinct_radii_mm:
            if not any(abs(want - got) <= tol_mm for got in distinct):
                missing.append(want)
        ok = not missing
        return DetectionResult(
            ok=ok,
            measured={"distinct_radii_observed": distinct, "wanted": distinct_radii_mm},
            reason=(None if ok else f"missing required radii: {missing}, observed {distinct}"),
        )
    # Otherwise just expect ≥ 3 distinct levels
    return DetectionResult(
        ok=len(distinct) >= 3,
        measured={"distinct_radii_observed": distinct},
        reason=(None if len(distinct) >= 3
                else f"only {len(distinct)} distinct radius bands, expected ≥ 3"),
    )


# ---------------------------------------------------------------------------
# Registry — verifier composes by feature.kind
# ---------------------------------------------------------------------------

DETECTORS = {
    "axle_hole":              detect_axial_hole,
    "axial_hole":             detect_axial_hole,        # alias
    "thread":                 detect_thread,
    "hex_head":               detect_hex_section,
    "hex_section":            detect_hex_section,        # alias
    "hollow_rim":             detect_hollow,
    "hollow":                 detect_hollow,             # alias
    "stepped_axial_profile":  detect_stepped_axial,
    "stepped_axial":          detect_stepped_axial,      # alias
    "bbox_length":            detect_bbox_extent,
    "long_axial":             detect_aspect_ratio,
}
