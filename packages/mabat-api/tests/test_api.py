"""mabat-api: every endpoint answers with mabat's own JSON shape."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from mabat_api import __version__, create_app  # noqa: E402

import mabat  # noqa: E402

client = TestClient(create_app())


def test_health_and_version() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True and payload["mabat_version"] == mabat.__version__
    assert __version__


def test_sections_lists_names_and_options() -> None:
    payload = client.get("/sections").json()
    assert payload["sections"] == list(mabat.section_names())
    assert payload["options"]["counters"] == ["gpu"]


def test_section_endpoint_returns_section_shape() -> None:
    payload = client.get("/sections/memory").json()
    assert set(payload) == {"name", "collected_at", "available", "data", "problems"}
    assert payload["name"] == "memory" and payload["available"] is True


def test_section_options_route_and_unknown_is_404() -> None:
    payload = client.get("/sections/system", params={"top": 0, "sample": 0}).json()
    assert payload["data"]["processes"]["top_n"] == 0
    payload = client.get("/sections/storage", params={"smart": "false"}).json()
    assert payload["data"]["smart"] is None
    assert client.get("/sections/nope").status_code == 404


def test_snapshot_trims_redacts_and_rejects_bad_names() -> None:
    payload = client.get(
        "/snapshot", params={"only": "cpu,memory", "sample": 0, "redact": "true"}
    ).json()
    assert payload["hostname"] == mabat.MASK
    assert payload["memory"]["available"] is True
    assert payload["gpu"]["problems"][0]["kind"] == "skipped"
    assert client.get("/snapshot", params={"only": "nope"}).status_code == 400


def test_connections_and_problems() -> None:
    response = client.get("/connections", params={"kind": "inet", "redact": "true"})
    assert response.status_code == 200
    payload = response.json()
    if payload["available"] and payload["data"]["connections"]:
        assert payload["data"]["connections"][0]["local_address"] == mabat.MASK
    problems = client.get("/problems").json()
    assert isinstance(problems, list)
    assert all({"section", "source", "kind", "detail"} <= set(p) for p in problems)


def test_openapi_documents_every_route() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/health",
        "/sections",
        "/sections/{name}",
        "/snapshot",
        "/connections",
        "/problems",
    } <= set(paths)
