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
    if not hasattr(obj, "Shape"):
        return ValidationResult(ok=True)  # no shape to validate

    shape = obj.Shape
    if shape.isNull():
        return ValidationResult(ok=False, error="Shape is null")
    if not shape.isValid():
        return ValidationResult(ok=False, error="Shape is invalid")

    # Additional check: shape type (optional)
    # Could also check volume > 0 etc.

    return ValidationResult(ok=True)
