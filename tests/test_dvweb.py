"""Offline test for scripts/dvweb.py: a file goes to Dataverse as raw bytes, not as JSON."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dvweb  # noqa: E402


class FakeResponse:
    status_code = 204
    content = b""
    headers: dict[str, str] = {}


class FakeSession:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.sent.append({"method": method, "url": url, **kwargs})
        return FakeResponse()


@pytest.fixture
def dv(monkeypatch: pytest.MonkeyPatch) -> dvweb.Dataverse:
    monkeypatch.setenv("DATAVERSE_URL", "https://example.crm.dynamics.test/")
    monkeypatch.setattr(dvweb.auth, "load_env", lambda: None)
    monkeypatch.setattr(dvweb.auth, "get_token", lambda: "token")
    monkeypatch.setattr(dvweb.auth, "get_plugin_headers", lambda _skill: {"User-Agent": "test"})
    client = dvweb.Dataverse("dv-data")
    client._http = FakeSession()
    return client


def test_a_file_is_sent_as_raw_bytes_with_its_name(dv: dvweb.Dataverse) -> None:
    pdf = b"%PDF-1.7\n\xff\x00binary"
    dv.upload_file("vz_contracts(abc)", "vz_document", "contract.pdf", pdf)
    (sent,) = dv._http.sent
    assert (sent["method"], sent["url"]) == ("PATCH", "https://example.crm.dynamics.test/api/data/v9.2/vz_contracts(abc)/vz_document")
    assert sent["data"] == pdf and sent["json"] is None
    assert sent["headers"]["Content-Type"] == "application/octet-stream"
    assert sent["headers"]["x-ms-file-name"] == "contract.pdf"


def test_a_json_request_still_sends_json(dv: dvweb.Dataverse) -> None:
    dv.request("PATCH", "vz_contracts(abc)", body={"vz_name": "x"})
    (sent,) = dv._http.sent
    assert sent["json"] == {"vz_name": "x"} and sent["data"] is None
    assert sent["headers"]["Content-Type"].startswith("application/json")
