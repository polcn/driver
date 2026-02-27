def test_generate_training_suggestion_creates_row_from_oura_sleep(client):
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-02",
            "hrv": 42.0,
            "readiness_score": 78,
            "source": "oura",
        },
    )
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-01",
            "hrv": 39.0,
            "readiness_score": 72,
            "source": "oura",
        },
    )

    response = client.post(
        "/api/v1/training/suggestions/generate",
        params={"target_date": "2026-03-02"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion_date"] == "2026-03-02"
    assert payload["scheduled_type"] == "strength"
    assert payload["intensity"] in {"moderate", "full"}
    assert payload["readiness_score"] == 78
    assert payload["hrv"] == 42.0
    assert payload["hrv_7day_avg"] == 40.5


def test_generate_training_suggestion_low_readiness_returns_easy_intensity(client):
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-03",
            "hrv": 30.0,
            "readiness_score": 55,
            "source": "oura",
        },
    )
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-02",
            "hrv": 40.0,
            "readiness_score": 72,
            "source": "oura",
        },
    )
    client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-03-03",
            "session_type": "cardio",
            "name": "Morning bike",
            "duration_min": 20,
            "source": "manual",
        },
    )

    response = client.post(
        "/api/v1/training/suggestions/generate",
        params={"target_date": "2026-03-03"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scheduled_type"] == "cardio"
    assert payload["intensity"] == "easy"
    assert "easy" in payload["suggestion"].lower()
