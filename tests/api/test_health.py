"""Tests for /health and /model-info endpoints."""

from pipeline import __version__


def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_model_info_returns_configuration(client) -> None:
    response = client.get("/model-info")

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "v1.0"
    assert body["method"] == "z_score"
    assert isinstance(body["min_history_periods"], int)
    assert isinstance(body["z_rising_threshold"], float)
    assert isinstance(body["z_falling_threshold"], float)
