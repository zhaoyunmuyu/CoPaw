# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swe.app.routers.local_models import router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_server_status_reports_local_models_unsupported() -> None:
    client = _build_client()

    response = client.get("/local-models/server")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "installable": False,
        "installed": False,
        "port": None,
        "model_name": None,
        "message": "Local models are no longer supported.",
    }


def test_local_model_listing_returns_empty_shell_response() -> None:
    client = _build_client()

    response = client.get("/local-models/models")

    assert response.status_code == 200
    assert response.json() == []


def test_download_progress_reports_idle_shell_response() -> None:
    client = _build_client()

    server_response = client.get("/local-models/server/download")
    model_response = client.get("/local-models/models/download")

    expected = {
        "status": "idle",
        "model_name": None,
        "downloaded_bytes": 0,
        "total_bytes": None,
        "speed_bytes_per_sec": 0.0,
        "source": None,
        "error": None,
        "local_path": None,
    }

    assert server_response.status_code == 200
    assert server_response.json() == expected
    assert model_response.status_code == 200
    assert model_response.json() == expected


def test_mutating_local_model_endpoints_return_gone() -> None:
    client = _build_client()

    responses = [
        client.post("/local-models/server/download"),
        client.delete("/local-models/server/download"),
        client.post("/local-models/server", json={"model_id": "test-model"}),
        client.delete("/local-models/server"),
        client.post(
            "/local-models/models/download",
            json={"model_name": "test-model"},
        ),
        client.delete("/local-models/models/download"),
    ]

    for response in responses:
        assert response.status_code == 410
        assert response.json() == {
            "detail": "Local model management has been removed from the backend.",
        }
