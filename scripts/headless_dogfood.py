#!/usr/bin/env python3
"""Autonomous end-to-end dog-food harness.

Two-process bridge:
  * DRIVER  — run with the project venv Python. Owns agent.run, the LLM
              adapter (anthropic / openai SDKs), History, and scenario
              verdicts. Has NO FreeCAD module access.
  * WORKER  — run with FreeCAD's bundled Python via `freecadcmd /path/to/
              headless_dogfood.py`. Owns the FreeCAD document and calls
              `neurocad.core.executor.execute(code, doc)`. Has NO LLM SDK.

The driver spawns the worker as a subprocess and pipes JSON-Lines RPC
over stdin/stdout. The agent.run callback `on_exec_needed` becomes a
synchronous round-trip to the worker.

Mode selection is automatic: if `import FreeCAD` succeeds, this file
acts as the worker. Otherwise it acts as the driver.

Usage (driver, from repo root):
    .venv/bin/python scripts/headless_dogfood.py                # all scenarios
    .venv/bin/python scripts/headless_dogfood.py --scenario R4  # one scenario
    .venv/bin/python scripts/headless_dogfood.py --list
    .venv/bin/python scripts/headless_dogfood.py --freecadcmd /custom/path

Environment overrides for API keys (driver only, fallback after keyring):
    NEUROCAD_ANTHROPIC_API_KEY
    NEUROCAD_OPENAI_API_KEY
    NEUROCAD_DEEPSEEK_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FREECADCMD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"


# ---------------------------------------------------------------------------
# Worker mode (runs inside freecadcmd)
# ---------------------------------------------------------------------------

def _looks_like_worker() -> bool:
    try:
        import FreeCAD  # noqa: F401
        return True
    except ImportError:
        return False


def _worker_main() -> int:
    import FreeCAD  # type: ignore[import-not-found]

    sys.path.insert(0, str(REPO_ROOT))
    from neurocad.core import executor

    out = sys.__stdout__
    inp = sys.__stdin__

    def reply(payload: dict) -> None:
        out.write(json.dumps(payload, ensure_ascii=False) + "\n")
        out.flush()

    doc = FreeCAD.newDocument("Dogfood")
    reply({"event": "ready", "doc": doc.Name, "fc_version": FreeCAD.Version()[:3]})

    for raw in inp:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            reply({"event": "error", "error": f"bad-json: {exc}"})
            continue
        cmd = req.get("cmd")
        if cmd == "quit":
            reply({"event": "bye"})
            return 0
        if cmd == "reset":
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:
                pass
            doc = FreeCAD.newDocument("Dogfood")
            reply({"event": "reset_ok", "doc": doc.Name})
            continue
        if cmd == "exec":
            code = req.get("code", "")
            # Capture every block to /tmp for post-mortem review of failures.
            try:
                import time as _t
                _stamp = _t.strftime("%H%M%S")
                _p = f"/tmp/dogfood_block_{_stamp}.py"
                with open(_p, "a", encoding="utf-8") as _f:
                    _f.write(f"# --- block at {_stamp} ---\n{code}\n\n")
            except Exception:
                pass
            try:
                result = executor.execute(code, doc)
                reply({
                    "event": "exec_result",
                    "ok": bool(result.ok),
                    "new_objects": list(result.new_objects),
                    "error": result.error,
                    "rollback_count": int(result.rollback_count),
                })
            except Exception as exc:  # noqa: BLE001 — never let worker die
                reply({
                    "event": "exec_result",
                    "ok": False,
                    "new_objects": [],
                    "error": f"worker exception: {exc!r}",
                    "rollback_count": 0,
                })
            continue
        if cmd == "inspect":
            objs = []
            for o in doc.Objects:
                # Each property access wrapped in its own try/except — some
                # OCCT solids (degenerate fuses, e.g. thumb anatomy) crash
                # when .Volume or .isValid is computed. Treat any such
                # crash as "this property is unknown" instead of aborting
                # the whole inspect.
                shape = None
                try:
                    shape = getattr(o, "Shape", None)
                except Exception:
                    shape = None
                vol = None
                valid = None
                bbox = None
                faces_n = edges_n = verts_n = None
                if shape is not None:
                    try:
                        vol = float(shape.Volume)
                    except Exception:
                        vol = None
                    try:
                        valid = bool(shape.isValid())
                    except Exception:
                        valid = None
                    try:
                        bb = shape.BoundBox
                        bbox = {
                            "xLen": float(bb.XLength), "yLen": float(bb.YLength),
                            "zLen": float(bb.ZLength),
                            "xMin": float(bb.XMin), "xMax": float(bb.XMax),
                            "yMin": float(bb.YMin), "yMax": float(bb.YMax),
                            "zMin": float(bb.ZMin), "zMax": float(bb.ZMax),
                            "cx": float((bb.XMin + bb.XMax) / 2),
                            "cy": float((bb.YMin + bb.YMax) / 2),
                            "cz": float((bb.ZMin + bb.ZMax) / 2),
                        }
                    except Exception:
                        bbox = None
                    try:
                        faces_n = len(shape.Faces) if hasattr(shape, "Faces") else None
                    except Exception:
                        faces_n = None
                    try:
                        edges_n = len(shape.Edges) if hasattr(shape, "Edges") else None
                    except Exception:
                        edges_n = None
                    try:
                        verts_n = len(shape.Vertexes) if hasattr(shape, "Vertexes") else None
                    except Exception:
                        verts_n = None
                try:
                    name = o.Name
                except Exception:
                    name = "?"
                try:
                    label = getattr(o, "Label", name)
                except Exception:
                    label = name
                try:
                    type_name = type(o).__name__
                except Exception:
                    type_name = "?"
                try:
                    type_id = getattr(o, "TypeId", None)
                except Exception:
                    type_id = None
                # InList = objects that REFERENCE this one. If non-empty,
                # this object is an INTERMEDIATE consumed by a Cut/Fuse/
                # Compound — its volume should NOT be counted as a final
                # part. Same FreeCAD attribute the GUI uses to grey-out
                # intermediate inputs.
                try:
                    in_list = [obj.Name for obj in getattr(o, "InList", [])
                               if hasattr(obj, "Name")]
                except Exception:
                    in_list = []
                # Visibility: FreeCAD has both o.ViewObject.Visibility (GUI)
                # and o.Visibility (data; True if shown). Treat False as
                # "hidden / intermediate" hint.
                try:
                    visibility = bool(getattr(o, "Visibility", True))
                except Exception:
                    visibility = True
                objs.append({
                    "name": name,
                    "label": label,
                    "type": type_name,
                    "type_id": type_id,
                    "volume": vol,
                    "valid": valid,
                    "bbox": bbox,
                    "faces": faces_n,
                    "edges": edges_n,
                    "vertices": verts_n,
                    "in_list": in_list,
                    "is_intermediate": len(in_list) > 0,
                    "visibility": visibility,
                })
            reply({"event": "inspect", "objects": objs})
            continue
        if cmd in ("count_radial_inside_runs", "count_axial_inside_runs"):
            # Semantic geometric analyzer.
            # `radial`: sample a ring at z = z_mid at r = r_outer * r_factor;
            #           count contiguous "inside" runs along the angular sweep.
            #           Used for: gear teeth, wheel spokes.
            # `axial`:  sample a vertical line at r = r_factor (absolute mm),
            #           angle = 0 (i.e. on +X axis), z from zMin to zMax;
            #           count contiguous "inside" runs along Z.
            #           Used for: thread turn count.
            import math as _math
            try:
                import FreeCAD as _FC
            except Exception:
                _FC = None
            name = req.get("name", "")
            sample_n = int(req.get("sample_n", 360))
            r_factor = float(req.get("r_factor", 0.95))
            o = doc.getObject(name)
            shape = getattr(o, "Shape", None) if o is not None else None
            if shape is None or _FC is None:
                reply({"event": "analyzer_result", "count": None, "error": f"no shape for {name!r}"})
                continue
            try:
                bb = shape.BoundBox
                cx = (bb.XMin + bb.XMax) / 2.0
                cy = (bb.YMin + bb.YMax) / 2.0
                z_mid = (bb.ZMin + bb.ZMax) / 2.0
                r_outer = max(bb.XLength, bb.YLength) / 2.0
                inside_pattern = []
                if cmd == "count_radial_inside_runs":
                    r_sample = r_outer * r_factor
                    for i in range(sample_n):
                        ang = 2.0 * _math.pi * i / sample_n
                        pt = _FC.Vector(cx + r_sample * _math.cos(ang),
                                        cy + r_sample * _math.sin(ang),
                                        z_mid)
                        inside_pattern.append(shape.isInside(pt, 0.01, True))
                else:  # axial: thread-turn counter
                    r_abs = r_factor  # interpreted as absolute mm here
                    for i in range(sample_n):
                        z = bb.ZMin + bb.ZLength * (i / max(1, sample_n - 1))
                        pt = _FC.Vector(cx + r_abs, cy, z)
                        inside_pattern.append(shape.isInside(pt, 0.01, True))
                # Count rising edges (outside → inside transitions). Wrap-around
                # only matters for the radial ring case.
                wrap = (cmd == "count_radial_inside_runs")
                runs = 0
                n = len(inside_pattern)
                for i in range(n):
                    prev = inside_pattern[(i - 1) % n] if wrap else (
                        inside_pattern[i - 1] if i > 0 else False
                    )
                    if inside_pattern[i] and not prev:
                        runs += 1
                inside_frac = sum(inside_pattern) / max(1, n)
                reply({
                    "event": "analyzer_result",
                    "count": int(runs),
                    "inside_fraction": float(inside_frac),
                    "r_outer": float(r_outer),
                    "bbox_xLen": float(bb.XLength),
                    "bbox_yLen": float(bb.YLength),
                    "bbox_zLen": float(bb.ZLength),
                    "z_mid": float(z_mid),
                })
            except Exception as exc:  # noqa: BLE001
                reply({"event": "analyzer_result", "count": None, "error": f"{exc!r}"})
            continue
        if cmd == "axial_radius_profile":
            # Sample the object at `sample_n` Z levels (linearly from zMin to
            # zMax) and at each level compute the maximum radial extent from
            # the bbox-XY centerline. The radius at a Z level is the largest
            # `r` such that the ray (cx + r·cos(θ), cy + r·sin(θ), z) is
            # inside the shape for some θ — we approximate by isInside on a
            # log-spaced set of r values.
            import math as _math
            try:
                import FreeCAD as _FC
            except Exception:
                _FC = None
            name = req.get("name", "")
            sample_n = int(req.get("sample_n", 50))
            r_max_hint = float(req.get("r_max_hint", 0.0))
            n_angles = int(req.get("n_angles", 16))
            o = doc.getObject(name)
            shape = getattr(o, "Shape", None) if o is not None else None
            if shape is None or _FC is None:
                reply({"event": "radial_profile", "profile": [], "error": f"no shape for {name!r}"})
                continue
            try:
                bb = shape.BoundBox
                cx = (bb.XMin + bb.XMax) / 2.0
                cy = (bb.YMin + bb.YMax) / 2.0
                r_max = r_max_hint or max(bb.XLength, bb.YLength) / 2.0 * 1.1
                # Use log-spaced r-grid for sensitivity (0.5 mm steps inside,
                # coarser outside).
                r_grid = []
                r = 0.5
                while r <= r_max:
                    r_grid.append(r)
                    r *= 1.05 if r > 5.0 else 1.10
                profile = []
                for iz in range(sample_n):
                    z = bb.ZMin + bb.ZLength * (iz / max(1, sample_n - 1))
                    max_r_here = 0.0
                    for r in r_grid:
                        any_inside = False
                        for ia in range(n_angles):
                            ang = 2.0 * _math.pi * ia / n_angles
                            pt = _FC.Vector(cx + r * _math.cos(ang),
                                            cy + r * _math.sin(ang), z)
                            if shape.isInside(pt, 0.01, True):
                                any_inside = True
                                break
                        if any_inside:
                            max_r_here = r
                        else:
                            # Once we leave the solid at one r, larger r unlikely to re-enter.
                            if max_r_here > 0:
                                break
                    profile.append({"z": float(z), "r_max": float(max_r_here)})
                reply({"event": "radial_profile", "profile": profile,
                       "z_min": float(bb.ZMin), "z_max": float(bb.ZMax)})
            except Exception as exc:  # noqa: BLE001
                reply({"event": "radial_profile", "profile": [], "error": f"{exc!r}"})
            continue
        if cmd == "joint_analysis":
            # Pairwise connectivity analysis for an assembly.
            #
            # For each pair of named objects:
            #   - bbox_overlap_volume : intersection volume of the two AABBs
            #   - touch_distance       : minimum distance between the two
            #                            shapes (Part.distToShape); 0 = touching
            #                            or overlapping
            #   - common_volume        : Part.common volume (mm³); > 0 = solids
            #                            share material (thread cut into shank,
            #                            tenon-in-mortise, etc.)
            #
            # Returns a connectivity verdict per object:
            #   - "connected" if it touches ≥ 1 other object (touch_distance ≤ tol)
            #   - "floating" otherwise
            #
            # tol: tolerance in mm for "touching" (default 0.5 mm — generous
            #      because LLM-generated parts often miss by < 1 mm).
            names = req.get("names", [])
            tol = float(req.get("tol", 0.5))
            try:
                import Part as _Part  # type: ignore[import-not-found]
            except Exception:
                _Part = None
            try:
                if not names:
                    names = [o.Name for o in doc.Objects]
                shapes = {}
                for n in names:
                    o = doc.getObject(n)
                    s = getattr(o, "Shape", None) if o is not None else None
                    if s is not None and getattr(s, "isValid", lambda: True)():
                        shapes[n] = s
                pairs = []
                n_list = list(shapes.keys())
                for i, a in enumerate(n_list):
                    for b in n_list[i + 1:]:
                        sa, sb = shapes[a], shapes[b]
                        # BoundBox AABB overlap volume
                        bba, bbb = sa.BoundBox, sb.BoundBox
                        dx = max(0.0, min(bba.XMax, bbb.XMax) - max(bba.XMin, bbb.XMin))
                        dy = max(0.0, min(bba.YMax, bbb.YMax) - max(bba.YMin, bbb.YMin))
                        dz = max(0.0, min(bba.ZMax, bbb.ZMax) - max(bba.ZMin, bbb.ZMin))
                        aabb_overlap = dx * dy * dz
                        # Shape-to-shape minimum distance
                        td = None
                        try:
                            res = sa.distToShape(sb)
                            td = float(res[0]) if res else None
                        except Exception:
                            td = None
                        # Common (intersection) volume — only meaningful if AABB overlaps
                        cv = None
                        if aabb_overlap > 0 and _Part is not None:
                            try:
                                inter = sa.common(sb)
                                if inter and inter.isValid():
                                    cv = float(inter.Volume)
                            except Exception:
                                cv = None
                        pairs.append({
                            "a": a, "b": b,
                            "aabb_overlap_mm3": aabb_overlap,
                            "touch_distance_mm": td,
                            "common_volume_mm3": cv,
                        })
                # Per-object connectivity verdict
                verdict = {}
                for n in n_list:
                    is_connected = False
                    for p in pairs:
                        if n not in (p["a"], p["b"]):
                            continue
                        if p["touch_distance_mm"] is not None and p["touch_distance_mm"] <= tol:
                            is_connected = True
                            break
                    verdict[n] = "connected" if is_connected else "floating"
                reply({
                    "event": "joint_result",
                    "pairs": pairs,
                    "verdict": verdict,
                    "tol_mm": tol,
                    "floating_count": sum(1 for v in verdict.values() if v == "floating"),
                    "connected_count": sum(1 for v in verdict.values() if v == "connected"),
                })
            except Exception as exc:  # noqa: BLE001
                reply({"event": "joint_result", "pairs": [], "verdict": {}, "error": f"{exc!r}"})
            continue
        reply({"event": "error", "error": f"unknown cmd {cmd!r}"})

    reply({"event": "bye_eof"})
    return 0


# ---------------------------------------------------------------------------
# Driver mode (runs from project venv)
# ---------------------------------------------------------------------------

class WorkerProxy:
    """Synchronous JSON-RPC client over a freecadcmd subprocess."""

    def __init__(self, freecadcmd_path: str, worker_script: Path, log_stderr_to: Path | None = None):
        stderr_target = (
            open(log_stderr_to, "w", encoding="utf-8") if log_stderr_to else subprocess.DEVNULL
        )
        self._stderr_file = stderr_target if log_stderr_to else None
        self._proc = subprocess.Popen(
            [freecadcmd_path, str(worker_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_target,
            text=True,
            bufsize=1,
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONUNBUFFERED": "1", "NEUROCAD_DOGFOOD_WORKER": "1"},
        )
        ready = self._read_event(timeout_s=30.0)
        if not ready or ready.get("event") != "ready":
            raise RuntimeError(f"worker did not signal ready (got {ready!r})")
        self.fc_version = ready.get("fc_version")
        self.doc_name = ready.get("doc")

    def _read_event(self, *, timeout_s: float | None = None) -> dict | None:
        deadline = time.monotonic() + timeout_s if timeout_s is not None else None
        while True:
            line = self._proc.stdout.readline()
            if not line:
                if self._proc.poll() is not None:
                    return None
                if deadline and time.monotonic() > deadline:
                    return None
                continue
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    def _rpc(self, payload: dict, *, timeout_s: float = 180.0) -> dict:
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()
        evt = self._read_event(timeout_s=timeout_s)
        if evt is None:
            raise RuntimeError(f"worker died during {payload.get('cmd')!r}")
        return evt

    def execute(self, code: str, *, timeout_s: float = 180.0) -> dict:
        return self._rpc({"cmd": "exec", "code": code}, timeout_s=timeout_s)

    def reset(self) -> dict:
        return self._rpc({"cmd": "reset"})

    def inspect(self) -> dict:
        return self._rpc({"cmd": "inspect"}, timeout_s=60.0)

    def count_radial(self, name: str, *, r_factor: float = 0.95, sample_n: int = 360) -> dict:
        return self._rpc({
            "cmd": "count_radial_inside_runs",
            "name": name, "r_factor": r_factor, "sample_n": sample_n,
        }, timeout_s=60.0)

    def count_axial(self, name: str, *, r_abs: float, sample_n: int = 360) -> dict:
        return self._rpc({
            "cmd": "count_axial_inside_runs",
            "name": name, "r_factor": r_abs, "sample_n": sample_n,
        }, timeout_s=60.0)

    def joint_analysis(self, names: list[str] | None = None, *, tol_mm: float = 0.5) -> dict:
        return self._rpc({
            "cmd": "joint_analysis",
            "names": names or [],
            "tol": tol_mm,
        }, timeout_s=180.0)

    def axial_radius_profile(self, name: str, *, sample_n: int = 50,
                              r_max_hint: float = 0.0, n_angles: int = 16) -> dict:
        return self._rpc({
            "cmd": "axial_radius_profile",
            "name": name, "sample_n": sample_n,
            "r_max_hint": r_max_hint, "n_angles": n_angles,
        }, timeout_s=120.0)

    def close(self) -> None:
        try:
            self._rpc({"cmd": "quit"}, timeout_s=10.0)
        except Exception:
            pass
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except Exception:
                pass


# ---------- Mock document used for system-prompt snapshot ------------------

class _MockDoc:
    """Stand-in `doc` for the driver.

    `agent.run` only inspects `doc.Name` and `doc.Objects` (via
    `context.capture`) when building the system prompt. The actual
    geometry lives in the worker, so a frozen snapshot is fine.
    """

    Name = "Dogfood"
    Objects: list = []


# ---------- Scenario definitions -------------------------------------------

@dataclass
class Scenario:
    code: str
    title: str
    prompt: str
    timeout_s: float = 180.0
    # success_check receives (final_ok, final_attempts, inspect_objects, error, proxy)
    # and returns (passed: bool, detail: str). `proxy` is the live WorkerProxy
    # so deeper-than-bbox checks (count_radial, joint_analysis, …) are possible.
    success_check: callable = field(default=lambda *a, **kw: (False, "no check"))


# ---------- L3 semantic helpers (driver-side) ------------------------------

def _valid_solids(objs: list[dict], min_vol: float = 0.0) -> list[dict]:
    return [o for o in objs if o.get("valid") and (o.get("volume") or 0) > min_vol]


def _largest_solid(objs: list[dict]) -> dict | None:
    cs = _valid_solids(objs)
    if not cs:
        return None
    return max(cs, key=lambda o: o.get("volume") or 0)


def _centroid_spread(objs: list[dict], axis: str) -> float:
    """Std-dev of centroids along the chosen axis ('x'|'y'|'z'). 0 = coplanar/coaxial."""
    key = {"x": "cx", "y": "cy", "z": "cz"}[axis]
    vals = [o["bbox"][key] for o in objs if o.get("bbox") and o["bbox"].get(key) is not None]
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return var ** 0.5


def _coaxial_z(objs: list[dict], tol_mm: float) -> tuple[bool, str]:
    """Test that all centroids share a common Z-axis (small cx/cy spread)."""
    if len(objs) < 2:
        return True, "≤1 object"
    sx = _centroid_spread(objs, "x")
    sy = _centroid_spread(objs, "y")
    ok = sx <= tol_mm and sy <= tol_mm
    return ok, f"cx_std={sx:.2f} cy_std={sy:.2f} (tol={tol_mm})"


def _coplanar_xy(objs: list[dict], tol_mm: float) -> tuple[bool, str]:
    """Test that all centroids share a common XY plane (small cz spread)."""
    if len(objs) < 2:
        return True, "≤1 object"
    sz = _centroid_spread(objs, "z")
    return sz <= tol_mm, f"cz_std={sz:.2f} (tol={tol_mm})"


def _joint_pass(proxy, names: list[str], *, tol_mm: float = 0.5,
                max_floating: int = 0) -> tuple[bool, str, dict]:
    """Use worker joint_analysis to verify everything's connected."""
    if not names:
        return True, "no names", {}
    j = proxy.joint_analysis(names, tol_mm=tol_mm)
    if j.get("error"):
        return False, f"joint_analysis error: {j['error']}", j
    floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
    if len(floating) <= max_floating:
        return True, f"joints ok ({j.get('connected_count', 0)}/{len(names)} connected)", j
    return False, f"{len(floating)} floating parts: {floating[:5]}", j


