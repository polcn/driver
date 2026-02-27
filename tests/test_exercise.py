def test_exercise_session_create_and_list_by_date(client):
    first_response = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Stair machine",
            "duration_min": 35,
            "calories_burned": 420,
            "avg_heart_rate": 122,
            "max_heart_rate": 139,
            "source": "manual",
            "notes": "kept it in zone 2",
        },
    )
    assert first_response.status_code == 201
    assert first_response.json()["name"] == "Stair machine"

    second_response = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-26",
            "session_type": "strength",
            "name": "Upper body",
            "duration_min": 55,
            "source": "manual",
        },
    )
    assert second_response.status_code == 201

    response = client.get("/api/v1/exercise/sessions", params={"date": "2026-02-27"})
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": first_response.json()["id"],
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Stair machine",
            "duration_min": 35,
            "calories_burned": 420.0,
            "avg_heart_rate": 122,
            "max_heart_rate": 139,
            "source": "manual",
            "notes": "kept it in zone 2",
            "created_at": response.json()[0]["created_at"],
            "deleted_at": None,
        }
    ]


def test_exercise_session_list_without_date_returns_recent_entries(client):
    client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-25",
            "session_type": "walk",
            "name": "Neighborhood walk",
            "duration_min": 25,
            "source": "manual",
        },
    )
    client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "strength",
            "name": "Lower body",
            "duration_min": 50,
            "source": "manual",
        },
    )

    response = client.get("/api/v1/exercise/sessions")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["recorded_date"] == "2026-02-27"
    assert payload[1]["recorded_date"] == "2026-02-25"


def test_exercise_sets_create_and_list_for_session(client):
    session_response = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "strength",
            "name": "Push day",
            "duration_min": 60,
            "source": "manual",
        },
    )
    session_id = session_response.json()["id"]

    first_set = client.post(
        f"/api/v1/exercise/sessions/{session_id}/sets",
        json={
            "exercise_name": "Bench press",
            "set_number": 1,
            "weight_lbs": 185,
            "reps": 5,
            "notes": "smooth",
        },
    )
    assert first_set.status_code == 201

    second_set = client.post(
        f"/api/v1/exercise/sessions/{session_id}/sets",
        json={
            "exercise_name": "Bench press",
            "set_number": 2,
            "weight_lbs": 185,
            "reps": 4,
        },
    )
    assert second_set.status_code == 201

    response = client.get(f"/api/v1/exercise/sessions/{session_id}/sets")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": first_set.json()["id"],
            "session_id": session_id,
            "exercise_name": "Bench press",
            "set_number": 1,
            "weight_lbs": 185.0,
            "reps": 5,
            "notes": "smooth",
        },
        {
            "id": second_set.json()["id"],
            "session_id": session_id,
            "exercise_name": "Bench press",
            "set_number": 2,
            "weight_lbs": 185.0,
            "reps": 4,
            "notes": None,
        },
    ]


def test_exercise_sets_require_existing_session(client):
    response = client.post(
        "/api/v1/exercise/sessions/999/sets",
        json={
            "exercise_name": "Bench press",
            "set_number": 1,
            "weight_lbs": 185,
            "reps": 5,
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Exercise session not found"}
