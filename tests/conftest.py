from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Callable, Optional


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        headers: Optional[dict] = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}
        self.text = text

    def json(self) -> Any:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


class FakeEndpoint:
    def __init__(
        self,
        get: Optional[Callable[..., FakeResponse]] = None,
        post: Optional[Callable[..., FakeResponse]] = None,
        patch: Optional[Callable[..., FakeResponse]] = None,
    ) -> None:
        self._get = get
        self._post = post
        self._patch = patch

    def get(self, *args, **kwargs) -> FakeResponse:
        if callable(self._get):
            return self._get(*args, **kwargs)
        if self._get is None:
            raise AssertionError("FakeEndpoint.get was called without a stub")
        return self._get

    def post(self, *args, **kwargs) -> FakeResponse:
        if callable(self._post):
            return self._post(*args, **kwargs)
        if self._post is None:
            raise AssertionError("FakeEndpoint.post was called without a stub")
        return self._post

    def patch(self, *args, **kwargs) -> FakeResponse:
        if callable(self._patch):
            return self._patch(*args, **kwargs)
        if self._patch is None:
            raise AssertionError("FakeEndpoint.patch was called without a stub")
        return self._patch


def write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return path
