def test_medical_history_crud_and_archive(client):
    create = client.post(
        "/api/v1/medical-history/",
        json={
            "category": "condition",
            "title": "Hypertriglyceridemia",
            "detail": "Monitoring with quarterly labs",
            "date": "2026-02-14",
            "active": 1,
        },
    )
    assert create.status_code == 201
    entry_id = create.json()["id"]

    list_response = client.get("/api/v1/medical-history/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    patch = client.patch(
        f"/api/v1/medical-history/{entry_id}",
        json={"notes": "Improving with reduced alcohol"},
    )
    assert patch.status_code == 200
    assert patch.json()["notes"] == "Improving with reduced alcohol"

    delete = client.delete(f"/api/v1/medical-history/{entry_id}")
    assert delete.status_code == 204

    active_only = client.get("/api/v1/medical-history/", params={"active_only": 1})
    assert active_only.status_code == 200
    assert active_only.json() == []
