def test_dashboard_today_includes_food_targets_and_empty_sections(client):
    create_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "lunch",
            "name": "Chicken bowl",
            "calories": 620,
            "protein_g": 52,
            "carbs_g": 44,
            "fat_g": 18,
            "fiber_g": 6,
            "sodium_mg": 740,
        },
    )
    assert create_response.status_code == 201

    response = client.get(
        "/api/v1/dashboard/today",
        params={"target_date": "2026-02-27"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-02-27"
    assert payload["food"]["entry_count"] == 1
    assert payload["food"]["calories"] == 620
    assert payload["targets"]["calories"] == 2000
    assert payload["exercise"] == []
    assert payload["sleep"] is None
    assert payload["suggestion"] is None


def test_dashboard_week_groups_food_and_exercise_by_day(client):
    food_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-25",
            "meal_type": "dinner",
            "name": "Salmon",
            "calories": 500,
            "protein_g": 40,
            "sodium_mg": 450,
        },
    )
    assert food_response.status_code == 201

    session_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "snack",
            "name": "Greek yogurt",
            "calories": 180,
            "protein_g": 18,
            "sodium_mg": 60,
        },
    )
    assert session_response.status_code == 201

    response = client.get("/api/v1/dashboard/week", params={"ending": "2026-02-27"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["start"] == "2026-02-21"
    assert payload["end"] == "2026-02-27"
    assert payload["food_by_day"] == [
        {
            "recorded_date": "2026-02-25",
            "calories": 500.0,
            "protein_g": 40.0,
            "sodium_mg": 450.0,
            "alcohol_calories": None,
        },
        {
            "recorded_date": "2026-02-27",
            "calories": 180.0,
            "protein_g": 18.0,
            "sodium_mg": 60.0,
            "alcohol_calories": None,
        },
    ]
    assert payload["exercise_by_day"] == []


def test_dashboard_trends_returns_cross_domain_series(client):
    food_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-26",
            "meal_type": "dinner",
            "name": "Steak",
            "calories": 700,
            "protein_g": 55,
            "sodium_mg": 900,
            "alcohol_calories": 120,
        },
    )
    assert food_response.status_code == 201

    session_response = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Bike",
            "duration_min": 42,
            "calories_burned": 360,
        },
    )
    assert session_response.status_code == 201

    sleep_response = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "duration_min": 455,
            "sleep_score": 81,
            "hrv": 47.5,
            "resting_hr": 56,
            "readiness_score": 79,
        },
    )
    assert sleep_response.status_code == 201

    weight_first = client.post(
        "/api/v1/metrics/",
        json={
            "recorded_date": "2026-02-27",
            "metric": "weight_lbs",
            "value": 210.4,
        },
    )
    assert weight_first.status_code == 201

    weight_second = client.post(
        "/api/v1/metrics/",
        json={
            "recorded_date": "2026-02-27",
            "metric": "weight_lbs",
            "value": 209.9,
        },
    )
    assert weight_second.status_code == 201

    waist_response = client.post(
        "/api/v1/metrics/",
        json={
            "recorded_date": "2026-02-27",
            "metric": "waist_in",
            "value": 38.25,
        },
    )
    assert waist_response.status_code == 201

    response = client.get("/api/v1/dashboard/trends", params={"days": 7, "ending": "2026-02-27"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["start"] == "2026-02-21"
    assert payload["end"] == "2026-02-27"
    assert payload["days"] == 7
    assert payload["food_by_day"] == [
        {
            "recorded_date": "2026-02-26",
            "calories": 700.0,
            "protein_g": 55.0,
            "sodium_mg": 900.0,
            "alcohol_calories": 120.0,
        }
    ]
    assert payload["exercise_by_day"] == [
        {
            "recorded_date": "2026-02-27",
            "sessions": 1,
            "duration_min": 42,
            "calories_burned": 360.0,
        }
    ]
    assert payload["sleep_by_day"] == [
        {
            "recorded_date": "2026-02-27",
            "duration_min": 455,
            "sleep_score": 81,
            "hrv": 47.5,
            "resting_hr": 56,
            "readiness_score": 79,
        }
    ]
    # Uses the latest metric entry for the same date.
    assert payload["weight_by_day"] == [{"recorded_date": "2026-02-27", "value": 209.9}]
    assert payload["waist_by_day"] == [{"recorded_date": "2026-02-27", "value": 38.25}]
