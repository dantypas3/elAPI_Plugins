from __future__ import annotations

from pathlib import Path

import pytest

from src.factories.exporter_factory import ExporterFactory
from src.factories.importer_factory import ImporterFactory
from src.services.exporters.resources_exporter import ResourcesExporter
from src.services.importers.resources_importer import ResourcesImporter


def test_exporter_factory_returns_resources() -> None:
    exporter = ExporterFactory.get_exporter("resources", obj_id=1)
    assert isinstance(exporter, ResourcesExporter)


def test_exporter_factory_unknown_raises() -> None:
    with pytest.raises(ValueError):
        ExporterFactory.get_exporter("missing")


def test_importer_factory_returns_resources(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("title\nA\n", encoding="utf-8")
    importer = ImporterFactory.get_importer("resources", csv_path=csv_path)
    assert isinstance(importer, ResourcesImporter)


def test_importer_factory_unknown_raises() -> None:
    with pytest.raises(ValueError):
        ImporterFactory.get_importer("unknown")
