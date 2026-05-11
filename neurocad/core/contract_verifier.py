"""Declarative post-execution verifier.

Reads a `DesignIntent` and runs the generic detectors from `features.py`
against the resulting doc — no per-class hardcoded knowledge.

This is the replacement for the per-object anti-patterns we accumulated in
`validator.py` (wheel/axle/gear/house token-matching). Whereas `validator.py`
runs PER-OBJECT during exec and knows about specific name tokens, the
contract verifier runs ONCE after the full block finishes, takes the
intent extracted by LLM-1 as the source of truth, and calls a small,
generic library of detectors composed by feature kind.

Contract:
    verify(doc, intent) -> VerifyReport

VerifyReport carries:
    ok          — bool, overall pass/fail
    failures    — list of failed checks with the offending part + feature
    detail      — list of all per-check results, for diagnostics / audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .features import DETECTORS, DetectionResult
from .intent import DesignIntent, Part


# ---------------------------------------------------------------------------

@dataclass
class CheckRecord:
    part: str
    feature_kind: str
    result: DetectionResult


@dataclass
class VerifyReport:
    ok: bool
    failures: list[CheckRecord] = field(default_factory=list)
    detail: list[CheckRecord] = field(default_factory=list)

    def short_summary(self) -> str:
        if self.ok:
            return f"contract OK ({len(self.detail)} checks passed)"
        n_fail = len(self.failures)
        first = self.failures[0]
        return (
            f"contract failed: {n_fail}/{len(self.detail)} checks; "
            f"first: {first.part}.{first.feature_kind} — {first.result.reason}"
        )

    def to_feedback(self) -> str:
        """Format failures into an LLM-feedback message so the agent can retry."""
        if self.ok:
            return ""
        lines = ["Design-contract verification failed:"]
        for f in self.failures[:5]:
            lines.append(
                f"  • {f.part}.{f.feature_kind}: {f.result.reason}"
            )
        if len(self.failures) > 5:
            lines.append(f"  … and {len(self.failures) - 5} more")
        lines.append(
            "Fix the geometry so each listed claim holds. Re-emit the "
            "Python block with corrected parameters."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------

def _find_part_object(doc, part: Part):
    """Try to find the FreeCAD object that represents the part.

    Strategy (best-effort, order matters):
      1. Exact name match doc.getObject(part.name)
      2. Label substring match (Cyrillic OK)
      3. Object with TypeId matching expected (Part::Cut for "gear"/"wheel" final, etc.)
    Returns the object or None.
    """
    try:
        o = doc.getObject(part.name)
        if o is not None:
            return o
    except Exception:
        pass
    needle = part.name.lower()
    for o in getattr(doc, "Objects", []):
        try:
            n = (getattr(o, "Name", "") or "").lower()
            lbl = (getattr(o, "Label", "") or "").lower()
        except Exception:
            continue
        if needle in n or needle in lbl:
            return o
    return None


# ---------------------------------------------------------------------------

def verify(doc, intent: DesignIntent) -> VerifyReport:
    """Run every feature claim in `intent` against the resulting doc.

    For each `Part`:
      1. Locate the corresponding doc-object (by name → label → type heuristic)
      2. For each `Feature`: look up detector in DETECTORS by kind
      3. Pass `shape` + `**feature.params` to the detector
      4. Collect results

    Missing detectors are recorded as failures with reason="unknown feature kind"
    so the LLM-1 layer can be tightened over time.
    """
    detail: list[CheckRecord] = []
    failures: list[CheckRecord] = []

    for part in intent.parts:
        obj = _find_part_object(doc, part)
        if obj is None:
            rec = CheckRecord(
                part.name, "<lookup>",
                DetectionResult(ok=False, reason=f"part {part.name!r} not found in doc"),
            )
            detail.append(rec); failures.append(rec)
            continue

        # Verify dimensions — ONLY for parts that have NO declared features.
        # Rationale: if the part has features, the LLM has already stated
        # what to verify geometrically (thread, hex_head, hollow, ...).
        # Adding bbox-extent checks on top of that creates semantic conflict
        # — for example «болт длиной 60 mm» in ISO means shank length, not
        # total bbox Z (head adds ~15 mm). The features capture that intent
        # precisely; the dimensions field can stay informational.
        skip_dimensions = bool(part.features)
        BBOX_NAME_AXIS = {
            "length":     "z",
            "height":     "z",
            "z_length":   "z",
            "z_extent":   "z",
            "width":      "x",
            "x_length":   "x",
            "x_extent":   "x",
            "depth":      "y",
            "y_length":   "y",
            "y_extent":   "y",
        }
        for dim_name, q in part.dimensions.items():
            tol = q.tol if q.tol is not None else max(0.5, q.value * 0.05)
            dim_key = dim_name.lower().strip()
            axis = BBOX_NAME_AXIS.get(dim_key)
            shape = getattr(obj, "Shape", None)
            if shape is None:
                continue
            if skip_dimensions:
                rec = CheckRecord(
                    part.name, f"dim:{dim_name}",
                    DetectionResult(
                        ok=True,
                        measured={"skipped": True,
                                  "reason": "part has features — dimensions informational"},
                    ),
                )
                detail.append(rec)
                continue
            if axis is None:
                rec = CheckRecord(
                    part.name, f"dim:{dim_name}",
                    DetectionResult(
                        ok=True,
                        measured={"skipped": True, "reason": "non-bbox dimension"},
                    ),
                )
                detail.append(rec)
                continue
            try:
                res = DETECTORS["bbox_length"](
                    shape, axis=axis, value_mm=q.value, tol_mm=tol,
                )
            except Exception as exc:
                res = DetectionResult(ok=False, reason=f"detector raised: {exc!r}")
            rec = CheckRecord(part.name, f"dim:{dim_name}", res)
            detail.append(rec)
            if not res.ok:
                failures.append(rec)

        # Verify features
        for feat in part.features:
            detector = DETECTORS.get(feat.kind)
            if detector is None:
                rec = CheckRecord(
                    part.name, feat.kind,
                    DetectionResult(ok=False, reason=f"unknown feature kind {feat.kind!r}"),
                )
                detail.append(rec); failures.append(rec)
                continue
            shape = getattr(obj, "Shape", None)
            if shape is None:
                rec = CheckRecord(
                    part.name, feat.kind,
                    DetectionResult(ok=False, reason="no Shape on object"),
                )
                detail.append(rec); failures.append(rec)
                continue
            try:
                res = detector(shape, **feat.params)
            except Exception as exc:
                res = DetectionResult(
                    ok=False,
                    reason=f"detector {feat.kind!r} raised: {exc!r}",
                )
            rec = CheckRecord(part.name, feat.kind, res)
            detail.append(rec)
            if not res.ok:
                failures.append(rec)

    return VerifyReport(ok=not failures, failures=failures, detail=detail)
