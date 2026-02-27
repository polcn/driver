def test_agent_today_summary_returns_aggregates_and_text(client):
    food_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "lunch",
            "name": "Chicken bowl",
            "calories": 620,
            "protein_g": 52,
            "sodium_mg": 740,
        },
    )
    assert food_response.status_code == 201

    steps_response = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-27",
            "metric": "steps",
            "value": 10250,
            "source": "oura",
        },
    )
    assert steps_response.status_code == 201

    response = client.get(
        "/api/v1/agent/today-summary",
        params={"target_date": "2026-02-27"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["food"]["calories"] == 620.0
    assert payload["activity"]["steps"] == 10250.0
    assert "calories 620.0" in payload["summary_text"]


def test_agent_week_summary_and_query_endpoint(client):
    for recorded_date, calories in [
        ("2026-02-25", 500),
        ("2026-02-26", 550),
        ("2026-02-27", 650),
    ]:
        response = client.post(
            "/api/v1/food/",
            json={
                "recorded_date": recorded_date,
                "meal_type": "dinner",
                "name": "Meal",
                "calories": calories,
                "protein_g": 40,
            },
        )
        assert response.status_code == 201

    week_response = client.get(
        "/api/v1/agent/week-summary",
        params={"ending": "2026-02-27"},
    )
    assert week_response.status_code == 200
    assert week_response.json()["food"]["calories"] == 1700.0

    query_response = client.get(
        "/api/v1/agent/query",
        params={"query_type": "week_summary", "target_date": "2026-02-27"},
    )
    assert query_response.status_code == 200
    assert query_response.json()["end"] == "2026-02-27"


def test_agent_daily_suggestion_autocreates_and_metric_trend_requires_metric(client):
    suggestion_response = client.get(
        "/api/v1/agent/daily-suggestion",
        params={"target_date": "2026-03-02", "create_if_missing": "true"},
    )
    assert suggestion_response.status_code == 200
    payload = suggestion_response.json()
    assert payload["suggestion_date"] == "2026-03-02"
    assert payload["suggestion"]

    invalid_trend = client.get(
        "/api/v1/agent/query",
        params={"query_type": "metric_trend", "target_date": "2026-02-27"},
    )
    assert invalid_trend.status_code == 422


def test_validation_hardening_for_phase3_routers(client):
    supplements_response = client.post(
        "/api/v1/supplements/",
        json={"name": "Creatine", "active": 2},
    )
    assert supplements_response.status_code == 422

    labs_response = client.post(
        "/api/v1/labs/",
        json={
            "drawn_date": "2026-02-14",
            "panel": "Lipid Panel",
            "marker": "LDL",
            "value": 130,
            "unit": "mg/dL",
            "reference_low": 200,
            "reference_high": 100,
        },
    )
    assert labs_response.status_code == 422


def test_agent_log_food_and_log_workout_endpoints(client):
    food_response = client.post(
        "/api/v1/agent/log-food",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "dinner",
            "name": "Salmon bowl",
            "calories": 640,
            "protein_g": 45,
            "notes": "logged from telegram",
        },
    )
    assert food_response.status_code == 201
    assert food_response.json()["source"] == "agent"
    assert food_response.json()["name"] == "Salmon bowl"

    workout_response = client.post(
        "/api/v1/agent/log-workout",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Bike intervals",
            "duration_min": 32,
            "calories_burned": 280,
        },
    )
    assert workout_response.status_code == 201
    assert workout_response.json()["source"] == "agent"
    assert workout_response.json()["session_type"] == "cardio"


def test_agent_sleep_query_endpoint(client):
    create_sleep = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "duration_min": 430,
            "sleep_score": 75,
            "source": "oura",
        },
    )
    assert create_sleep.status_code == 201

    query = client.get("/api/v1/agent/sleep", params={"target_date": "2026-02-27"})
    assert query.status_code == 200
    payload = query.json()
    assert payload["date"] == "2026-02-27"
    assert payload["sleep"]["sleep_score"] == 75