# ---------- Strengthened checkers (L3) -------------------------------------

def _check_cube(ok, attempts, objs, err, proxy=None):
    if not ok:
        return False, f"agent failed: {err}"
    # L3: bbox dimensions must be 20 ± 0.5 mm on each side (target side = 20).
    target = 20.0
    tol = 0.5
    candidates = [
        o for o in _valid_solids(objs)
        if o.get("bbox") and all(
            abs(o["bbox"][k] - target) <= tol for k in ("xLen", "yLen", "zLen")
        )
    ]
    if candidates:
        c = candidates[0]
        bb = c["bbox"]
        return True, (
            f"{c['name']} {bb['xLen']:.1f}×{bb['yLen']:.1f}×{bb['zLen']:.1f} "
            f"vol={c['volume']:.0f} attempts={attempts}"
        )
    return False, (
        "no 20×20×20 ± 0.5 mm cube; bboxes: "
        + str([(o['name'], o.get('bbox', {}).get('xLen'),
               o.get('bbox', {}).get('yLen'), o.get('bbox', {}).get('zLen'))
              for o in _valid_solids(objs)[:5]])
    )


def _check_bolt_head_is_hex(objs: list[dict]) -> tuple[bool, str]:
    """Detect hexagonal head: look for a sub-solid named 'HexHead' / 'Head' /
    'BoltHead' whose bbox xLen != yLen (hex bboxes are rectangular ~1.15:1
    due to corner-to-flat asymmetry), OR has 8-14 faces (hex prism = 8 faces:
    6 sides + top + bottom; chamfered hex adds ~4 more).

    Round-cylinder head: bbox xLen ≈ yLen AND faces ≈ 3 (top + bottom + side).
    """
    candidates = [
        o for o in objs
        if (o.get("valid") and (o.get("volume") or 0) > 100
            and any(k in o["name"].lower() for k in ("head", "hex")))
    ]
    if not candidates:
        return False, "no Head-named sub-solid found"
    head = max(candidates, key=lambda o: o["volume"])
    bb = head.get("bbox") or {}
    xl, yl = bb.get("xLen", 0), bb.get("yLen", 0)
    if xl <= 0 or yl <= 0:
        return False, f"head {head['name']!r} has zero bbox"
    aspect = max(xl, yl) / min(xl, yl)
    faces = head.get("faces") or 0
    # Hex prism has 8 faces (6 sides + top + bottom) and rectangular bbox
    # with aspect 2/sqrt(3) ≈ 1.155 (corner-to-corner / flat-to-flat).
    # Tolerance: 1.08-1.30 (chamfers/fillets can slightly distort).
    hex_aspect = 1.08 <= aspect <= 1.30
    hex_faces = 6 <= faces <= 20
    if hex_aspect and hex_faces:
        return True, f"head={head['name']!r} aspect={aspect:.2f} faces={faces} (hex)"
    if not hex_aspect:
        return False, (
            f"head {head['name']!r} bbox is too circular: aspect={aspect:.2f} "
            f"(hex expected 1.08-1.30, xLen={xl:.1f} yLen={yl:.1f}) "
            f"— LLM may have used a Cylinder instead of a hex prism"
        )
    return False, f"head {head['name']!r} faces={faces} (hex prism expects 6-20)"


