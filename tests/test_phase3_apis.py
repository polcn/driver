def test_phase3_labs_supplements_medications_and_medical_history(client):
    lab = client.post(
        "/api/v1/labs/",
        json={
            "drawn_date": "2026-02-14",
            "panel": "Lipid Panel",
            "marker": "Triglycerides",
            "value": 244,
            "unit": "mg/dL",
            "reference_high": 149,
            "flag": "H",
        },
    )
    assert lab.status_code == 201
    assert (
        client.get("/api/v1/labs/", params={"marker": "Triglycerides"}).status_code
        == 200
    )

    supplement = client.post(
        "/api/v1/supplements/",
        json={"name": "Creatine", "dose": "5g", "frequency": "daily"},
    )
    assert supplement.status_code == 201
    supplement_id = supplement.json()["id"]
    assert (
        client.patch(
            f"/api/v1/supplements/{supplement_id}", json={"active": 0}
        ).status_code
        == 200
    )

    medication = client.post(
        "/api/v1/medications/",
        json={"name": "Rosuvastatin", "dose": "10mg", "indication": "lipids"},
    )
    assert medication.status_code == 201
    medication_id = medication.json()["id"]
    assert (
        client.patch(
            f"/api/v1/medications/{medication_id}", json={"active": 0}
        ).status_code
        == 200
    )

    history = client.post(
        "/api/v1/medical-history/",
        json={"category": "condition", "title": "Hypertriglyceridemia"},
    )
    assert history.status_code == 201
    history_id = history.json()["id"]
    assert (
        client.patch(
            f"/api/v1/medical-history/{history_id}", json={"notes": "tracked"}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/medical-history/{history_id}").status_code == 204
