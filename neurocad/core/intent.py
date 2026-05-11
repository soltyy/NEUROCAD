"""Design-intent schema — the structured contract extracted from a user prompt.

Two-pass LLM architecture (Sprint 5.24+):
    LLM-1 (intent extractor) reads the user's free-form prompt and produces
    a `DesignIntent` — a list of `Part` records with their dimensions,
    features and joints, all named/derived from engineering standards the
    LLM already knows (ISO, ГОСТ, ASTM, DIN, СП, ...).

    LLM-2 (code generator) reads the `DesignIntent` and emits FreeCAD code.

    The post-execution verifier reads the SAME `DesignIntent` and calls
    generic feature detectors against the resulting geometry — no hardcoded
    per-class anti-patterns in the validator layer.

Schema is intentionally narrow at the start (MVP). Each new engineering
domain (mechanics, architecture, сопромат) extends the `Feature` enum and
the corresponding generic detector, NOT the validator file.

Why Pydantic — strict validation when LLM-1 returns malformed JSON: the
agent treats a parse failure as "intent extraction failed, retry" rather
than silently passing junk to LLM-2.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Primitive types
# ---------------------------------------------------------------------------

class Quantity(BaseModel):
    """A physical scalar with units.

    All values are normalized to SI in mm-units convention used by FreeCAD:
        length      → millimetres
        mass        → grams
        force       → newtons
        pressure    → megapascals (= N/mm²)
        time        → seconds
        angle       → degrees

    Accepts LLM-friendly shorthand: a plain number (`12000`) or string
    («12 mm», «4.5», «90 deg») is auto-coerced to `Quantity(value=…, unit=…)`.
    """
    value: float
    unit: str = "mm"
    tol: float | None = Field(default=None,
                              description="± tolerance in same unit; None=default ±5 %")

    @model_validator(mode="before")
    @classmethod
    def _coerce_scalar(cls, data: Any) -> Any:
        if isinstance(data, (int, float)):
            return {"value": float(data), "unit": "mm"}
        if isinstance(data, str):
            m = re.match(r"^\s*([+\-]?\d*\.?\d+)\s*([a-zA-Zа-яА-Я°]*)\s*$", data)
            if m:
                return {"value": float(m.group(1)), "unit": (m.group(2) or "mm")}
        return data


class Standard(BaseModel):
    """Reference to an engineering standard (ISO, ГОСТ, DIN, ASTM, СП, …)."""
    family: str               # "ISO", "ГОСТ", "DIN", "ASTM", "СП"
    number: str               # "4014", "33200-2014", "262", …
    grade: str | None = None  # "8.8", "РУ1-Ш", "Grade B", …


# ---------------------------------------------------------------------------
# Features — abstract geometric / engineering claims the agent must verify
# ---------------------------------------------------------------------------

class Feature(BaseModel):
    """A single verifiable claim about a part.

    The `kind` discriminator routes the verifier to a generic detector in
    `neurocad.core.features` (e.g. `kind="axle_hole"` → `has_hole_at_axis(...)`).
    `params` is a free-form dict the detector reads; the verifier does NOT
    interpret it.

    Examples:
        Feature(kind="axle_hole",  params={"radius_min_mm": 4.0})
        Feature(kind="thread",     params={"axis": "Z", "pitch_mm": 3.0,
                                            "length_mm": 30.0,
                                            "major_d_mm": 24.0})
        Feature(kind="hex_head",   params={"across_flats_mm": 36.0})
        Feature(kind="hollow_rim", params={"max_density": 0.30})
        Feature(kind="stepped_axial_profile",
                params={"distinct_radii": [65.0, 82.5, 97.0]})
    """
    kind: str
    params: dict = Field(default_factory=dict)


class Joint(BaseModel):
    """Required connection between two named parts.

    `mode` describes the connection type:
        "touch":   surfaces must be coincident (distToShape ≤ tol)
        "inside":  one part must be entirely inside another (e.g. spheres in container)
        "coaxial": shared axis with optional tolerance
        "coplanar":shared plane
    """
    a: str                                                # part name
    b: str                                                # part name
    mode: Literal["touch", "inside", "coaxial", "coplanar"]
    tol_mm: float = 0.5


# ---------------------------------------------------------------------------
# Part — one component of the assembly
# ---------------------------------------------------------------------------

class Part(BaseModel):
    """One identifiable part of the assembly (or the whole, if single-part)."""
    name: str                                             # e.g. "Bolt", "Rim", "Spoke_00"
    type: str                                             # "bolt", "gear", "wheel", "axle", "house", …
    standard: Standard | None = None
    dimensions: dict[str, Quantity] = Field(default_factory=dict)
    features: list[Feature] = Field(default_factory=list)
    material: str | None = None                            # "steel", "aluminum", …


# ---------------------------------------------------------------------------
# Loads — for mechanics / сопромат / FEA
# ---------------------------------------------------------------------------

class Load(BaseModel):
    """An applied load for FEA. The verifier may run CalculiX afterwards."""
    on_part: str
    kind: Literal["force", "pressure", "moment", "fixed"]
    magnitude: float                                       # N, MPa, N·mm, or 0 for "fixed"
    direction: tuple[float, float, float] | None = None    # unit vector; None ↔ fixed


# ---------------------------------------------------------------------------
# DesignIntent — the full extracted contract
# ---------------------------------------------------------------------------

class DesignIntent(BaseModel):
    """Top-level contract extracted from a user prompt.

    Built by `intent_extractor.extract(prompt, llm)`, consumed by
    `contract_verifier.verify(intent, doc)` and (optionally) by the
    code-generation LLM-2 as a structured input.

    Round-trip: every successful agent run can serialize the intent next
    to its audit-log entry, so a future system can replay verification
    against an updated detector library without re-prompting the LLM.
    """
    prompt: str
    parts: list[Part]
    joints: list[Joint] = Field(default_factory=list)
    loads: list[Load] = Field(default_factory=list)
    notes: str | None = None                               # LLM-1's free-text rationale


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def empty_intent(prompt: str) -> DesignIntent:
    """Bootstrap an empty intent — used as the agent's fallback when LLM-1
    cannot or refuses to extract a contract."""
    return DesignIntent(prompt=prompt, parts=[])
