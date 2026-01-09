from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.services.exporters import experiments_exporter as exp_module
from tests.conftest import FakeEndpoint, FakeResponse


def test_fetch_data(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(**kwargs: object) -> FakeResponse:
        return FakeResponse(json_data={"data": [{"id": 1}]})

    def fake_paged_fetch(
        get_page: Callable[..., list[dict[str, Any]]], **kwargs: object
    ) -> list[dict[str, Any]]:
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

    def fake_to_excel(self: object, path: str | Path, index: bool = False) -> None:
        Path(path).write_text("x", encoding="utf-8")

    monkeypatch.setattr(pd.DataFrame, "to_excel", fake_to_excel, raising=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    out = exporter.xlsx_export("exp.xlsx")
    assert out is not None
    assert out.exists()
