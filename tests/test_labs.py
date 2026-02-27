def test_labs_create_and_query_by_marker_and_date(client):
    first = client.post(
        "/api/v1/labs/",
        json={
            "drawn_date": "2026-02-14",
            "panel": "Lipid Panel",
            "marker": "Triglycerides",
            "value": 182,
            "unit": "mg/dL",
            "reference_high": 149,
            "flag": "H",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/labs/",
        json={
            "drawn_date": "2026-02-14",
            "panel": "Lipid Panel",
            "marker": "LDL",
            "value": 131,
            "unit": "mg/dL",
            "reference_high": 99,
            "flag": "H",
        },
    )
    assert second.status_code == 201

    marker_response = client.get("/api/v1/labs/", params={"marker": "Triglycerides"})
    assert marker_response.status_code == 200
    marker_payload = marker_response.json()
    assert len(marker_payload) == 1
    assert marker_payload[0]["value"] == 182.0

    date_response = client.get("/api/v1/labs/", params={"drawn_date": "2026-02-14"})
    assert date_response.status_code == 200
    assert len(date_response.json()) == 2

    list_response = client.get("/api/v1/labs/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2
