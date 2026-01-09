from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import FakeEndpoint, FakeResponse
from src.services.exporters import resources_exporter as res_module


def test_xlsx_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_get(**kwargs):
        return FakeResponse(json_data=[{"id": 1, "metadata": "{}"}])

    monkeypatch.setattr(res_module, "get_fixed", lambda name: FakeEndpoint(get=fake_get))

    def fake_validate(self):
        return None

    monkeypatch.setattr(res_module.IDValidator, "validate", fake_validate)

    exporter = res_module.ResourcesExporter(category_id=1)

    def fake_to_excel(self, path, index=False):
        Path(path).write_text("x", encoding="utf-8")

    monkeypatch.setattr(pd.DataFrame, "to_excel", fake_to_excel, raising=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    out = exporter.xlsx_export("res.xlsx")
    assert out.exists()