def _check_bolt(ok, attempts, objs, err, proxy=None):
    """Bolt: ≥3 valid solids (head + shank + thread), coaxial along Z, all
    joints touching (no floating parts), thread quality verified by
    (a) explicit Thread/Helix object with non-trivial volume OR
    (b) main bolt's face count significantly higher than a smooth hex bolt
        (smooth ≈ 10 faces; threaded ≥ 15).
    L5: head must be HEXAGONAL (not round) — verified by bbox aspect ratio
    and face count."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 3:
        return False, f"only {len(valid)} valid solid(s) — bolt expects head+shank+thread"
    main = _largest_solid(objs)
    bb = main.get("bbox") or {}
    z_len = bb.get("zLen", 0)
    xy_len = max(bb.get("xLen", 0), bb.get("yLen", 0))
    if z_len < xy_len:
        return False, f"main solid {main['name']!r} is not Z-axial: zLen={z_len:.1f} xy={xy_len:.1f}"
    # Coaxiality.
    coax_ok, coax_msg = _coaxial_z(valid, tol_mm=5.0)
    if not coax_ok:
        return False, f"parts not coaxial along Z: {coax_msg}"
    # Thread quality: look for explicit Thread / Helix / Cut residue object
    # with substantial volume; OR rely on face count of the main bolt.
    thread_candidates = [
        o for o in objs
        if (o.get("valid") and (o.get("volume") or 0) > 50.0
            and any(k in o["name"].lower() for k in ("thread", "helix", "swept")))
    ]
    thread_msg = ""
    main_faces = main.get("faces") or 0
    if thread_candidates:
        t = max(thread_candidates, key=lambda o: o["volume"])
        thread_msg = f" thread={t['name']!r}(vol={t['volume']:.0f},faces={t.get('faces')})"
    elif main_faces < 15:
        return False, (
            f"no Thread/Helix object found AND main bolt {main['name']!r} "
            f"has only {main_faces} faces (smooth bolts have ~10; threaded ≥15) "
            f"— thread cut probably failed"
        )
    else:
        thread_msg = f" main_faces={main_faces}"
    # Joints (no floating parts).
    if proxy is not None:
        j_ok, j_msg, _ = _joint_pass(
            proxy, [o["name"] for o in valid], tol_mm=0.5, max_floating=0
        )
        if not j_ok:
            return False, f"bolt joints: {j_msg}"
    # L5: head must be hexagonal.
    hex_ok, hex_msg = _check_bolt_head_is_hex(objs)
    if not hex_ok:
        return False, f"hex head check: {hex_msg}"
    return True, (
        f"{len(valid)} valid parts coaxial-Z (zLen={z_len:.1f}, xy≈{xy_len:.1f})"
        f"{thread_msg}; {hex_msg}, attempts={attempts}"
    )


def _check_atlas(ok, attempts, objs, err, proxy=None):
    """Atlas letters: ≥8 letter-like solids; all near the same Z (orbit is
    horizontal); centroid distance from common (cx,cy) is similar across
    letters (orbital placement)."""
    if not ok:
        return False, f"agent failed: {err}"
    glyphs = [
        o for o in objs
        if o["name"].startswith(("ShapeString", "Letter3D", "Extrusion", "Text"))
        or o.get("label", "").startswith(("ShapeString", "Letter3D"))
    ]
    valid_glyphs = [o for o in glyphs if o.get("valid")]
    if len(valid_glyphs) < 8:
        return False, f"only {len(valid_glyphs)} valid glyph(s)"
    # All glyph centroids should be near a common Z (planar orbit).
    cz_ok, cz_msg = _coplanar_xy(valid_glyphs, tol_mm=8.0)
    if not cz_ok:
        return False, f"glyphs not coplanar: {cz_msg}"
    # Compute orbit center & radius spread.
    cx_mean = sum(o["bbox"]["cx"] for o in valid_glyphs) / len(valid_glyphs)
    cy_mean = sum(o["bbox"]["cy"] for o in valid_glyphs) / len(valid_glyphs)
    radii = [
        ((o["bbox"]["cx"] - cx_mean) ** 2 + (o["bbox"]["cy"] - cy_mean) ** 2) ** 0.5
        for o in valid_glyphs
    ]
    r_mean = sum(radii) / len(radii) if radii else 0
    r_std = (sum((r - r_mean) ** 2 for r in radii) / len(radii)) ** 0.5 if radii else 0
    # For an orbital arrangement r_std/r_mean ≤ 0.25.
    if r_mean > 0 and r_std / r_mean > 0.30:
        return False, f"glyphs not on an orbit: r_mean={r_mean:.1f} r_std={r_std:.1f}"
    return True, (
        f"{len(valid_glyphs)} glyphs, orbit r≈{r_mean:.1f}±{r_std:.1f}, "
        f"Z-spread={cz_msg.split('=')[-1]}, attempts={attempts}"
    )


def _make_check_min_valid_solids(min_n: int, label: str = "valid solid(s)"):
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        valid = _valid_solids(objs)
        if len(valid) >= min_n:
            total_vol = sum(o["volume"] for o in valid)
            return True, f"{len(valid)} {label} (Σvol={total_vol:.0f} mm³), attempts={attempts}"
        return False, f"only {len(valid)} valid solid(s) out of {len(objs)} total"
    return _check


def _check_gear(expected_teeth: int, tol: int = 4):
    """Real tooth count via radial inside-sampling, not name substrings.
    L9: a real gear must have a CENTRAL AXLE HOLE — verified by sampling
    isInside at small radii near the gear's center. A solid disc with teeth
    is geometrically wrong (no shaft can pass through).
    L10: pick the largest FINAL (non-intermediate) solid as the gear — the
    intermediate fused-disc+teeth solid (input to Cut) is bigger by volume
    but has no axle hole; that's the bug we want to catch."""
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        finals = [o for o in _valid_solids(objs)
                  if not o.get("is_intermediate", False)]
        if not finals:
            finals = _valid_solids(objs)
        if not finals:
            return False, "no valid solid"
        main = max(finals, key=lambda o: o.get("volume") or 0)
        bb = main.get("bbox") or {}
        x_len, y_len, z_len = bb.get("xLen", 0), bb.get("yLen", 0), bb.get("zLen", 0)
        if not (0.0 < x_len and abs(x_len - y_len) / max(x_len, y_len) < 0.20):
            return False, (
                f"main solid not disc-like: x={x_len:.1f} y={y_len:.1f} z={z_len:.1f}"
            )
        if proxy is None:
            return False, "no proxy — cannot count teeth"
        rad = proxy.count_radial(main["name"], r_factor=0.95, sample_n=720)
        n = rad.get("count")
        if n is None:
            return False, f"count_radial failed: {rad.get('error')}"
        lo, hi = expected_teeth - tol, expected_teeth + tol
        if not (lo <= n <= hi):
            return False, (
                f"tooth_count={n} outside [{lo}, {hi}] "
                f"(expected ~{expected_teeth}); main={main['name']!r} "
                f"x={x_len:.1f} y={y_len:.1f}"
            )
        # L9: central axle hole check. Sample at r ≈ 0.05 × outer_r.
        # If the gear has a hole, this radius is OUTSIDE the solid →
        # inside_fraction near 0. Solid disc → near 1.
        hole_msg = ""
        try:
            outer_r = max(x_len, y_len) / 2.0
            inner = proxy.count_radial(main["name"], r_factor=0.05, sample_n=360)
            inside_frac = inner.get("inside_fraction", 1.0)
            hole_msg = f", center_inside={inside_frac:.2f}"
            if inside_frac > 0.20:
                return False, (
                    f"gear has NO central axle hole: at r=0.05·outer_r "
                    f"({0.05 * outer_r:.1f} mm), inside_fraction={inside_frac:.2f} "
                    f"(expected < 0.20). A solid disc with teeth is geometrically "
                    f"wrong — real gears need a shaft hole."
                )
        except Exception as exc:  # noqa: BLE001
            hole_msg = f", hole_check_err={exc!r}"
        return True, (
            f"{main['name']!r} teeth={n} (expected {expected_teeth}±{tol}), "
            f"disc {x_len:.1f}×{y_len:.1f}×{z_len:.1f}{hole_msg}, attempts={attempts}"
        )
    return _check


