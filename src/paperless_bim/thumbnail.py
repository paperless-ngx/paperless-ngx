"""
Isometric SVG thumbnail renderer for IFC models.

Strategy (lightweight):
  - Use `ifcopenshell.geom.settings` + `file.create_iterator` with a
    compact triangle-mesh setting (tessellate=0.5) to keep memory small.
  - Aggregate all meshes' vertices into one point cloud / triangle list.
  - Render with matplotlib's SVG backend in a single ``Axes`` view, ax = 0
    so the SVG stays a few KB even for million-element models.
  - No textures, no labels — just an iso silhouette that conveys shape.

For models with zero geometry (rare), we emit a fallback placeholder SVG
so the consumer doesn't have to special-case empty models.
"""
from __future__ import annotations

import logging
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import matplotlib

# Use the non-interactive Agg backend — we only write SVG, never display.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

log = logging.getLogger("paperless.bim.thumbnail")

# Soft, dark-on-light palette so the SVG is readable on light dashboards.
_FACE_COLOR = "#1A73E8"
_EDGE_COLOR = "#0B3D91"
_BG_COLOR = "#FFFFFF"
_RASTER_DPI = 96


def _collect_geometry(model: ifcopenshell.file, *, max_elements: int = 200_000):
    """
    Tessellate the model and yield (verts, faces) tuples. Hard-cap on
    element count so a pathological model can't OOM the worker.

    Implementation note: the ``ifcopenshell.geom.iterator`` API differs
    across versions (init params, mandatory ``initialize()``), so we
    use the simpler ``create_shape`` per element. It's slower but works
    uniformly across 0.7.x and 0.8.x.
    """
    s = ifcopenshell.geom.settings()
    for key, value in (
        ("WELD_VERTICES", True),
        ("APPLY_DEFAULT_MATERIALS", True),
        ("USE_WORLD_COORDS", True),
    ):
        try:
            s.set(key, value)
        except RuntimeError:
            log.debug("ifcopenshell setting %s unavailable; skipping", key)

    yielded = 0
    skipped = 0
    elements = list(model.by_type("IfcElement"))
    for element in elements:
        if yielded >= max_elements:
            log.warning(
                "IFC has more than %d elements; capping thumbnail geometry",
                max_elements,
            )
            break
        try:
            shape = ifcopenshell.geom.create_shape(s, element)
        except RuntimeError as exc:
            skipped += 1
            log.debug("skipped element with geometry error: %s", exc)
            continue
        if shape is None:
            continue
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        yield verts, faces
        yielded += 1
    if skipped:
        log.info("skipped %d IFC elements with broken geometry", skipped)


def _make_svg(
    verts_list: list[list[float]],
    faces_list: list[list[int]],
    out_path: Path,
    *,
    width: int = 800,
    height: int = 600,
):
    """Build a single isometric SVG of the merged mesh."""
    if not faces_list:
        # Empty model — emit a small placeholder so the pipeline can move on.
        fig, ax = plt.subplots(figsize=(width / _RASTER_DPI, height / _RASTER_DPI))
        ax.set_axis_off()
        ax.text(
            0.5, 0.5,
            "(empty IFC model)",
            ha="center", va="center",
            fontsize=14, color="#5F6368",
        )
        fig.savefig(out_path, format="svg", bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
        return

    fig = plt.figure(figsize=(width / _RASTER_DPI, height / _RASTER_DPI))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_axis_off()

    # Draw each element's triangles as a flat polycollection. Splitting per
    # element keeps memory lower than one big array concat.
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    for verts, faces in zip(verts_list, faces_list):
        if not faces:
            continue
        triangles = []
        for i in range(0, len(faces), 3):
            a, b, c = faces[i], faces[i + 1], faces[i + 2]
            triangles.append((
                (verts[a * 3], verts[a * 3 + 1], verts[a * 3 + 2]),
                (verts[b * 3], verts[b * 3 + 1], verts[b * 3 + 2]),
                (verts[c * 3], verts[c * 3 + 1], verts[c * 3 + 2]),
            ))
        if not triangles:
            continue
        coll = Poly3DCollection(
            triangles,
            facecolors=_FACE_COLOR,
            edgecolors=_EDGE_COLOR,
            linewidths=0.05,
            alpha=0.95,
        )
        ax.add_collection3d(coll)

    # Equal aspect ratio so the model isn't distorted.
    # Compute bounds from verts in chunks to avoid copying the whole list.
    minx = miny = minz = float("inf")
    maxx = maxy = maxz = float("-inf")
    for verts in verts_list:
        for i in range(0, len(verts), 3):
            x, y, z = verts[i], verts[i + 1], verts[i + 2]
            if x < minx: minx = x
            if y < miny: miny = y
            if z < minz: minz = z
            if x > maxx: maxx = x
            if y > maxy: maxy = y
            if z > maxz: maxz = z
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_zlim(minz, maxz)

    # Isometric viewpoint: equal elevation/azimuth around 30-35°.
    ax.view_init(elev=25, azim=-60)
    ax.set_box_aspect((1, 1, 1))

    fig.savefig(out_path, format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def render_thumbnail(document_path, out_path: Path) -> Path:
    """
    Render an SVG thumbnail of the IFC model at *document_path* into
    *out_path*. Returns the output path.
    """
    model = ifcopenshell.open(str(document_path))
    verts_list: list[list[float]] = []
    faces_list: list[list[int]] = []
    for verts, faces in _collect_geometry(model):
        verts_list.append(verts)
        faces_list.append(faces)
    _make_svg(verts_list, faces_list, out_path)
    return out_path
