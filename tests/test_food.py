def test_food_entry_lifecycle(client):
    response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "breakfast",
            "name": "Protein shake",
            "calories": 240,
            "protein_g": 48,
            "carbs_g": 6,
            "fat_g": 2,
            "fiber_g": 1,
            "sodium_mg": 180,
            "source": "agent",
            "notes": "post-workout",
        },
    )

    assert response.status_code == 201
    entry = response.json()
    assert entry["name"] == "Protein shake"
    assert entry["notes"] == "post-workout"

    entry_id = entry["id"]

    patch_response = client.patch(
        f"/api/v1/food/{entry_id}",
        json={"calories": 250, "notes": None},
    )
    assert patch_response.status_code == 200
    updated_entry = patch_response.json()
    assert updated_entry["calories"] == 250
    assert updated_entry["notes"] is None

    summary_response = client.get("/api/v1/food/summary", params={"date": "2026-02-27"})
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["entry_count"] == 1
    assert summary["calories"] == 250
    assert summary["protein_g"] == 48
    assert summary["targets"]["calories"] == 2000

    delete_response = client.delete(f"/api/v1/food/{entry_id}")
    assert delete_response.status_code == 204

    post_delete_summary = client.get(
        "/api/v1/food/summary",
        params={"date": "2026-02-27"},
    )
    assert post_delete_summary.status_code == 200
    assert post_delete_summary.json()["entry_count"] == 0


def test_food_list_excludes_soft_deleted_entries(client):
    create_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "snack",
            "name": "Jerky",
        },
    )
    assert create_response.status_code == 201

    entry_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v1/food/{entry_id}")
    assert delete_response.status_code == 204

    response = client.get("/api/v1/food/", params={"date": "2026-02-27"})
    assert response.status_code == 200
    assert response.json() == []


def test_food_summary_uses_latest_effective_target_for_each_metric(
    client, db_module_fixture
):
    conn = db_module_fixture.get_db()
    try:
        conn.execute(
            """INSERT INTO targets
               (metric, value, effective_date, notes)
               VALUES (?, ?, ?, ?)""",
            ("calories", 1900, "2026-02-26", "updated target"),
        )
        conn.execute(
            """INSERT INTO targets
               (metric, value, effective_date, notes)
               VALUES (?, ?, ?, ?)""",
            ("protein_g", 200, "2026-02-28", "future target"),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/v1/food/summary", params={"date": "2026-02-27"})

    assert response.status_code == 200
    assert response.json()["targets"] == {
        "calories": 1900.0,
        "protein_g": 180.0,
        "sodium_mg": 2300.0,
    }


def test_food_weekly_summary_groups_days_in_range(client):
    first_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-22",
            "meal_type": "breakfast",
            "name": "Eggs",
            "calories": 300,
            "protein_g": 24,
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/food/",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "dinner",
            "name": "Steak",
            "calories": 700,
            "protein_g": 60,
        },
    )
    assert second_response.status_code == 201

    response = client.get("/api/v1/food/summary/week", params={"ending": "2026-02-27"})

    assert response.status_code == 200
    assert response.json() == {
        "ending": "2026-02-27",
        "days": [
            {
                "recorded_date": "2026-02-22",
                "entry_count": 1,
                "calories": 300.0,
                "protein_g": 24.0,
                "carbs_g": None,
                "fat_g": None,
                "fiber_g": None,
                "sodium_mg": None,
                "alcohol_calories": None,
            },
            {
                "recorded_date": "2026-02-27",
                "entry_count": 1,
                "calories": 700.0,
                "protein_g": 60.0,
                "carbs_g": None,
                "fat_g": None,
                "fiber_g": None,
                "sodium_mg": None,
                "alcohol_calories": None,
            },
        ],
    }


def test_food_from_photo_creates_estimated_entry_with_photo_url(client):
    response = client.post(
        "/api/v1/food/from-photo",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "drink",
            "description": "Protein shake with almond milk",
            "photo_url": "https://example.com/photo.jpg",
            "servings": 1.0,
            "source": "agent",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["is_estimated"] == 1
    assert payload["photo_url"] == "https://example.com/photo.jpg"
    assert payload["source"] == "agent"
    assert payload["protein_g"] >= 30
    assert payload["analysis_method"] in {"heuristic", "vision"}
    assert 0 <= payload["analysis_confidence"] <= 1
    assert "Estimated from photo input" in payload["notes"]


def test_food_from_photo_applies_manual_overrides(client):
    response = client.post(
        "/api/v1/food/from-photo",
        json={
            "recorded_date": "2026-02-27",
            "meal_type": "drink",
            "description": "Protein shake",
            "photo_url": "https://example.com/photo.jpg",
            "servings": 1.0,
            "source": "agent",
            "calories": 333,
            "protein_g": 44,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["calories"] == 333
    assert payload["protein_g"] == 44


def test_photo_estimate_endpoint_returns_estimate_and_confidence(client):
    response = client.post(
        "/api/v1/food/photo-estimate",
        json={
            "description": "Salad with grilled chicken",
            "photo_url": "https://example.com/photo.jpg",
            "servings": 1.0,
            "use_vision": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_method"] == "heuristic"
    assert 0 <= payload["analysis_confidence"] <= 1
    assert payload["estimate"]["name"] == "Salad with grilled chicken"
