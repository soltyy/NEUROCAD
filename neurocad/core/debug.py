"""Lightweight runtime diagnostics for FreeCAD console/report view."""

from __future__ import annotations

import threading


def _emit(method_name: str, message: str) -> None:
    line = f"[NeuroCad] {message}\n"
    try:
        import FreeCAD  # type: ignore

        console = getattr(FreeCAD, "Console", None)
        if console is not None and hasattr(console, method_name):
            getattr(console, method_name)(line)
    except Exception:
        pass
    # Also mirror to stdout so the Python console shows the same trace.
    print(line, end="")


def _compact(value: object, limit: int = 240) -> str:
    text = str(value).replace("\n", "\\n")
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def log_info(stage: str, message: str, **fields: object) -> None:
    parts = [stage, message]
    if fields:
        parts.extend(f"{key}={_compact(value)}" for key, value in fields.items())
    parts.append(f"thread={threading.current_thread().name}")
    _emit("PrintMessage", " | ".join(parts))


def log_warn(stage: str, message: str, **fields: object) -> None:
    parts = [stage, message]
    if fields:
        parts.extend(f"{key}={_compact(value)}" for key, value in fields.items())
    parts.append(f"thread={threading.current_thread().name}")
    _emit("PrintWarning", " | ".join(parts))


def log_error(stage: str, message: str, **fields: object) -> None:
    parts = [stage, message]
    if fields:
        parts.extend(f"{key}={_compact(value)}" for key, value in fields.items())
    parts.append(f"thread={threading.current_thread().name}")
    _emit("PrintError", " | ".join(parts))


def log_notify(message: str, **fields: object) -> None:
    """Log a user-visible notification emitted during request processing.

    Appears as a dedicated ``agent.notify`` line so UI events can be traced
    separately from internal execution events.
    Uses PrintLog so the entries are stored without cluttering the Report view.
    """
    parts = ["agent.notify", message]
    if fields:
        parts.extend(f"{key}={_compact(value)}" for key, value in fields.items())
    parts.append(f"thread={threading.current_thread().name}")
    _emit("PrintLog", " | ".join(parts))
