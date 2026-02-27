def test_supplements_create_list_and_patch_active_status(client):
    create = client.post(
        "/api/v1/supplements/",
        json={
            "name": "Creatine",
            "dose": "5g",
            "frequency": "daily",
            "active": 1,
            "started_date": "2026-01-01",
        },
    )
    assert create.status_code == 201
    supplement_id = create.json()["id"]

    active_response = client.get("/api/v1/supplements/")
    assert active_response.status_code == 200
    assert len(active_response.json()) == 1

    patch = client.patch(
        f"/api/v1/supplements/{supplement_id}",
        json={"active": 0, "stopped_date": "2026-03-01"},
    )
    assert patch.status_code == 200
    assert patch.json()["active"] == 0
    assert patch.json()["stopped_date"] == "2026-03-01"

    active_after_patch = client.get("/api/v1/supplements/")
    assert active_after_patch.status_code == 200
    assert active_after_patch.json() == []

    all_response = client.get("/api/v1/supplements/", params={"active_only": 0})
    assert all_response.status_code == 200
    assert len(all_response.json()) == 1