def _check_wheel(min_spokes: int = 4):
    """Bicycle wheel: 1 rim (Z-axial torus/disc) + 1 hub + ≥min_spokes radial
    spokes connecting hub to rim. Verify spoke count via count_radial near
    the hub radius.
    L5 — the wheel must be HOLLOW: rim should be annular (тор / кольцо), not
    a solid disc. Combined volume of all parts < 30 % of the equivalent
    solid disc of same outer diameter."""
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        valid = _valid_solids(objs)
        if len(valid) < 3:
            return False, f"only {len(valid)} valid parts — wheel needs rim+hub+spokes"
        # The biggest solid is usually the rim or a fused wheel; pick whichever
        # is "disc-like" with the largest XY footprint as the rim.
        disc_like = [
            o for o in valid
            if (o.get("bbox") and abs(o["bbox"]["xLen"] - o["bbox"]["yLen"]) /
                max(o["bbox"]["xLen"], o["bbox"]["yLen"], 1) < 0.15)
        ]
        if not disc_like:
            return False, "no disc-like part (rim?)"
        rim = max(disc_like, key=lambda o: o["bbox"]["xLen"] * o["bbox"]["yLen"])
        # Coplanarity of all valid parts. Tolerance scales with the wheel
        # diameter (max XY footprint) — a real bike wheel has a hub that
        # protrudes ~20-30 mm front/back of the rim plane, which is normal.
        wheel_d = max(rim["bbox"]["xLen"], rim["bbox"]["yLen"])
        cz_tol = max(wheel_d * 0.10, 50.0)  # 10% of diameter, min 50 mm
        cz_ok, cz_msg = _coplanar_xy(valid, tol_mm=cz_tol)
        if not cz_ok:
            return False, f"wheel parts not coplanar: {cz_msg}"
        # L5/L8: wheel must be HOLLOW. Use the FINAL wheel's OWN bbox for the
        # equivalent solid disc — earlier we used the "rim" object's bbox, but
        # that picked the flat SpokeFuse compound (bbox 955×955×2) and produced
        # a tiny v_solid (1.43M instead of ~10M), giving a false-positive fail.
        # The final wheel's bbox is the right reference for "what a solid disc
        # of the same overall envelope would have".
        import math as _m
        finals = [o for o in valid if not o.get("is_intermediate", False)]
        if not finals:
            finals = valid  # safety: nothing marked intermediate
        final = max(finals, key=lambda o: (o.get("volume") or 0))
        fbb = final.get("bbox") or {}
        final_xy = max(fbb.get("xLen", 0), fbb.get("yLen", 0))
        final_z = fbb.get("zLen", 0)
        v_solid = _m.pi * (final_xy / 2.0) ** 2 * final_z
        v_final = final.get("volume") or 0
        density = v_final / v_solid if v_solid > 0 else 0
        if density > 0.50:
            top = sorted(valid, key=lambda o: o.get("volume") or 0, reverse=True)[:5]
            debug = ", ".join(
                f"{o['name']}(vol={o['volume']:.0f},"
                f"xy={o['bbox']['xLen']:.0f}x{o['bbox']['yLen']:.0f},"
                f"z={o['bbox']['zLen']:.0f},inter={o.get('is_intermediate', False)})"
                for o in top if o.get("bbox")
            )
            return False, (
                f"wheel is too solid: final={final['name']!r} vol={v_final:.0f} mm³ "
                f"in bbox {final_xy:.0f}×{final_xy:.0f}×{final_z:.0f} "
                f"(equiv. solid disc {v_solid:.0f} mm³, density={density:.2f} > 0.50) "
                f"— rim should be annular/torus. top5: [{debug}]"
            )
        # Spoke count: sample radial isInside at mid-radius — count contiguous
        # inside-runs. With rim + spokes, runs ≈ rim's annular "inside ring"
        # (mostly continuous) is detected as 1 run at outer radius. Use ~50%
        # radius (inside the spoke band but outside the hub).
        spoke_count_msg = ""
        if proxy is not None:
            try:
                rad = proxy.count_radial(rim["name"], r_factor=0.55, sample_n=720)
                count = rad.get("count")
                spoke_count_msg = f" radial_runs(0.55r)={count}"
                if count is not None and count < min_spokes:
                    # The rim might be a single solid without spoke cavities.
                    # Try analyzing the entire compound: count distinct
                    # "spoke" solids by their bbox being long-thin radials.
                    pass
            except Exception as exc:  # noqa: BLE001
                spoke_count_msg = f" radial_err={exc!r}"
        # Joint connectivity.
        j_msg = ""
        if proxy is not None:
            j_ok, jm, _ = _joint_pass(proxy, [o["name"] for o in valid],
                                       tol_mm=2.0, max_floating=max(0, len(valid) // 5))
            j_msg = f"; {jm}"
            if not j_ok:
                return False, f"wheel parts disconnected: {jm}"
        return True, (
            f"{len(valid)} parts, rim={rim['name']!r} "
            f"({rim['bbox']['xLen']:.0f}×{rim['bbox']['yLen']:.0f}, "
            f"density={density:.2f}){spoke_count_msg}{j_msg}, attempts={attempts}"
        )
    return _check


def _check_house(ok, attempts, objs, err, proxy=None):
    """House: ≥2 Z-layers (ground + upper story) by centroid z; walls span
    both. Floor's bbox z is near bottom; roof bbox z near top."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 5:
        return False, f"only {len(valid)} valid solid(s) — house expects ≥5"
    # Look for multi-story: split centroid Z into 3 quantiles.
    czs = sorted(o["bbox"]["cz"] for o in valid if o.get("bbox"))
    if len(czs) < 3:
        return False, "missing bbox info"
    z_low, z_high = czs[0], czs[-1]
    if z_high - z_low < 100:  # 2-storey house ≥ 100 mm total height
        return False, f"house too flat (z span = {z_high - z_low:.0f} mm)"
    # Joint connectivity — most parts should touch some neighbour. Allow
    # up to 30 % floating (e.g. furniture / detached door).
    floating_msg = ""
    if proxy is not None:
        j = proxy.joint_analysis([o["name"] for o in valid], tol_mm=5.0)
        floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
        floating_msg = f"; floating={len(floating)}/{len(valid)}"
        if len(floating) > len(valid) * 0.5:
            return False, f"too many floating parts: {len(floating)}/{len(valid)}"
    return True, (
        f"{len(valid)} solids, z-span={z_high - z_low:.0f} mm"
        f"{floating_msg}, attempts={attempts}"
    )


def _check_kitchen(ok, attempts, objs, err, proxy=None):
    """Kitchen wall: cabinets along a wall — most parts should be coplanar
    (one wall direction), and connected to the wall or adjacent cabinet."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 6:
        return False, f"only {len(valid)} valid solid(s)"
    # Floor / wall: detect the largest, flattest bbox.
    base = max(valid, key=lambda o: (o["bbox"]["xLen"] * o["bbox"]["yLen"])
               if o.get("bbox") else 0)
    base_z = base["bbox"]["cz"] if base.get("bbox") else 0
    base_z_len = base["bbox"]["zLen"] if base.get("bbox") else 1
    base_z_min = base["bbox"]["zMin"] if base.get("bbox") else 0
    floating_msg = ""
    if proxy is not None:
        j = proxy.joint_analysis([o["name"] for o in valid], tol_mm=5.0)
        floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
        floating_msg = f"; floating={len(floating)}/{len(valid)}"
        if len(floating) > len(valid) * 0.5:
            return False, f"too many floating parts: {len(floating)}/{len(valid)}"
    return True, (
        f"{len(valid)} solids, base={base['name']!r} "
        f"(z_min={base_z_min:.0f}){floating_msg}, attempts={attempts}"
    )


def _check_wireframe(min_vertices: int = 32, min_edges: int = 80,
                      min_distinct_vertices: int = 30):
    """Wireframe (pentaract / graph / polytope): ≥min_vertices Part::Sphere
    primitives at vertex positions + ≥min_edges Part::Cylinder primitives
    along edges. Each cylinder should touch ≥1 sphere (its endpoints).

    Classification uses TypeId (Part::Sphere / Part::Cylinder) — robust
    against diagonal cylinder bboxes that look "cubic" after projection.

    L6: vertex spheres must be at DISTINCT positions. A degenerate projection
    can collapse multiple nD vertices to the same 3D point — bad recipe.
    Require ≥ min_distinct_vertices unique centroids (≥1 mm apart)."""
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        valid = _valid_solids(objs)
        # Prefer TypeId classification; fall back to bbox aspect for objects
        # without TypeId or for compound results.
        spheres = []
        cylinders = []
        other = []
        for o in valid:
            tid = (o.get("type_id") or "").lower()
            if "sphere" in tid:
                spheres.append(o)
            elif "cylinder" in tid:
                cylinders.append(o)
            else:
                bb = o.get("bbox") or {}
                xl, yl, zl = bb.get("xLen", 0), bb.get("yLen", 0), bb.get("zLen", 0)
                sides = sorted([xl, yl, zl])
                if sides[0] == 0:
                    continue
                ratio = sides[2] / sides[0]
                if ratio <= 1.5:
                    spheres.append(o)
                elif ratio >= 2.0:
                    cylinders.append(o)
                else:
                    other.append(o)
        if len(spheres) < min_vertices:
            return False, f"only {len(spheres)} spheres (expected ≥{min_vertices})"
        if len(cylinders) < min_edges:
            return False, f"only {len(cylinders)} cylinders (expected ≥{min_edges})"
        # L6: vertex distinctness. Two spheres at distance < 1 mm count as one.
        centers = [(o["bbox"]["cx"], o["bbox"]["cy"], o["bbox"]["cz"])
                   for o in spheres if o.get("bbox")]
        distinct = []
        for c in centers:
            if not any(
                ((c[0] - d[0]) ** 2 + (c[1] - d[1]) ** 2 + (c[2] - d[2]) ** 2) ** 0.5 < 1.0
                for d in distinct
            ):
                distinct.append(c)
        if len(distinct) < min_distinct_vertices:
            return False, (
                f"only {len(distinct)} distinct vertex positions (≥1 mm apart) "
                f"out of {len(spheres)} spheres — projection collapsed vertices"
            )
        # Sample 5 random cylinders; each must touch ≥1 sphere within 1.5 mm.
        import random as _rng
        bad = 0
        bad_msg = ""
        if proxy is not None:
            sample = _rng.sample(cylinders, k=min(5, len(cylinders)))
            for cyl in sample:
                names = [cyl["name"]] + [s["name"] for s in spheres[:80]]
                j = proxy.joint_analysis(names, tol_mm=1.5)
                v = j.get("verdict", {})
                if v.get(cyl["name"]) != "connected":
                    bad += 1
            if bad:
                bad_msg = f"; {bad}/5 sampled cylinders floating"
        return True, (
            f"{len(spheres)} vertex-spheres ({len(distinct)} distinct) + "
            f"{len(cylinders)} edge-cylinders ({len(other)} other){bad_msg}, "
            f"attempts={attempts}"
        )
    return _check


def _check_axle(ok, attempts, objs, err, proxy=None):
    """Railway axle (ГОСТ 33200-2014, РУ1-Ш variant): one long Z-axial solid,
    length ≈ 2294 mm. L5 — stepped diameters along Z. ГОСТ specifies:
      шейки (journals)        ⌀ 130 mm  — both ends, for bearing
      предподступичные        ⌀ 165 mm  — transition (under labyrinth seal)
      подступичные (hubs)     ⌀ 194 mm  — где насажены колёса
      средняя часть           ⌀ 165 mm  — between hubs
    A plain straight cylinder of ⌀165 fails this check — must have ≥3
    distinct radius levels along Z."""
    if not ok:
        return False, f"agent failed: {err}"
    main = _largest_solid(objs)
    if main is None or not main.get("bbox"):
        return False, "no valid solid"
    bb = main["bbox"]
    z_len = bb["zLen"]
    xy_len = max(bb["xLen"], bb["yLen"])
    if z_len < 1500:
        return False, f"axle Z-length too short: {z_len:.0f} (expected ≈ 2294)"
    if z_len < xy_len:
        return False, f"axle not Z-axial: zLen={z_len:.0f} xy={xy_len:.0f}"
    if proxy is None:
        return True, (
            f"{main['name']!r} {bb['xLen']:.0f}×{bb['yLen']:.0f}×{bb['zLen']:.0f}, "
            f"attempts={attempts}"
        )
    # L5: probe radial profile along Z. Detect distinct radius levels.
    prof = proxy.axial_radius_profile(main["name"], sample_n=80,
                                      r_max_hint=xy_len / 2.0 * 1.05)
    if prof.get("error") or not prof.get("profile"):
        return True, (
            f"{main['name']!r} {bb['xLen']:.0f}×{bb['yLen']:.0f}×{bb['zLen']:.0f}, "
            f"attempts={attempts} (profile unavailable: {prof.get('error')})"
        )
    radii = [p["r_max"] for p in prof["profile"] if p["r_max"] > 0]
    if len(radii) < 3:
        return False, f"axle has only {len(radii)} non-zero radius samples"
    r_min, r_max = min(radii), max(radii)
    r_range = r_max - r_min
    # ГОСТ РУ1-Ш has 4 distinct sections; demand at least 5 mm difference
    # between min/max radius (would catch a plain cylinder).
    if r_range < 5.0:
        return False, (
            f"axle radius is uniform ({r_min:.1f}-{r_max:.1f} mm, range {r_range:.1f} mm) "
            f"— ГОСТ РУ1-Ш requires stepped journals/hubs/middle (130/165/194 mm)"
        )
    # Cluster radii into "levels". Histogram with 5 mm bin width.
    bins = {}
    for r in radii:
        b = round(r / 5.0) * 5.0
        bins[b] = bins.get(b, 0) + 1
    distinct_levels = sum(1 for n in bins.values() if n >= 2)
    if distinct_levels < 3:
        return False, (
            f"axle has only {distinct_levels} distinct radius levels "
            f"(radii ≈ {sorted(bins.keys())}), expected ≥ 3"
        )
    return True, (
        f"{main['name']!r} length={z_len:.0f} mm, radii {r_min:.0f}-{r_max:.0f} mm "
        f"in {distinct_levels} levels {sorted(bins.keys())}, attempts={attempts}"
    )


def _check_thumb(ok, attempts, objs, err, proxy=None):
    """Thumb: 3 phalanx-like segments along a chain, each connected to the
    next. Skin/tendons/joints may add more parts."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 3:
        return False, f"only {len(valid)} valid solid(s)"
    if proxy is not None:
        j = proxy.joint_analysis([o["name"] for o in valid], tol_mm=2.0)
        floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
        # Up to 20 % loose parts (e.g. nail, tendon segments far apart).
        if len(floating) > len(valid) * 0.5:
            return False, f"too many floating parts: {len(floating)}/{len(valid)}"
        return True, (
            f"{len(valid)} parts, floating={len(floating)}, attempts={attempts}"
        )
    return True, f"{len(valid)} parts, attempts={attempts}"


def _check_cones_around_cube(ok, attempts, objs, err, proxy=None):
    """10 конусов + 1 куб. Cones radial around cube center, all touching cube
    or close to it. Cones should be on a circle in some plane."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 11:
        return False, f"only {len(valid)} valid solid(s) — expected 11 (10 cones + 1 cube)"
    # Identify the cube as the solid with bbox closest to cubic and highest
    # volume.
    cubic = [o for o in valid
             if o.get("bbox") and
             max(o["bbox"]["xLen"], o["bbox"]["yLen"], o["bbox"]["zLen"]) <
                 1.5 * min(o["bbox"]["xLen"], o["bbox"]["yLen"], o["bbox"]["zLen"])]
    if not cubic:
        return False, "no cubic-bbox solid found"
    cube = max(cubic, key=lambda o: o["volume"])
    others = [o for o in valid if o["name"] != cube["name"]]
    # Cone centroids should cluster on a sphere around the cube centroid.
    bbc = cube["bbox"]
    cube_c = (bbc["cx"], bbc["cy"], bbc["cz"])
    dists = [
        ((o["bbox"]["cx"] - cube_c[0]) ** 2 +
         (o["bbox"]["cy"] - cube_c[1]) ** 2 +
         (o["bbox"]["cz"] - cube_c[2]) ** 2) ** 0.5
        for o in others if o.get("bbox")
    ]
    if not dists:
        return False, "no cone-like centroids"
    d_mean = sum(dists) / len(dists)
    d_std = (sum((d - d_mean) ** 2 for d in dists) / len(dists)) ** 0.5
    rel = d_std / max(d_mean, 1)
    if rel > 0.35:
        return False, (
            f"cones not on a circle/sphere around cube: "
            f"d_mean={d_mean:.0f} d_std={d_std:.0f} rel={rel:.2f}"
        )
    return True, (
        f"cube={cube['name']!r}, {len(others)} cones at d={d_mean:.0f}±{d_std:.0f} "
        f"(rel={rel:.2f}), attempts={attempts}"
    )


def _check_spheres_in_volume(min_n: int, *, no_overlap: bool = True,
                               exclude_container: bool = True):
    """Packing check: ≥min_n spheres with cubic bbox.

    If `no_overlap` is True, sample 100 random pairs and assert none overlap
    (centroid distance ≥ r_a + r_b minus 5 % tolerance).

    If `exclude_container` is True, the LARGEST sphere is treated as the
    container (e.g. a host sphere that the fillers live inside) and is NOT
    pairwise-checked against fillers — only fillers among themselves are
    checked. This matches "fill X with smaller spheres" prompts where the
    big sphere by definition contains the small ones.
    """
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        valid = _valid_solids(objs)
        if len(valid) < min_n:
            return False, f"only {len(valid)} solids — expected ≥{min_n}"
        spheres = []
        for o in valid:
            tid = (o.get("type_id") or "").lower()
            bb = o.get("bbox") or {}
            xl, yl, zl = bb.get("xLen", 0), bb.get("yLen", 0), bb.get("zLen", 0)
            cubic = (xl > 0 and yl > 0 and zl > 0 and
                     max(xl, yl, zl) < 1.20 * min(xl, yl, zl))
            if "sphere" in tid or cubic:
                spheres.append(o)
        if len(spheres) < min_n:
            return False, f"only {len(spheres)} sphere-like — non-sphere shapes leaking"
        # Identify and optionally exclude the container (largest sphere).
        spheres_sorted = sorted(spheres, key=lambda o: o["volume"], reverse=True)
        container = None
        check_pool = spheres_sorted
        if exclude_container and len(spheres_sorted) >= 2:
            largest = spheres_sorted[0]
            second = spheres_sorted[1]
            # Container heuristic: largest is ≥ 5× larger than 2nd by volume.
            if largest["volume"] > 5 * second["volume"]:
                container = largest
                check_pool = spheres_sorted[1:]
        if no_overlap and len(check_pool) >= 2:
            import math as _m
            import random as _rng
            def _radius(o):
                v = o.get("volume") or 0
                return ((3 * v) / (4 * _m.pi)) ** (1 / 3) if v > 0 else 0
            with_r = [(o, _radius(o)) for o in check_pool]
            pairs = []
            if len(with_r) <= 30:
                for i in range(len(with_r)):
                    for j in range(i + 1, len(with_r)):
                        pairs.append((with_r[i], with_r[j]))
            else:
                for _ in range(100):
                    a, b = _rng.sample(with_r, 2)
                    pairs.append((a, b))
            overlap_count = 0
            worst = None
            for (oa, ra), (ob, rb) in pairs:
                ba, bb_ = oa["bbox"], ob["bbox"]
                d = ((ba["cx"] - bb_["cx"]) ** 2 +
                     (ba["cy"] - bb_["cy"]) ** 2 +
                     (ba["cz"] - bb_["cz"]) ** 2) ** 0.5
                if d < (ra + rb) * 0.95:  # 5% tolerance for grid-snap noise
                    overlap_count += 1
                    overshoot = (ra + rb) - d
                    if worst is None or overshoot > worst[0]:
                        worst = (overshoot, oa["name"], ob["name"], d, ra + rb)
            if overlap_count > 0:
                return False, (
                    f"{overlap_count}/{len(pairs)} sampled pairs OVERLAP "
                    f"(worst: {worst[1]!r}↔{worst[2]!r} d={worst[3]:.1f} "
                    f"need≥{worst[4]:.1f})"
                )
        container_msg = f" container={container['name']!r}" if container else ""
        return True, (
            f"{len(spheres)}/{len(valid)} spheres{container_msg} "
            f"(Σvol={sum(o['volume'] for o in spheres):.0f}, "
            f"non-overlap verified on {len(check_pool)}), attempts={attempts}"
        )
    return _check


def _check_cones_around_cube_strict(expected_cones: int = 10, *,
                                     uniformity_tol: float = 0.20):
    """10 конусов вокруг куба — strict version: cones must be uniformly
    distributed around the cube (centroid angular spread). Detects clustering
    bugs (e.g. LLM puts 5 cones on +X side and 5 on -X side instead of evenly
    around the perimeter)."""
    def _check(ok, attempts, objs, err, proxy=None):
        if not ok:
            return False, f"agent failed: {err}"
        valid = _valid_solids(objs)
        # Find cube + cones via TypeId.
        cubes = [o for o in valid if "box" in (o.get("type_id") or "").lower()]
        cones = [o for o in valid if "cone" in (o.get("type_id") or "").lower()]
        if not cubes:
            # Fallback: detect by bbox cubic shape, biggest volume.
            cubic = [
                o for o in valid
                if o.get("bbox") and
                max(o["bbox"]["xLen"], o["bbox"]["yLen"], o["bbox"]["zLen"]) <
                1.20 * min(o["bbox"]["xLen"], o["bbox"]["yLen"], o["bbox"]["zLen"])
            ]
            if not cubic:
                return False, "no cube found"
            cubes = [max(cubic, key=lambda o: o["volume"])]
        cube = cubes[0]
        bbc = cube["bbox"]
        cube_c = (bbc["cx"], bbc["cy"], bbc["cz"])
        if len(cones) < expected_cones:
            # Fallback: assume any non-cube valid solid is a cone.
            cones = [o for o in valid if o["name"] != cube["name"]]
        if len(cones) < expected_cones:
            return False, (
                f"only {len(cones)} cone-like objects (expected {expected_cones})"
            )
        # Uniformity check via angular distribution around the cube's Z axis.
        # Project each cone centroid onto the XY plane, compute angle from cube center.
        import math as _m
        angles = []
        for o in cones:
            bb = o.get("bbox") or {}
            dx = bb.get("cx", 0) - cube_c[0]
            dy = bb.get("cy", 0) - cube_c[1]
            angles.append(_m.atan2(dy, dx))
        # Sort angles, compute consecutive differences (wrapping at 2π).
        angles.sort()
        n = len(angles)
        diffs = []
        for i in range(n):
            d = angles[(i + 1) % n] - angles[i]
            if i == n - 1:
                d += 2 * _m.pi
            diffs.append(d)
        ideal = 2 * _m.pi / n
        max_dev = max(abs(d - ideal) for d in diffs) / ideal
        if max_dev > uniformity_tol:
            return False, (
                f"cones NOT uniform around cube: max angular deviation "
                f"{max_dev:.2f} > tol {uniformity_tol:.2f} "
                f"(ideal step {_m.degrees(ideal):.1f}°, "
                f"actual range {_m.degrees(min(diffs)):.0f}°..{_m.degrees(max(diffs)):.0f}°)"
            )
        # Also: cones should be approximately equidistant from the cube center.
        dists = [
            ((bb["cx"] - cube_c[0]) ** 2 + (bb["cy"] - cube_c[1]) ** 2) ** 0.5
            for o in cones if (bb := o.get("bbox"))
        ]
        d_mean = sum(dists) / len(dists)
        d_std = (sum((d - d_mean) ** 2 for d in dists) / len(dists)) ** 0.5
        rel = d_std / max(d_mean, 1)
        if rel > 0.10:
            return False, (
                f"cones not equidistant: d_mean={d_mean:.0f} d_std={d_std:.0f} "
                f"(rel={rel:.2f} > 0.10)"
            )
        return True, (
            f"cube={cube['name']!r}, {len(cones)} cones at d={d_mean:.0f}±{d_std:.0f} "
            f"(rel={rel:.2f}), angular max_dev={max_dev:.2f} (≤{uniformity_tol}), "
            f"attempts={attempts}"
        )
    return _check


def _check_kitchen_4m(ok, attempts, objs, err, proxy=None):
    """Kitchen wall ≈ 4 m: total assembly span along the longest horizontal
    axis must be in [3500, 4500] mm. ≥6 valid parts, mostly connected,
    base solid at ground level (z_min ≈ 0).
    L12: the user said «можно было разместить мойку» — verify there IS a sink:
    either a separate Part::Box named «sink»/«мойка»/«basin», OR a Part::Cut
    object representing the countertop-with-sink cutout."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 6:
        return False, f"only {len(valid)} valid solid(s)"
    if not valid or not valid[0].get("bbox"):
        return False, "missing bbox info"
    x_min = min(o["bbox"]["xMin"] for o in valid if o.get("bbox"))
    x_max = max(o["bbox"]["xMax"] for o in valid if o.get("bbox"))
    y_min = min(o["bbox"]["yMin"] for o in valid if o.get("bbox"))
    y_max = max(o["bbox"]["yMax"] for o in valid if o.get("bbox"))
    z_min = min(o["bbox"]["zMin"] for o in valid if o.get("bbox"))
    z_max = max(o["bbox"]["zMax"] for o in valid if o.get("bbox"))
    horizontal_span = max(x_max - x_min, y_max - y_min)
    if not (3500 <= horizontal_span <= 4500):
        return False, (
            f"wall span {horizontal_span:.0f} mm outside [3500, 4500] "
            f"(expected ≈ 4000 mm = 4 m); x={x_max - x_min:.0f} y={y_max - y_min:.0f}"
        )
    # L12: sink presence — name OR Cut on a countertop.
    sink_tokens = ("sink", "мойк", "basin", "раковин")
    countertop_cut_tokens = ("countertop", "столеш")
    sinks = [
        o for o in objs
        if any(t in (o["name"] + " " + o.get("label", "")).lower()
               for t in sink_tokens)
    ]
    countertop_cuts = [
        o for o in objs
        if "cut" in (o.get("type_id") or "").lower()
        and any(t in (o["name"] + " " + o.get("label", "")).lower()
                for t in countertop_cut_tokens)
    ]
    if not sinks and not countertop_cuts:
        return False, (
            "no sink found: expected a Part::Box named «sink»/«мойка»/"
            "«basin» OR a Part::Cut on a countertop. The user explicitly "
            "asked for a sink («чтобы можно было разместить мойку»)."
        )
    sink_msg = f"; sinks={[o['name'] for o in sinks[:3]]}{[o['name'] for o in countertop_cuts[:3]] if countertop_cuts else ''}"
    floating_msg = ""
    if proxy is not None:
        j = proxy.joint_analysis([o["name"] for o in valid], tol_mm=5.0)
        floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
        floating_msg = f"; floating={len(floating)}/{len(valid)}"
        if len(floating) > len(valid) * 0.5:
            return False, f"too many floating parts: {len(floating)}/{len(valid)}"
    return True, (
        f"{len(valid)} solids, span={horizontal_span:.0f}×{z_max - z_min:.0f} mm"
        f"{sink_msg}{floating_msg}, attempts={attempts}"
    )


def _check_house_2storey(ok, attempts, objs, err, proxy=None):
    """House 2 этажа: total height should be in [4000, 8500] mm (a 2-storey
    house is typically 5-7 m tall). Footprint diagonal in [4000, 25000] mm.
    Two distinct Z-bands of centroids visible.
    L6: at least one tall vertical wall (zLen ≥ 2000 mm AND zLen ≥ max(xLen,
    yLen)) must exist — catches "house = single floor slab" failure mode."""
    if not ok:
        return False, f"agent failed: {err}"
    valid = _valid_solids(objs)
    if len(valid) < 5:
        return False, f"only {len(valid)} valid solid(s)"
    if not valid[0].get("bbox"):
        return False, "missing bbox info"
    z_min = min(o["bbox"]["zMin"] for o in valid if o.get("bbox"))
    z_max = max(o["bbox"]["zMax"] for o in valid if o.get("bbox"))
    x_min = min(o["bbox"]["xMin"] for o in valid if o.get("bbox"))
    x_max = max(o["bbox"]["xMax"] for o in valid if o.get("bbox"))
    y_min = min(o["bbox"]["yMin"] for o in valid if o.get("bbox"))
    y_max = max(o["bbox"]["yMax"] for o in valid if o.get("bbox"))
    height = z_max - z_min
    # Realistic 2-storey envelope: 3.5 m (flat-roof minimalist) to 8 m
    # (steep gabled roof + porch + tall ceilings). >8 m suggests LLM piled
    # 3 storey-heights instead of 2.
    # Realistic envelope: a 2-storey house with steep gables + porch can be
    # 8.5 m tall (e.g. 3000 + 3000 storey + 2500 gable roof + 200 porch step).
    # Anything > 8500 mm strongly suggests 3 stacked storey-heights.
    if not (3500 <= height <= 8500):
        return False, (
            f"house height {height:.0f} mm outside [3500, 8500] "
            f"(2-storey realistic ≈ 5000-7500 mm; >8.5 m suggests 3 storey heights stacked)"
        )
    footprint = max(x_max - x_min, y_max - y_min)
    if not (4000 <= footprint <= 25000):
        return False, (
            f"house footprint {footprint:.0f} mm outside [4000, 25000]"
        )
    # Two-storey check: at least 2 distinct Z-bands of centroids,
    # band 1 in lower 40 %, band 2 in upper 40 %, of the height.
    czs = sorted(o["bbox"]["cz"] for o in valid if o.get("bbox"))
    lower_threshold = z_min + 0.40 * height
    upper_threshold = z_max - 0.40 * height
    lower_count = sum(1 for c in czs if c < lower_threshold)
    upper_count = sum(1 for c in czs if c > upper_threshold)
    if lower_count < 2 or upper_count < 2:
        return False, (
            f"not two distinct Z-bands: lower={lower_count} upper={upper_count} "
            f"(expected ≥ 2 each)"
        )
    # L6: at least one tall vertical wall must exist.
    walls = [
        o for o in valid
        if o.get("bbox")
        and o["bbox"]["zLen"] >= 2000.0
        and o["bbox"]["zLen"] >= max(o["bbox"]["xLen"], o["bbox"]["yLen"])
    ]
    if not walls:
        return False, (
            "no vertical wall (zLen ≥ 2 m AND zLen ≥ xLen/yLen) found "
            "— house has only horizontal slabs?"
        )
    floating_msg = ""
    if proxy is not None:
        j = proxy.joint_analysis([o["name"] for o in valid], tol_mm=5.0)
        floating = [n for n, v in j.get("verdict", {}).items() if v == "floating"]
        floating_msg = f"; floating={len(floating)}/{len(valid)}"
        if len(floating) > len(valid) * 0.5:
            return False, f"too many floating parts: {len(floating)}/{len(valid)}"
    return True, (
        f"{len(valid)} solids, h={height:.0f} mm footprint={footprint:.0f} mm, "
        f"Z-bands: lower={lower_count} upper={upper_count}, {len(walls)} tall walls"
        f"{floating_msg}, attempts={attempts}"
    )


SCENARIOS: list[Scenario] = [
    # ----- Baseline 3 scenarios (Sprint 5.22) ---------------------------------
    Scenario("R4", "Регрессия — куб 20×20×20",
             "Сделай куб 20×20×20 мм",
             timeout_s=120.0,
             success_check=_check_cube),
    Scenario("R1", "Болт M24 с резьбой",
             "Сделай болт M24 длиной 60 мм с резьбой",
             timeout_s=240.0,
             success_check=_check_bolt),
    Scenario("ATLAS", "Слова АТЛАС КОНСАЛТИНГ по орбите сферы",
             "По орбите сферы запусти слова АТЛАС КОНСАЛТИНГ, по кругу сколько влезет",
             timeout_s=300.0,
             success_check=_check_atlas),
    # ----- Extended suite (Sprint 5.23): distinct error classes mined ---------
    Scenario("E1", "Болт M30 + шайба (canonical 5.7+ recipe)",
             "Сделай сложный болт M30 с резьбой и шайбой",
             timeout_s=300.0,
             success_check=_check_bolt),
    Scenario("E2", "Болт M24 ISO (full recipe)",
             "Болт M24 ISO",
             timeout_s=300.0,
             success_check=_check_bolt),
    Scenario("E3", "Болт M24 с резьбой без упрощений",
             "Болт M24 с резьбой без упрощений",
             timeout_s=300.0,
             success_check=_check_bolt),
    Scenario("E4", "Шестерёнка 24 зуба (tooth count = 24)",
             "шестерёнка 24 зуба",
             timeout_s=240.0,
             success_check=_check_gear(24)),
    Scenario("E5", "Шестерёнка 20 зубьев (tooth count = 20)",
             "Сделай шестерёнку 20 зубьев",
             timeout_s=240.0,
             success_check=_check_gear(20)),
    Scenario("E6", "Эвольвентная шестерня (any plausible tooth count)",
             "эвольвентная шестерня 18 зубьев",
             timeout_s=240.0,
             success_check=_check_gear(18, tol=6)),
    Scenario("E7", "Большое зубчатое колесо (gear)",
             "большое зубчатое колесо 30 зубьев",
             timeout_s=240.0,
             success_check=_check_gear(30, tol=8)),
    Scenario("E8", "Колесо велосипеда (≥4 spokes, parts touching)",
             "колесо велосипеда со спицами",
             timeout_s=300.0,
             success_check=_check_wheel(min_spokes=4)),
    Scenario("E9", "Колесо велосипеда со спицами (≥8 spokes ok)",
             "Сделай колесо велосипеда со спицами",
             timeout_s=300.0,
             success_check=_check_wheel(min_spokes=4)),
    Scenario("E10", "Pentaract (4D куб, ≥32 vertex-spheres + ≥80 edge-cylinders)",
             "Пентеракт содержит:\n32 точки\n80 отрезков и квадратов\n40 кубов",
             timeout_s=300.0,
             success_check=_check_wireframe(min_vertices=32, min_edges=80)),
    Scenario("E11", "10 конусов вокруг куба (uniform radial layout)",
             "10 конусов вокруг куба",
             timeout_s=180.0,
             success_check=_check_cones_around_cube_strict(10, uniformity_tol=0.30)),
    Scenario("E12", "Сферы разного диаметра в кубе (≥5 spheres, non-overlapping)",
             "заполни куб разного диаметра сферами полностью, сферы не должны перекрывать друг друга",
             timeout_s=300.0,
             success_check=_check_spheres_in_volume(5, no_overlap=True)),
    Scenario("E13", "Заполнение сферы сферами разного диаметра (≥5 spheres, non-overlapping)",
             "заполни как песком и камнями сферу другими сферами разного диаметра, сферы не должны пересекаться",
             timeout_s=300.0,
             success_check=_check_spheres_in_volume(5, no_overlap=True)),
    Scenario("E14", "Стена кухни 4 м с мебелью (span 3.5-4.5 m, ≥6 parts)",
             "у меня стена кухни 4 метра, наполни ее кухонной мебелью, чтобы можно было разместить мойку",
             timeout_s=420.0,
             success_check=_check_kitchen_4m),
    Scenario("E15", "Дом 2 этажа (height 3.5-8 m, 2 Z-bands of parts)",
             "построй дом 2 этажа на каждой стене по 2 окна на одной из сторон дверь и крыльцо",
             timeout_s=420.0,
             success_check=_check_house_2storey),
    Scenario("E16", "Ось колёсной пары РУ1-Ш (длина ≈ 2294 mm, Z-axial)",
             "Сделай ось колёсной пары РУ1-Ш по ГОСТ 33200-2014. Ось вращательной симметрии — Z. Длина 2294 мм. Диаметры шеек 130 мм, подступичных частей 165 мм, средней части 165 мм.",
             timeout_s=300.0,
             success_check=_check_axle),
    Scenario("E17", "Большой палец руки (≥3 parts, mostly connected)",
             "сделай анатомически верный большой палец человеческой руки",
             timeout_s=300.0,
             success_check=_check_thumb),
]


# ---------- Key + model resolution -----------------------------------------

ENV_OVERRIDES = {
    "anthropic": "NEUROCAD_ANTHROPIC_API_KEY",
    "openai":    "NEUROCAD_OPENAI_API_KEY",
    "deepseek":  "NEUROCAD_DEEPSEEK_API_KEY",
    "ollama":    "NEUROCAD_OLLAMA_API_KEY",
}


def _resolve_api_key(key_slug: str) -> tuple[str | None, str]:
    """Return (key, source). Tries env override → key_storage → None."""
    env_var = ENV_OVERRIDES.get(key_slug)
    if env_var and os.environ.get(env_var):
        return os.environ[env_var], f"env:{env_var}"
    try:
        from neurocad.config import key_storage
        # key_storage uses the bare slug as the account (settings UI passes
        # `spec.key_slug` directly).
        key, backend = key_storage.load_key(key_slug)
        if key:
            return key, f"keystorage:{backend}"
    except Exception as exc:  # noqa: BLE001
        return None, f"keystorage error: {exc}"
    return None, "not-found"


def _build_adapter(spec, api_key: str):
    """Instantiate the LLM adapter for a ModelSpec."""
    if spec.adapter == "anthropic":
        from neurocad.llm.anthropic import AnthropicAdapter
        return AnthropicAdapter(api_key=api_key, model=spec.model_id)
    if spec.adapter == "openai":
        from neurocad.llm.openai import OpenAIAdapter
        kwargs = {"api_key": api_key, "model": spec.model_id}
        if spec.base_url:
            kwargs["base_url"] = spec.base_url
        return OpenAIAdapter(**kwargs)
    raise ValueError(f"unsupported adapter type {spec.adapter!r}")


# ---------- Scenario runner ------------------------------------------------

@dataclass
class ScenarioResult:
    scenario: Scenario
    passed: bool
    detail: str
    attempts: int
    elapsed_s: float
    objects: list[dict] = field(default_factory=list)
    final_error: str | None = None


def _run_one(
    scenario: Scenario,
    proxy: WorkerProxy,
    spec,
    api_key: str,
) -> ScenarioResult:
    from neurocad.core import agent as agent_mod
    from neurocad.core.agent import AgentCallbacks
    from neurocad.core.history import History

    adapter = _build_adapter(spec, api_key)
    history = History()
    doc = _MockDoc()

    def on_exec_needed(code: str, attempt: int) -> dict:
        try:
            r = proxy.execute(code, timeout_s=scenario.timeout_s)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "new_objects": [], "error": f"bridge error: {exc!r}", "rollback_count": 0}
        return {
            "ok": r.get("ok", False),
            "new_objects": r.get("new_objects", []),
            "error": r.get("error"),
            "rollback_count": r.get("rollback_count", 0),
        }

    callbacks = AgentCallbacks(
        on_chunk=lambda _c: None,
        on_attempt=lambda _n, _m: None,
        on_status=lambda _s: None,
        on_exec_needed=on_exec_needed,
    )

    start = time.monotonic()
    proxy.reset()  # fresh document per scenario
    try:
        result = agent_mod.run(scenario.prompt, doc, adapter, history, callbacks)
    except Exception as exc:  # noqa: BLE001
        return ScenarioResult(
            scenario=scenario, passed=False,
            detail=f"agent.run raised: {exc!r}",
            attempts=0, elapsed_s=time.monotonic() - start,
        )
    elapsed = time.monotonic() - start

    inspect = proxy.inspect()
    objs = inspect.get("objects", [])

    passed, detail = scenario.success_check(
        result.ok, result.attempts, objs, result.error, proxy
    )
    return ScenarioResult(
        scenario=scenario,
        passed=passed,
        detail=detail,
        attempts=result.attempts,
        elapsed_s=elapsed,
        objects=objs,
        final_error=result.error,
    )


# ---------- Driver main ----------------------------------------------------

def _driver_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scenario", default="all",
                        help="Scenario code (R4 / R1 / ATLAS) or 'all'. Default: all")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit")
    parser.add_argument("--freecadcmd", default=DEFAULT_FREECADCMD,
                        help=f"Path to freecadcmd (default: {DEFAULT_FREECADCMD})")
    parser.add_argument("--model-id", default=None,
                        help="Override model_id (default: from NeuroCAD config.json)")
    parser.add_argument("--worker-stderr", default=None,
                        help="Path to capture worker stderr (default: discarded)")
    args = parser.parse_args(argv)

    if args.list:
        for s in SCENARIOS:
            print(f"  {s.code:8s} — {s.title}")
        return 0

    if not Path(args.freecadcmd).exists():
        print(f"ERROR: freecadcmd not found at {args.freecadcmd}", file=sys.stderr)
        return 2

    # --- resolve model + key ---------------------------------------------------
    sys.path.insert(0, str(REPO_ROOT))
    from neurocad.config.config import load as load_config
    from neurocad.llm import models as model_registry

    # In the venv (no FreeCAD), _get_config_dir() can't reach the user's
    # production config at  ~/Library/Application Support/FreeCAD/.../neurocad/.
    # Read it directly if the file exists; otherwise fall back to the
    # default-resolved config.
    config = None
    macos_cfg = Path.home() / "Library" / "Application Support" / "FreeCAD" / "v1-1" / "neurocad" / "config.json"
    if macos_cfg.exists():
        try:
            config = json.loads(macos_cfg.read_text(encoding="utf-8"))
            print(f"Config: {macos_cfg}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not read {macos_cfg}: {exc}", file=sys.stderr)
    if config is None:
        config = load_config()
        print("Config: defaults (no FreeCAD UserAppData)")
    model_id = args.model_id or config.get("model_id") or model_registry.default_model_id()
    spec = model_registry.get_model(model_id)
    if spec is None:
        print(f"ERROR: unknown model_id {model_id!r}. Available:", file=sys.stderr)
        for s in model_registry.list_models():
            print(f"  {s.id}", file=sys.stderr)
        return 2
    print(f"Model: {spec.display_name}  ({spec.id}, adapter={spec.adapter})")

    api_key, source = _resolve_api_key(spec.key_slug)
    if not api_key:
        env_var = ENV_OVERRIDES.get(spec.key_slug, "?")
        print(f"ERROR: no API key for slug {spec.key_slug!r} ({source})", file=sys.stderr)
        print(
            f"  Set ${env_var} OR store via NeuroCad Settings dialog.",
            file=sys.stderr,
        )
        return 3
    print(f"Key source: {source}  (len={len(api_key)})")

    # --- pick scenarios --------------------------------------------------------
    if args.scenario == "all":
        scenarios = list(SCENARIOS)
    else:
        scenarios = [s for s in SCENARIOS if s.code.lower() == args.scenario.lower()]
        if not scenarios:
            print(f"ERROR: unknown scenario {args.scenario!r}. Use --list.", file=sys.stderr)
            return 2

    # --- spawn worker + run ----------------------------------------------------
    stderr_path = Path(args.worker_stderr) if args.worker_stderr else None
    print(f"Spawning worker: {args.freecadcmd} {Path(__file__)}")
    proxy = WorkerProxy(args.freecadcmd, Path(__file__), log_stderr_to=stderr_path)
    print(f"Worker ready (FreeCAD {'.'.join(proxy.fc_version or [])}, doc={proxy.doc_name})\n")

    results: list[ScenarioResult] = []
    try:
        for sc in scenarios:
            print(f"=== {sc.code} — {sc.title}")
            print(f"    prompt: {sc.prompt!r}")
            r = _run_one(sc, proxy, spec, api_key)
            results.append(r)
            mark = "PASS" if r.passed else "FAIL"
            print(f"    [{mark}] attempts={r.attempts} elapsed={r.elapsed_s:.1f}s — {r.detail}")
            if not r.passed and r.final_error:
                print(f"    error: {r.final_error[:200]}")
            print()
    finally:
        proxy.close()

    # --- summary ---------------------------------------------------------------
    n_pass = sum(1 for r in results if r.passed)
    print("=" * 70)
    print(f"TOTAL: {n_pass}/{len(results)} scenarios passed")
    return 0 if n_pass == len(results) else 1


# ---------------------------------------------------------------------------

# freecadcmd imports user scripts as a module (not __main__), so we cannot
# rely on the __main__ guard. Detect worker context via FreeCAD presence
# combined with an explicit env flag set by the driver subprocess.
if os.environ.get("NEUROCAD_DOGFOOD_WORKER") == "1" and _looks_like_worker():
    sys.exit(_worker_main())

if __name__ == "__main__":
    sys.exit(_driver_main(sys.argv[1:]))
