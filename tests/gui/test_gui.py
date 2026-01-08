from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import FakeEndpoint, FakeResponse, write_csv
import gui.gui as gui


def test_index_get(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": [{"title": "A"}]})

    def fake_paged_fetch(get_page, **kwargs):
        return get_page(limit=kwargs["page_size"], offset=kwargs["start_offset"])

    monkeypatch.setattr(gui.endpoints, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(gui, "paged_fetch", fake_paged_fetch)

    gui.app.testing = True
    client = gui.app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200


def test_export_resources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": []})

    def fake_paged_fetch(get_page, **kwargs):
        return []

    monkeypatch.setattr(gui.endpoints, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(gui, "paged_fetch", fake_paged_fetch)

    class DummyExporter:
        def xlsx_export(self, filename=None):
            out = tmp_path / "res.xlsx"
            out.write_text("x", encoding="utf-8")
            return out

    monkeypatch.setattr(gui.ExporterFactory, "get_exporter", lambda *args, **kwargs: DummyExporter())

    gui.app.testing = True
    client = gui.app.test_client()
    resp = client.post("/", data={"export_type": "resources", "category": "1"})
    assert resp.status_code == 200


def test_import_resources_from_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": []})

    def fake_paged_fetch(get_page, **kwargs):
        return []

    monkeypatch.setattr(gui.endpoints, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(gui, "paged_fetch", fake_paged_fetch)

    class DummyImporter:
        def create_all_from_csv(self):
            return ["1", "2"]

    monkeypatch.setattr(gui.ImporterFactory, "get_importer", lambda *args, **kwargs: DummyImporter())

    csv_path = write_csv(tmp_path / "imp.csv", ["title"], [["t"]])

    gui.app.testing = True
    client = gui.app.test_client()
    resp = client.post(
        "/",
        data={
            "export_type": "imports",
            "category": "1",
            "import_path": str(csv_path),
            "import_target": "resources",
        },
    )
    assert resp.status_code == 302


def test_import_unknown_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": []})

    def fake_paged_fetch(get_page, **kwargs):
        return []

    monkeypatch.setattr(gui.endpoints, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(gui, "paged_fetch", fake_paged_fetch)

    gui.app.testing = True
    client = gui.app.test_client()
    resp = client.post(
        "/",
        data={
            "export_type": "imports",
            "category": "1",
            "import_path": str(tmp_path / "missing.csv"),
            "import_target": "unknown",
        },
    )
    assert resp.status_code == 302


def test_import_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": []})

    def fake_paged_fetch(get_page, **kwargs):
        return []

    monkeypatch.setattr(gui.endpoints, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(gui, "paged_fetch", fake_paged_fetch)

    gui.app.testing = True
    client = gui.app.test_client()
    resp = client.post(
        "/",
        data={
            "export_type": "imports",
            "category": "1",
            "import_path": str(tmp_path / "missing.csv"),
            "import_target": "resources",
        },
    )
    assert resp.status_code == 302
