def test_body_metrics_create_and_query_by_range(client):
    first_response = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-24",
            "metric": "weight_lbs",
            "value": 201.4,
            "source": "manual",
            "notes": "morning weigh-in",
        },
    )
    assert first_response.status_code == 201
    assert first_response.json()["metric"] == "weight_lbs"

    second_response = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-27",
            "metric": "weight_lbs",
            "value": 199.8,
            "source": "manual",
        },
    )
    assert second_response.status_code == 201

    third_response = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-27",
            "metric": "waist_in",
            "value": 39.5,
            "source": "manual",
        },
    )
    assert third_response.status_code == 201

    response = client.get(
        "/api/v1/metrics",
        params={"metric": "weight_lbs", "days": 7, "ending": "2026-02-27"},
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "recorded_date": "2026-02-24",
            "metric": "weight_lbs",
            "value": 201.4,
            "source": "manual",
            "notes": "morning weigh-in",
            "created_at": response.json()[0]["created_at"],
        },
        {
            "recorded_date": "2026-02-27",
            "metric": "weight_lbs",
            "value": 199.8,
            "source": "manual",
            "notes": None,
            "created_at": response.json()[1]["created_at"],
        },
    ]
