def test_doctor_visit_report_includes_core_sections(client):
    for recorded_date, calories, protein, sodium in [
        ("2026-02-25", 500, 40, 700),
        ("2026-02-26", 600, 45, 750),
        ("2026-02-27", 550, 42, 720),
    ]:
        response = client.post(
            "/api/v1/food/",
            json={
                "recorded_date": recorded_date,
                "meal_type": "dinner",
                "name": "Meal",
                "calories": calories,
                "protein_g": protein,
                "sodium_mg": sodium,
                "alcohol_calories": 120 if recorded_date == "2026-02-26" else 0,
            },
        )
        assert response.status_code == 201

    sleep = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-02-27",
            "duration_min": 420,
            "sleep_score": 73,
            "readiness_score": 70,
            "source": "oura",
        },
    )
    assert sleep.status_code == 201

    exercise = client.post(
        "/api/v1/exercise/sessions",
        json={
            "recorded_date": "2026-02-27",
            "session_type": "cardio",
            "name": "Bike",
            "duration_min": 35,
            "calories_burned": 310,
            "source": "manual",
        },
    )
    assert exercise.status_code == 201

    weight_1 = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-25",
            "metric": "weight_lbs",
            "value": 202.5,
            "source": "manual",
        },
    )
    assert weight_1.status_code == 201
    weight_2 = client.post(
        "/api/v1/metrics",
        json={
            "recorded_date": "2026-02-27",
            "metric": "weight_lbs",
            "value": 201.2,
            "source": "manual",
        },
    )
    assert weight_2.status_code == 201

    supplement = client.post(
        "/api/v1/supplements/",
        json={"name": "Creatine", "dose": "5g", "frequency": "daily", "active": 1},
    )
    assert supplement.status_code == 201
    medication = client.post(
        "/api/v1/medications/",
        json={
            "name": "Rosuvastatin",
            "dose": "10mg",
            "indication": "lipids",
            "active": 1,
        },
    )
    assert medication.status_code == 201

    labs = client.post(
        "/api/v1/labs/",
        json={
            "drawn_date": "2026-02-14",
            "panel": "Lipid Panel",
            "marker": "Triglycerides",
            "value": 182,
            "unit": "mg/dL",
            "flag": "H",
        },
    )
    assert labs.status_code == 201

    history = client.post(
        "/api/v1/medical-history/",
        json={
            "category": "condition",
            "title": "Hypertriglyceridemia",
            "detail": "Monitoring quarterly labs",
            "active": 1,
        },
    )
    assert history.status_code == 201

    report = client.get(
        "/api/v1/reports/doctor-visit",
        params={"ending": "2026-02-27", "days": 7},
    )
    assert report.status_code == 200
    payload = report.json()
    assert payload["exercise"]["session_count"] == 1
    assert payload["body_metrics"]["latest_weight"] == 201.2
    assert payload["active_supplements"][0]["name"] == "Creatine"
    assert "Doctor Visit Report" in payload["report_markdown"]
    assert "Latest Labs" in payload["report_markdown"]
