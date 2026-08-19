"""Tests for GET /skills/{skill_name}."""


def test_skill_detail_found(client) -> None:
    response = client.get("/skills/Python")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["skill"] == "Python"
    assert body["data"] is not None
    assert body["data"]["skill"] == "Python"
    assert body["data"]["current_mentions"] == 120


def test_skill_detail_case_insensitive(client) -> None:
    response = client.get("/skills/kubernetes")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["data"]["z_score"] == 2.68


def test_skill_detail_not_found(client) -> None:
    response = client.get("/skills/COBOL")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["data"] is None
    assert "model_version" in body
    assert "generated_at" in body


def test_skill_detail_falling_skill(client) -> None:
    response = client.get("/skills/Docker")

    body = response.json()
    assert body["found"] is True
    assert body["data"]["trend"] == "falling"
    assert body["data"]["direction"] == "down"
    assert body["data"]["z_score"] == -1.5
