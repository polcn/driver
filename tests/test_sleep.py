def test_sleep_record_create_and_get_by_date(client):
    create_response = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "bedtime": "2026-02-26T22:45:00",
            "wake_time": "2026-02-27T06:30:00",
            "duration_min": 465,
            "deep_min": 78,
            "rem_min": 92,
            "core_min": 250,
            "awake_min": 45,
            "hrv": 41.7,
            "resting_hr": 54,
            "readiness_score": 81,
            "sleep_score": 79,
            "source": "manual",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["recorded_date"] == "2026-02-27"

    response = client.get("/api/v1/sleep", params={"recorded_date": "2026-02-27"})
    assert response.status_code == 200
    assert response.json() == {
        "id": create_response.json()["id"],
        "recorded_date": "2026-02-27",
        "bedtime": "2026-02-26T22:45:00",
        "wake_time": "2026-02-27T06:30:00",
        "duration_min": 465,
        "deep_min": 78,
        "rem_min": 92,
        "core_min": 250,
        "awake_min": 45,
        "hrv": 41.7,
        "resting_hr": 54,
        "readiness_score": 81,
        "sleep_score": 79,
        "cpap_used": None,
        "cpap_ahi": None,
        "cpap_hours": None,
        "cpap_leak_95": None,
        "cpap_pressure_avg": None,
        "source": "manual",
        "created_at": response.json()["created_at"],
    }


def test_sleep_record_list_by_window_returns_recent_first(client):
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-25",
            "duration_min": 430,
            "sleep_score": 72,
            "source": "manual",
        },
    )
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "duration_min": 470,
            "sleep_score": 80,
            "source": "manual",
        },
    )

    response = client.get(
        "/api/v1/sleep",
        params={"days": 7, "ending": "2026-02-27"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["recorded_date"] == "2026-02-27"
    assert payload[1]["recorded_date"] == "2026-02-25"
