"""Validate geometry after execution."""

from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of geometry validation."""
    ok: bool
    error: str | None = None


def validate(obj) -> ValidationResult:
    """Two‑stage validation: State then Shape."""
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
    
    # Additional check: shape type (optional)
    # Could also check volume > 0 etc.
    
    return ValidationResult(ok=True)
