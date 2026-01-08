from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import FakeEndpoint, FakeResponse
from src.services.exporters import experiments_exporter as exp_module


def test_fetch_data(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data={"data": [{"id": 1}]})

    def fake_paged_fetch(get_page, **kwargs):
        return get_page(limit=kwargs["page_size"], offset=kwargs["start_offset"])

    monkeypatch.setattr(exp_module, "get_fixed", lambda name: FakeEndpoint(get=fake_get))
    monkeypatch.setattr(exp_module, "paged_fetch", fake_paged_fetch)

    exporter = exp_module.ExperimentsExporter()
    df = exporter.fetch_data()
    assert not df.empty


def test_process_data_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = exp_module.ExperimentsExporter()
    monkeypatch.setattr(exporter, "fetch_data", lambda: pd.DataFrame())
    assert exporter.process_data().empty


def test_xlsx_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exporter = exp_module.ExperimentsExporter()
    monkeypatch.setattr(exporter, "process_data", lambda: pd.DataFrame({"a": [1]}))

    def fake_to_excel(self, path, index=False):
        Path(path).write_text("x", encoding="utf-8")

    monkeypatch.setattr(pd.DataFrame, "to_excel", fake_to_excel, raising=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    out = exporter.xlsx_export("exp.xlsx")
    assert out is not None
    assert out.exists()
