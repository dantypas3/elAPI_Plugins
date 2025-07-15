# tests/test_client.py
"""Unit tests for LabfolderClient."""

import pytest
import json
from requests import Response, Session
from responses import RequestsMock

from labfolder_migration import LabfolderClient



@pytest.fixture
def client():
    """Create a LabfolderClient with a fake base_url and no real HTTP calls."""
    client = LabfolderClient(email="user@example.com",
                             password="secret",
                             base_url="https://api.labfolder.test")
    return client


def make_response(status: int, payload: dict) -> Response:
    """Helper to build a requests.Response with JSON and status code."""
    resp = Response()
    resp.status_code = status
    resp._content = json.dumps(payload).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    return resp


def test_login_success(monkeypatch):
    """login() sets _token and Authorization header on success."""
    fake_resp = make_response(200, {"token": " abc123 "})
    monkeypatch.setattr(Session, "post", lambda self, url, json: fake_resp)

    client = LabfolderClient("u", "p", "https://api")
    token = client.login()
    assert token == "abc123"
    assert client._token == "abc123"
    assert client._session.headers["Authorization"] == "Bearer abc123"


def test_login_http_error(monkeypatch):
    """login() raises RuntimeError on HTTP error status."""
    bad = make_response(401, {"error": "unauthorized"})
    monkeypatch.setattr(Session, "post", lambda self, url, json: bad)
    client = LabfolderClient("u", "p", "https://api")
    with pytest.raises(RuntimeError) as ei:
        client.login()
    assert "Login failed (401)" in str(ei.value)


def test_get_calls_correct_url(monkeypatch):
    """get() should GET the correct URL with params."""
    fake_resp = make_response(200, {"data": []})
    captured = {}
    def fake_get(self, url, params=None):
        captured['url'] = url
        captured['params'] = params
        return fake_resp

    monkeypatch.setattr(Session, "get", fake_get)
    client = LabfolderClient("u", "p", "https://api/v2")
    resp = client.get("entries", params={"limit": 10})
    assert resp == fake_resp
    assert captured['url'] == "https://api/v2/entries"
    assert captured['params'] == {"limit": 10}