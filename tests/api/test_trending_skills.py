"""Tests for GET /trending-skills."""


def test_trending_skills_default_limit(client) -> None:
    response = client.get("/trending-skills")

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "v1.0"
    assert "generated_at" in body
    assert body["period_count"] == 4
    assert body["limit"] == 10
    assert isinstance(body["skills"], list)
    assert len(body["skills"]) <= 10


def test_trending_skills_ranked_by_z_score(client) -> None:
    response = client.get("/trending-skills?limit=4")

    skills = response.json()["skills"]
    assert skills[0]["skill"] == "Kubernetes"
    assert skills[0]["z_score"] == 2.68
    assert skills[0]["trend"] == "rising"
    assert skills[0]["direction"] == "up"


def test_trending_skills_limit_query_param(client) -> None:
    response = client.get("/trending-skills?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert len(body["skills"]) == 2
    assert body["total_skills"] == 4


def test_trending_skills_direction_filter_up(client) -> None:
    response = client.get("/trending-skills?direction=up")

    assert response.status_code == 200
    skills = response.json()["skills"]
    assert all(s["direction"] == "up" for s in skills)
    assert len(skills) == 2


def test_trending_skills_direction_filter_down(client) -> None:
    response = client.get("/trending-skills?direction=down")

    skills = response.json()["skills"]
    assert len(skills) == 1
    assert skills[0]["skill"] == "Docker"


def test_trending_skills_direction_filter_flat(client) -> None:
    response = client.get("/trending-skills?direction=flat")

    skills = response.json()["skills"]
    assert len(skills) == 1
    assert skills[0]["skill"] == "SQL"


def test_trending_skills_invalid_direction_rejected(client) -> None:
    response = client.get("/trending-skills?direction=sideways")

    assert response.status_code == 422


def test_trending_skills_limit_too_low_rejected(client) -> None:
    response = client.get("/trending-skills?limit=0")

    assert response.status_code == 422


def test_trending_skills_limit_too_high_rejected(client) -> None:
    response = client.get("/trending-skills?limit=201")

    assert response.status_code == 422


def test_trending_skills_response_schema(client) -> None:
    response = client.get("/trending-skills?limit=1")

    skill = response.json()["skills"][0]
    assert "skill" in skill
    assert "current_mentions" in skill
    assert "previous_mentions" in skill
    assert "change" in skill
    assert "change_percent" in skill
    assert "z_score" in skill
    assert "trend" in skill
    assert "direction" in skill
