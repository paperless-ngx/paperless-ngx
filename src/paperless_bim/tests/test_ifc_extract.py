"""
Smoke tests for paperless_bim.ifc_extract.

These tests build a tiny synthetic IFC model in-memory using ifcopenshell's
file construction API — no fixture file needed. They cover:
  - is_ifc_file() correctly sniffs the magic header
  - extract_text() produces the [PROJECT] / BUILDINGS / SPACES sections
  - extract_metadata() yields the expected key/value pairs
"""
from pathlib import Path

from django.test import SimpleTestCase

from paperless_bim.ifc_extract import extract_metadata
from paperless_bim.ifc_extract import extract_text
from paperless_bim.ifc_extract import is_ifc_file


def _build_minimal_ifc(tmp: Path) -> Path:
    import ifcopenshell

    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Project",
        LongName="Smoke test project",
    )
    site = model.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Default Site",
    )
    building = model.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Tower A",
        LongName="Residential tower",
    )
    storey = model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="L01",
    )
    space = model.create_entity(
        "IfcSpace",
        GlobalId=ifcopenshell.guid.new(),
        Name="Office",
        LongName="Open-plan office",
    )
    # Decomposition hierarchy
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=project,
        RelatedObjects=[site],
    )
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=site,
        RelatedObjects=[building],
    )
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=building,
        RelatedObjects=[storey],
    )
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=storey,
        RelatedObjects=[space],
    )
    # A wall so element counts are non-zero
    model.create_entity(
        "IfcWall",
        GlobalId=ifcopenshell.guid.new(),
        Name="W1",
    )
    # A material with a category
    model.create_entity(
        "IfcMaterial",
        Name="Concrete",
    )

    path = tmp / "tiny.ifc"
    model.write(str(path))
    return path


class IfcExtractTests(SimpleTestCase):
    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp(prefix="paperless-bim-test-"))
        self.path = _build_minimal_ifc(self.tmp)

    def test_is_ifc_file_true(self):
        self.assertTrue(is_ifc_file(self.path))

    def test_is_ifc_file_false_on_text(self):
        text_path = self.tmp / "note.txt"
        text_path.write_text("hello world")
        self.assertFalse(is_ifc_file(text_path))

    def test_extract_text_includes_project_and_building(self):
        text = extract_text(self.path)
        self.assertIn("[PROJECT]", text)
        self.assertIn("项目名：Test Project", text)
        self.assertIn("Tower A", text)
        self.assertIn("L01", text)
        self.assertIn("Office", text)
        self.assertIn("IFC schema：IFC4", text)

    def test_extract_metadata_emits_schema_and_counts(self):
        meta = extract_metadata(self.path)
        keys = {(m["prefix"], m["key"]) for m in meta}
        self.assertIn(("project", "schema"), keys)
        self.assertIn(("counts", "buildings"), keys)
        self.assertIn(("counts", "storeys"), keys)
        self.assertIn(("counts", "spaces"), keys)
        self.assertIn(("counts", "elements_total"), keys)
        # element_total should be >= 1 (the IfcWall we built)
        wall_total = next(
            m["value"] for m in meta
            if (m["prefix"], m["key"]) == ("counts", "elements_total")
        )
        self.assertGreaterEqual(wall_total, 1)
