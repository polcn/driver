def test_goal_create_list_patch_and_generate_plan(client):
    create = client.post(
        "/api/v1/goals/",
        json={
            "name": "Reduce weight",
            "metric": "weight_lbs",
            "goal_type": "target",
            "target_value": 190,
            "start_date": "2026-02-27",
            "target_date": "2026-06-01",
            "notes": "Cut body fat gradually",
        },
    )
    assert create.status_code == 201
    goal_id = create.json()["id"]

    list_response = client.get("/api/v1/goals/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    patch = client.patch(f"/api/v1/goals/{goal_id}", json={"active": 0})
    assert patch.status_code == 200
    assert patch.json()["active"] == 0

    generate = client.post(f"/api/v1/goals/{goal_id}/plans/generate")
    assert generate.status_code == 201
    generated_plan = generate.json()
    assert generated_plan["version"] == 1
    assert "Goal plan: Reduce weight" in generated_plan["plan"]

    manual = client.post(
        f"/api/v1/goals/{goal_id}/plans",
        json={"plan": "### Revised plan\n1. Increase protein."},
    )
    assert manual.status_code == 201
    assert manual.json()["version"] == 2

    plans = client.get(f"/api/v1/goals/{goal_id}/plans")
    assert plans.status_code == 200
    assert [item["version"] for item in plans.json()] == [2, 1]


def test_goal_validation_requires_target_value_or_direction(client):
    missing_target = client.post(
        "/api/v1/goals/",
        json={
            "name": "Drop sodium",
            "metric": "sodium_mg",
            "goal_type": "target",
            "start_date": "2026-02-27",
        },
    )
    assert missing_target.status_code == 422

    missing_direction = client.post(
        "/api/v1/goals/",
        json={
            "name": "Move HRV up",
            "metric": "hrv",
            "goal_type": "directional",
            "start_date": "2026-02-27",
        },
    )
    assert missing_direction.status_code == 422
