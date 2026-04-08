"""Capture document state into a structured snapshot."""

from dataclasses import dataclass, field


@dataclass
class ObjectInfo:
    """Information about a single object in the document."""
    name: str
    type_id: str
    shape_type: str | None = None
    volume_mm3: float | None = None
    placement: str | None = None
    visible: bool = True


@dataclass
class DocSnapshot:
    """Snapshot of a FreeCAD document."""
    filename: str
    active_object: str | None = None
    objects: list[ObjectInfo] = field(default_factory=list)
    unit: str = "mm"


def capture(doc) -> DocSnapshot:
    """Create a snapshot of the given FreeCAD document."""
    if doc is None:
        return DocSnapshot(filename="Untitled")

    objects = []
    for obj in doc.Objects:
        shape_type = None
        volume_mm3 = None
        if hasattr(obj, "Shape") and obj.Shape is not None:
            shape = obj.Shape
            shape_type = shape.ShapeType
            if hasattr(shape, "Volume"):
                # Volume is in mm³ for metric parts
                volume_mm3 = shape.Volume

        placement = None
        if hasattr(obj, "Placement"):
            try:
                placement = str(obj.Placement.toTuple())
            except Exception:
                placement = str(obj.Placement)

        visible = bool(getattr(obj, "Visibility", True))

        objects.append(ObjectInfo(
            name=obj.Name,
            type_id=obj.TypeId,
            shape_type=shape_type,
            volume_mm3=volume_mm3,
            placement=placement,
            visible=visible,
        ))

    active = doc.ActiveObject.Name if hasattr(doc, "ActiveObject") and doc.ActiveObject else None

    return DocSnapshot(
        filename=doc.Name,
        active_object=active,
        objects=objects,
        unit="mm",  # FreeCAD's internal unit is mm
    )


def to_prompt_str(snap: DocSnapshot, max_chars: int = 2000) -> str:
    """Convert snapshot to a concise string suitable for LLM prompt."""
    lines = []
    lines.append(f"Document: {snap.filename} (unit: {snap.unit})")
    if snap.active_object:
        lines.append(f"Active object: {snap.active_object}")

    if snap.objects:
        lines.append("Objects:")
        for obj in snap.objects:
            line = f"  - {obj.name} ({obj.type_id})"
            if obj.shape_type:
                line += f" [{obj.shape_type}]"
            if obj.volume_mm3 is not None:
                line += f" vol={obj.volume_mm3:.1f} mm³"
            if obj.placement:
                line += f" placement={obj.placement}"
            if not obj.visible:
                line += " (hidden)"
            lines.append(line)
    else:
        lines.append("No objects in the document.")

    full = "\n".join(lines)
    if len(full) > max_chars:
        # Truncate, keep the beginning
        full = full[:max_chars - 3] + "..."
    return full
