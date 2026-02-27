def test_medications_create_list_and_patch(client):
    create = client.post(
        "/api/v1/medications/",
        json={
            "name": "Rosuvastatin",
            "dose": "10mg",
            "prescriber": "Dr. Tyson",
            "indication": "lipids",
            "active": 1,
        },
    )
    assert create.status_code == 201
    medication_id = create.json()["id"]

    active_response = client.get("/api/v1/medications/")
    assert active_response.status_code == 200
    assert len(active_response.json()) == 1

    patch = client.patch(
        f"/api/v1/medications/{medication_id}",
        json={"dose": "20mg", "active": 0, "stopped_date": "2026-03-05"},
    )
    assert patch.status_code == 200
    assert patch.json()["dose"] == "20mg"
    assert patch.json()["active"] == 0
    assert patch.json()["stopped_date"] == "2026-03-05"

    all_response = client.get("/api/v1/medications/", params={"active_only": 0})
    assert all_response.status_code == 200
    assert len(all_response.json()) == 1
