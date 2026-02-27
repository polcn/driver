def test_coaching_latest_returns_empty_payload(client):
    response = client.get("/api/v1/coaching/digests/latest")
    assert response.status_code == 200
    assert response.json() == {"daily": None, "weekly": None}


def test_generate_daily_digest_persists_and_returns_highlights(client):
    food_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "lunch",
            "name": "Chicken bowl",
            "calories": 700,
            "protein_g": 60,
            "sodium_mg": 900,
        },
    )
    assert food_response.status_code == 201

    sleep_response = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "duration_min": 435,
            "sleep_score": 78,
            "readiness_score": 75,
            "source": "oura",
        },
    )
    assert sleep_response.status_code == 201

    exercise_response = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Bike",
            "duration_min": 40,
            "source": "manual",
        },
    )
    assert exercise_response.status_code == 201

    response = client.post(
        "/api/v1/coaching/digests/generate-daily",
        params={"target_date": "2026-02-27"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["digest_type"] == "daily"
    assert payload["digest_date"] == "2026-02-27"
    assert payload["summary"].startswith("Daily digest for 2026-02-27")
    assert len(payload["highlights"]) >= 3

    latest_response = client.get("/api/v1/coaching/digests/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["daily"]["digest_date"] == "2026-02-27"
    assert latest_payload["weekly"] is None


def test_generate_weekly_digest_includes_week_range_summary(client):
    for recorded_date, calories in [
        ("2026-02-22", 1900),
        ("2026-02-24", 2000),
        ("2026-02-27", 2100),
    ]:
        food_response = client.post(
            "/api/v1/food/",
            json={
                "recorded_date": recorded_date,
                "meal_type": "dinner",
                "name": f"Meal {recorded_date}",
                "calories": calories,
                "protein_g": 170,
                "sodium_mg": 2200,
            },
        )
        assert food_response.status_code == 201

    for recorded_date in ["2026-02-23", "2026-02-25"]:
        exercise_response = client.post(
            "/api/v1/exercise/sessions",
            json={
                "recorded_date": recorded_date,
                "session_type": "strength",
                "name": "Lift",
                "duration_min": 55,
                "source": "manual",
            },
        )
        assert exercise_response.status_code == 201

    response = client.post(
        "/api/v1/coaching/digests/generate-weekly",
        params={"ending": "2026-02-27"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["digest_type"] == "weekly"
    assert payload["digest_date"] == "2026-02-27"
    assert payload["summary"].startswith("Weekly digest for 2026-02-21 to 2026-02-27")
    assert any("Training volume" in line for line in payload["highlights"])

    latest_response = client.get("/api/v1/coaching/digests/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["weekly"]["digest_date"] == "2026-02-27"
