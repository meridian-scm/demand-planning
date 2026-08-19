"""Integration tests for the initial API surface."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_application_health_is_live(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "meridian-backend",
        "version": "0.1.0",
    }


def test_readiness_is_honest_without_reference_artifacts(client: TestClient) -> None:
    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "data_ready": False,
        "checks": {"artifact_reader": False, "reference_manifest": False},
        "detail": "Reference data manifest is not available; data endpoints are not ready.",
    }


def test_readiness_stays_honest_when_only_a_manifest_exists(
    client: TestClient, artifact_directory: Path
) -> None:
    artifact_directory.mkdir()
    (artifact_directory / "manifest.json").write_text("{}", encoding="utf-8")

    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "data_ready": False,
        "checks": {"artifact_reader": False, "reference_manifest": True},
        "detail": "Reference manifest exists, but the artifact reader is not implemented yet.",
    }


def test_openapi_uses_the_expected_api_paths(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/ready" in paths
