"""
IFC structured-text extraction.

Produces a deterministic, human-readable text dump of an IFC model so that
the consumer pipeline stores searchable content (used by full-text search
and DocRead Q&A). The output is grouped into five sections:

    [PROJECT], [BUILDINGS], [SPACES], [MATERIALS], [CLASSIFICATION]

Extraction is defensive: malformed entities are skipped, large enumerations
are capped so a 1M-element model doesn't produce a 50 MB blob that bloats
the document content column.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

import ifcopenshell

# Limits chosen so a complex project (~500k elements) still produces a
# searchable but bounded text blob. The point is full-text search hits,
# not a faithful serialization.
MAX_BUILDINGS = 50
MAX_SPACES = 500
MAX_MATERIAL_ROWS = 200
MAX_CLASSIFICATION_ROWS = 200
MAX_TEXT_LEN = 200  # truncate long description/name strings


def _truncate(s: str | None) -> str:
    if not s:
        return ""
    s = str(s).strip().replace("\n", " ").replace("\r", " ")
    if len(s) > MAX_TEXT_LEN:
        s = s[: MAX_TEXT_LEN - 1] + "…"
    return s


def _count_by_type(model: ifcopenshell.file, ifc_class: str) -> int:
    try:
        return len(model.by_type(ifc_class))
    except RuntimeError:
        return 0


def _unit_string(props) -> str:
    """
    IfcPropertySingleValue can carry a unit symbol (e.g. "m³") next to its
    numeric value. We render both as a compact "value unit" string.
    """
    val = getattr(props, "NominalValue", None)
    unit = getattr(props, "Unit", None)
    if val is None:
        return ""
    try:
        text = str(val.wrappedValue)
    except Exception:  # pragma: no cover
        return ""
    if unit:
        try:
            text = f"{text} {unit}"
        except Exception:
            pass
    return text


def _extract_project(model: ifcopenshell.file) -> list[str]:
    lines: list[str] = []
    projects = model.by_type("IfcProject")
    if not projects:
        return lines
    project = projects[0]
    name = _truncate(getattr(project, "Name", None)) or "(unnamed)"
    long_name = _truncate(getattr(project, "LongName", None))
    description = _truncate(getattr(project, "Description", None))

    schema = _truncate(getattr(model, "schema", None)) or "(unknown)"
    header = getattr(model, "header", None)
    created = _truncate(getattr(header, "file_name", None) and
                        getattr(getattr(header, "file_name", None), "time_stamp", None))

    author = ""
    author_blocks = list(model.by_type("IfcPerson"))
    if author_blocks:
        persons = []
        for p in author_blocks[:5]:
            fam = _truncate(getattr(p, "FamilyName", None))
            giv = _truncate(getattr(p, "GivenName", None))
            mid = _truncate(getattr(p, "MiddleNames", None))
            org = _truncate(getattr(p, "Organization", None))
            name_part = " ".join(x for x in (giv, mid, fam) if x)
            if org:
                name_part = f"{name_part} <{org}>" if name_part else org
            if name_part:
                persons.append(name_part)
        if persons:
            author = ", ".join(persons)

    lines.append(f"项目名：{name}")
    if long_name:
        lines.append(f"长名称：{long_name}")
    if description:
        lines.append(f"描述：{description}")
    lines.append(f"IFC schema：{schema}")
    if author:
        lines.append(f"作者：{author}")
    if created:
        lines.append(f"时间戳：{created}")

    # Application export info
    try:
        apps = list(model.by_type("IfcApplication"))
        if apps:
            app = apps[0]
            app_name = _truncate(getattr(app, "ApplicationFullName", None))
            app_ver = _truncate(getattr(app, "Version", None))
            dev = _truncate(getattr(getattr(app, "ApplicationDeveloper", None), "Name", None))
            bits = " · ".join(x for x in (app_name, app_ver, dev) if x)
            if bits:
                lines.append(f"导出工具：{bits}")
    except RuntimeError:
        pass

    # High-level element counts (useful for "how many walls does this model have?")
    counts = [
        ("IfcSite", _count_by_type(model, "IfcSite")),
        ("IfcBuilding", _count_by_type(model, "IfcBuilding")),
        ("IfcBuildingStorey", _count_by_type(model, "IfcBuildingStorey")),
        ("IfcSpace", _count_by_type(model, "IfcSpace")),
        ("IfcWall", _count_by_type(model, "IfcWall")),
        ("IfcSlab", _count_by_type(model, "IfcSlab")),
        ("IfcBeam", _count_by_type(model, "IfcBeam")),
        ("IfcColumn", _count_by_type(model, "IfcColumn")),
        ("IfcDoor", _count_by_type(model, "IfcDoor")),
        ("IfcWindow", _count_by_type(model, "IfcWindow")),
        ("IfcRoof", _count_by_type(model, "IfcRoof")),
        ("IfcStair", _count_by_type(model, "IfcStair")),
        ("IfcRailing", _count_by_type(model, "IfcRailing")),
        ("IfcMember", _count_by_type(model, "IfcMember")),
        ("IfcPlate", _count_by_type(model, "IfcPlate")),
        ("IfcProxy", _count_by_type(model, "IfcProxy")),
    ]
    lines.append("")
    lines.append("构件总数：")
    for label, n in counts:
        if n:
            lines.append(f"- {label}：{n}")
    return lines


def _ancestor(entity, *ifc_classes):
    """
    Walk ``entity.Decomposes`` (IfcRelAggregates) up the hierarchy and
    return the first ancestor whose class is one of ``ifc_classes``.
    """
    seen = set()
    stack = [entity]
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if cur.is_a() in ifc_classes:
            return cur
        for rel in getattr(cur, "Decomposes", []) or []:
            parent = getattr(rel, "RelatingObject", None)
            if parent is not None:
                stack.append(parent)
    return None


def _extract_buildings(model: ifcopenshell.file) -> list[str]:
    lines: list[str] = []
    buildings = list(model.by_type("IfcBuilding"))[:MAX_BUILDINGS]
    if not buildings:
        return lines
    lines.append("")
    for b in buildings:
        name = _truncate(getattr(b, "Name", None)) or "(unnamed)"
        long_name = _truncate(getattr(b, "LongName", None))
        elev = ""
        try:
            ev = getattr(b, "ElevationOfRefHeight", None)
            if ev is not None:
                elev = f"{ev.wrappedValue:.2f} m"
        except Exception:
            elev = ""
        bits = [name]
        if long_name:
            bits.append(long_name)
        if elev:
            bits.append(f"基准高程 {elev}")
        # count storeys/spaces that descend from this building, going up
        # the IfcRelAggregates chain (space → storey → building).
        storeys = [
            s for s in model.by_type("IfcBuildingStorey")
            if _ancestor(s, "IfcBuilding") == b
        ]
        spaces = [
            sp for sp in model.by_type("IfcSpace")
            if _ancestor(sp, "IfcBuilding") == b
        ]
        bits.append(f"楼层 {len(storeys)} 个，空间 {len(spaces)} 个")
        lines.append("- " + "（".join(bits[:2]) + (")" if len(bits) > 1 else "") +
                     (" · " + " · ".join(bits[2:]) if len(bits) > 2 else ""))
    return lines


def _extract_spaces(model: ifcopenshell.file) -> list[str]:
    lines: list[str] = []
    spaces = list(model.by_type("IfcSpace"))[:MAX_SPACES]
    if not spaces:
        return lines

    # Group by storey
    by_storey: dict[str, list[str]] = {}
    for sp in spaces:
        name = _truncate(getattr(sp, "Name", None)) or "(unnamed)"
        long_name = _truncate(getattr(sp, "LongName", None))
        storey = "(未指定楼层)"
        try:
            for rel in getattr(sp, "Decomposes", []) or []:
                parent = getattr(rel, "RelatingObject", None)
                if parent is not None and parent.is_a("IfcBuildingStorey"):
                    storey = _truncate(getattr(parent, "Name", None)) or "(unnamed storey)"
                    break
        except Exception:
            pass
        line = f"  - {name}"
        if long_name and long_name != name:
            line += f"（{long_name}）"
        by_storey.setdefault(storey, []).append(line)

    lines.append("")
    lines.append(f"空间（按楼层分组，共 {len(spaces)} 个）：")
    for storey, items in by_storey.items():
        lines.append(f"- {storey}：")
        lines.extend(items[:50])
        if len(items) > 50:
            lines.append(f"  · 还有 {len(items) - 50} 个空间…")
    return lines


def _extract_materials(model: ifcopenshell.file) -> list[str]:
    lines: list[str] = []
    counts: Counter = Counter()
    name_by_class: dict[str, str] = {}

    for mat in model.by_type("IfcMaterial"):
        cls = mat.is_a()
        name = _truncate(getattr(mat, "Name", None)) or cls
        try:
            cats = [
                _truncate(getattr(c, "Category", None))
                for c in getattr(mat, "MaterialCategories", []) or []
            ]
        except Exception:
            cats = []
        key = name if name else cls
        counts[key] += 1
        if key not in name_by_class:
            name_by_class[key] = cls

    if not counts:
        return lines

    lines.append("")
    lines.append("主要材料（按引用数量倒序）：")
    for name, n in counts.most_common(MAX_MATERIAL_ROWS):
        lines.append(f"- {name}：{n} 处引用")
    if len(counts) > MAX_MATERIAL_ROWS:
        lines.append(f"  · 还有 {len(counts) - MAX_MATERIAL_ROWS} 种材料…")
    return lines


def _extract_classifications(model: ifcopenshell.file) -> list[str]:
    lines: list[str] = []
    seen: Counter = Counter()
    try:
        refs = list(model.by_type("IfcClassificationReference"))
    except RuntimeError:
        refs = []
    if not refs:
        return lines
    lines.append("")
    lines.append("分类系统：")
    for ref in refs[:MAX_CLASSIFICATION_ROWS]:
        ident = _truncate(getattr(ref, "Identification", None))
        name = _truncate(getattr(ref, "Name", None))
        if not (ident or name):
            continue
        key = f"{ident} {name}".strip()
        seen[key] += 1
    for k, n in seen.most_common(MAX_CLASSIFICATION_ROWS):
        lines.append(f"- {k}：{n} 处使用")
    return lines


def extract_text(document_path) -> str:
    """
    Open the IFC file at *document_path* and return a structured-text dump.

    Raises :class:`ifcopenshell.file` open errors upstream; callers should
    translate them into ``ParseError`` so the consumer treats the file as
    unsupported.
    """
    model = ifcopenshell.open(str(document_path))

    sections: list[Iterable[str]] = [
        ["[PROJECT]"],
        _extract_project(model),
        _extract_buildings(model),
        _extract_spaces(model),
        _extract_materials(model),
        _extract_classifications(model),
    ]
    out: list[str] = []
    for s in sections:
        out.extend(s)
    return "\n".join(s for s in out if s).strip() + "\n"


def extract_metadata(document_path) -> list[dict]:
    """
    Return list-of-dicts in the format expected by DocumentParser.extract_metadata.
    """
    model = ifcopenshell.open(str(document_path))

    items: list[dict] = []
    for project in model.by_type("IfcProject"):
        items.append({
            "namespace": "ifc",
            "prefix": "project",
            "key": "name",
            "value": _truncate(getattr(project, "Name", None)) or "",
        })
        items.append({
            "namespace": "ifc",
            "prefix": "project",
            "key": "schema",
            "value": _truncate(getattr(model, "schema", None)) or "",
        })
        items.append({
            "namespace": "ifc",
            "prefix": "project",
            "key": "long_name",
            "value": _truncate(getattr(project, "LongName", None)) or "",
        })
    items.append({
        "namespace": "ifc",
        "prefix": "counts",
        "key": "buildings",
        "value": _count_by_type(model, "IfcBuilding"),
    })
    items.append({
        "namespace": "ifc",
        "prefix": "counts",
        "key": "storeys",
        "value": _count_by_type(model, "IfcBuildingStorey"),
    })
    items.append({
        "namespace": "ifc",
        "prefix": "counts",
        "key": "spaces",
        "value": _count_by_type(model, "IfcSpace"),
    })
    items.append({
        "namespace": "ifc",
        "prefix": "counts",
        "key": "elements_total",
        "value": sum(_count_by_type(model, c) for c in (
            "IfcWall", "IfcSlab", "IfcBeam", "IfcColumn", "IfcDoor",
            "IfcWindow", "IfcRoof", "IfcStair", "IfcRailing", "IfcMember",
            "IfcPlate", "IfcProxy",
        )),
    })
    return items


def is_ifc_file(document_path) -> bool:
    """
    Sniff an IFC file by its magic header `ISO-10303-21`. Cheap check that
    runs before invoking ifcopenshell.
    """
    try:
        with open(document_path, "rb") as fh:
            head = fh.read(64)
    except OSError:
        return False
    return b"ISO-10303-21" in head
