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

    response = client.get("/api/v1/dashboard/today", params={"target_date": "2026-02-27"})

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
