def build_payload(
    metrics=None,
    workouts=None,
):
    return {
        "data": {
            "metrics": metrics or [],
            "workouts": workouts or [],
        }
    }


def test_ingest_metrics_maps_and_upserts_body_metrics(client, db_module_fixture):
    payload = build_payload(
        metrics=[
            {
                "name": "resting_heart_rate",
                "units": "count/min",
                "data": [{"date": "2026-02-27 08:00:00", "qty": 58}],
            },
            {
                "name": "weight_body_mass",
                "units": "lb",
                "data": [{"date": "2026-02-27 07:00:00", "qty": 198.4}],
            },
            {
                "name": "active_energy",
                "units": "kcal",
                "data": [{"date": "2026-02-27", "qty": 450}],
            },
            {
                "name": "step_count",
                "units": "count",
                "data": [{"date": "2026-02-27", "qty": 8234}],
            },
            {
                "name": "heart_rate",
                "units": "count/min",
                "data": [{"date": "2026-02-27 08:00:00", "qty": 101}],
            },
        ]
    )

    first = client.post("/api/v1/ingest/apple-health", json=payload)
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert first.json()["processed"]["metrics"] == 4

    second_payload = build_payload(
        metrics=[
            {
                "name": "resting_heart_rate",
                "units": "count/min",
                "data": [{"date": "2026-02-27 08:00:00", "qty": 57}],
            }
        ]
    )
    second = client.post("/api/v1/ingest/apple-health", json=second_payload)
    assert second.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        rows = conn.execute(
            """SELECT metric, value
               FROM body_metrics
               WHERE recorded_date='2026-02-27' AND source='apple_health'
               ORDER BY metric"""
        ).fetchall()
        assert [dict(row) for row in rows] == [
            {"metric": "active_calories", "value": 450.0},
            {"metric": "resting_hr", "value": 57.0},
            {"metric": "steps", "value": 8234.0},
            {"metric": "weight_lbs", "value": 198.4},
        ]
    finally:
        conn.close()


def test_ingest_workout_creates_session_and_hr_zones(client, db_module_fixture):
    payload = build_payload(
        workouts=[
            {
                "name": "Traditional Strength Training",
                "start": "2026-02-27 09:00:00",
                "end": "2026-02-27 10:00:00",
                "duration": 3600,
                "activeEnergy": {"qty": 320, "units": "kcal"},
                "heartRateData": [
                    {"date": "2026-02-27 09:00:00", "qty": 95},
                    {"date": "2026-02-27 09:15:00", "qty": 128},
                    {"date": "2026-02-27 09:30:00", "qty": 142},
                    {"date": "2026-02-27 09:45:00", "qty": 115},
                ],
            }
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200
    assert response.json()["processed"]["workouts"] == 1

    conn = db_module_fixture.get_db()
    try:
        session = conn.execute(
            """SELECT id, session_type, duration_min, calories_burned, avg_heart_rate, max_heart_rate, source
               FROM exercise_sessions
               WHERE source='apple_health'"""
        ).fetchone()
        assert dict(session) == {
            "id": session["id"],
            "session_type": "strength",
            "duration_min": 60,
            "calories_burned": 320.0,
            "avg_heart_rate": 120,
            "max_heart_rate": 142,
            "source": "apple_health",
        }

        zones = conn.execute(
            """SELECT zone, minutes, pct_of_session
               FROM exercise_hr_zones
               WHERE session_id=?
               ORDER BY zone""",
            (session["id"],),
        ).fetchall()
        assert len(zones) > 0
        pct_sum = sum(row["pct_of_session"] for row in zones)
        assert 99.5 <= pct_sum <= 100.5
    finally:
        conn.close()


def test_ingest_is_idempotent_for_workouts(client, db_module_fixture):
    payload = build_payload(
        workouts=[
            {
                "name": "Stair Session",
                "start": "2026-02-28 09:00:00",
                "duration": 1800,
                "activeEnergy": {"qty": 220, "units": "kcal"},
                "heartRateData": [
                    {"date": "2026-02-28 09:00:00", "qty": 110},
                    {"date": "2026-02-28 09:15:00", "qty": 112},
                ],
            }
        ]
    )

    first = client.post("/api/v1/ingest/apple-health", json=payload)
    assert first.status_code == 200
    second = client.post("/api/v1/ingest/apple-health", json=payload)
    assert second.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        session_count = conn.execute(
            "SELECT COUNT(*) AS count FROM exercise_sessions WHERE source='apple_health'"
        ).fetchone()["count"]
        zone_count = conn.execute(
            "SELECT COUNT(*) AS count FROM exercise_hr_zones"
        ).fetchone()["count"]
        assert session_count == 1
        assert zone_count == 1
    finally:
        conn.close()


def test_ingest_sleep_analysis_inserts_apple_health_record(client, db_module_fixture):
    payload = build_payload(
        metrics=[
            {
                "name": "sleep_analysis",
                "units": "hr",
                "data": [{"date": "2026-03-01", "qty": 6.5}],
            }
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT recorded_date, duration_min, source
               FROM sleep_records
               WHERE recorded_date='2026-03-01'"""
        ).fetchone()
        assert dict(row) == {
            "recorded_date": "2026-03-01",
            "duration_min": 390,
            "source": "apple_health",
        }
    finally:
        conn.close()


def test_ingest_sleep_analysis_does_not_overwrite_oura(client, db_module_fixture):
    client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-02",
            "duration_min": 440,
            "source": "oura",
        },
    )
    payload = build_payload(
        metrics=[
            {
                "name": "sleep_analysis",
                "units": "hr",
                "data": [{"date": "2026-03-02", "qty": 6.0}],
            }
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT duration_min, source
               FROM sleep_records
               WHERE recorded_date='2026-03-02'"""
        ).fetchone()
        assert dict(row) == {"duration_min": 440, "source": "oura"}
    finally:
        conn.close()


def test_ingest_workout_without_heart_rate_data_does_not_create_zones(
    client, db_module_fixture
):
    payload = build_payload(
        workouts=[
            {
                "name": "Easy Walk",
                "start": "2026-03-03 07:15:00",
                "duration": 2400,
                "activeEnergy": {"qty": 150, "units": "kcal"},
            }
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        session = conn.execute(
            "SELECT id FROM exercise_sessions WHERE source='apple_health'"
        ).fetchone()
        zone_count = conn.execute(
            "SELECT COUNT(*) AS count FROM exercise_hr_zones WHERE session_id=?",
            (session["id"],),
        ).fetchone()["count"]
        assert zone_count == 0
    finally:
        conn.close()


def test_ingest_hr_zone_all_zone_two_maps_to_100_percent(client, db_module_fixture):
    payload = build_payload(
        workouts=[
            {
                "name": "Bike Ride",
                "start": "2026-03-04 18:00:00",
                "duration": 1800,
                "heartRateData": [
                    {"date": "2026-03-04 18:00:00", "qty": 102},
                    {"date": "2026-03-04 18:10:00", "qty": 110},
                    {"date": "2026-03-04 18:20:00", "qty": 108},
                    {"date": "2026-03-04 18:30:00", "qty": 104},
                ],
            }
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        zone_rows = conn.execute(
            """SELECT zone, minutes, pct_of_session
               FROM exercise_hr_zones
               ORDER BY zone"""
        ).fetchall()
        assert [dict(row) for row in zone_rows] == [
            {
                "zone": 2,
                "minutes": 30.0,
                "pct_of_session": 100.0,
            }
        ]
    finally:
        conn.close()


def test_ingest_allows_two_same_day_same_name_workouts_with_different_start_times(
    client, db_module_fixture
):
    payload = build_payload(
        workouts=[
            {
                "name": "Traditional Strength Training",
                "start": "2026-03-05 09:00:00",
                "duration": 1800,
            },
            {
                "name": "Traditional Strength Training",
                "start": "2026-03-05 17:00:00",
                "duration": 1800,
            },
        ]
    )

    response = client.post("/api/v1/ingest/apple-health", json=payload)
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        rows = conn.execute(
            """SELECT recorded_date, name, external_id
               FROM exercise_sessions
               WHERE source='apple_health'
               ORDER BY external_id"""
        ).fetchall()
        assert [dict(row) for row in rows] == [
            {
                "recorded_date": "2026-03-05",
                "name": "Traditional Strength Training",
                "external_id": "apple_health:2026-03-05 09:00:00",
            },
            {
                "recorded_date": "2026-03-05",
                "name": "Traditional Strength Training",
                "external_id": "apple_health:2026-03-05 17:00:00",
            },
        ]
    finally:
        conn.close()


def test_oura_ingest_creates_sleep_from_sleep_and_readiness_payload(
    client, db_module_fixture
):
    payload = {
        "sleep": [
            {
                "day": "2026-03-06",
                "bedtime_start": "2026-03-05T22:40:00",
                "bedtime_end": "2026-03-06T06:40:00",
                "total_sleep_duration": 28800,
                "deep_sleep_duration": 5400,
                "rem_sleep_duration": 6600,
                "light_sleep_duration": 15000,
                "awake_time": 1800,
                "score": 82,
            }
        ],
        "readiness": [
            {
                "day": "2026-03-06",
                "score": 77,
                "average_hrv": 39.2,
                "resting_heart_rate": 52,
            }
        ],
    }
    response = client.post("/api/v1/ingest/oura", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["processed"]["sleep"] == 1
    assert response.json()["processed"]["readiness"] == 1

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT recorded_date, duration_min, deep_min, rem_min, core_min, awake_min,
                      readiness_score, sleep_score, hrv, resting_hr, source
               FROM sleep_records
               WHERE recorded_date='2026-03-06'"""
        ).fetchone()
        assert dict(row) == {
            "recorded_date": "2026-03-06",
            "duration_min": 480,
            "deep_min": 90,
            "rem_min": 110,
            "core_min": 250,
            "awake_min": 30,
            "readiness_score": 77,
            "sleep_score": 82,
            "hrv": 39.2,
            "resting_hr": 52,
            "source": "oura",
        }
    finally:
        conn.close()


def test_oura_ingest_resync_updates_existing_oura_row(client, db_module_fixture):
    initial_payload = {
        "sleep": [{"day": "2026-03-07", "total_sleep_duration": 25200, "score": 70}],
        "readiness": [{"day": "2026-03-07", "score": 65, "average_hrv": 31.5}],
    }
    updated_payload = {
        "sleep": [{"day": "2026-03-07", "total_sleep_duration": 27000, "score": 74}],
        "readiness": [{"day": "2026-03-07", "score": 71, "average_hrv": 36.4}],
    }

    assert client.post("/api/v1/ingest/oura", json=initial_payload).status_code == 200
    assert client.post("/api/v1/ingest/oura", json=updated_payload).status_code == 200

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT duration_min, sleep_score, readiness_score, hrv, source
               FROM sleep_records
               WHERE recorded_date='2026-03-07'"""
        ).fetchone()
        assert dict(row) == {
            "duration_min": 450,
            "sleep_score": 74,
            "readiness_score": 71,
            "hrv": 36.4,
            "source": "oura",
        }
    finally:
        conn.close()


def test_oura_ingest_overwrites_existing_apple_health_sleep_record(
    client, db_module_fixture
):
    client.post(
        "/api/v1/ingest/apple-health",
        json={
            "data": {
                "metrics": [
                    {
                        "name": "sleep_analysis",
                        "units": "hr",
                        "data": [{"date": "2026-03-08", "qty": 6.2}],
                    }
                ],
                "workouts": [],
            }
        },
    )

    response = client.post(
        "/api/v1/ingest/oura",
        json={
            "sleep": [
                {"day": "2026-03-08", "total_sleep_duration": 27600, "score": 79}
            ],
            "readiness": [{"day": "2026-03-08", "score": 75}],
        },
    )
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT duration_min, sleep_score, readiness_score, source
               FROM sleep_records
               WHERE recorded_date='2026-03-08'"""
        ).fetchone()
        assert dict(row) == {
            "duration_min": 460,
            "sleep_score": 79,
            "readiness_score": 75,
            "source": "oura",
        }
    finally:
        conn.close()


def test_oura_ingest_skips_manual_sleep_record(client, db_module_fixture):
    client.post(
        "/api/v1/sleep",
        json={"recorded_date": "2026-03-09", "duration_min": 430, "source": "manual"},
    )

    response = client.post(
        "/api/v1/ingest/oura",
        json={"sleep": [{"day": "2026-03-09", "total_sleep_duration": 30000}]},
    )
    assert response.status_code == 200
    assert response.json()["processed"]["skipped"] >= 1

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            "SELECT duration_min, source FROM sleep_records WHERE recorded_date='2026-03-09'"
        ).fetchone()
        assert dict(row) == {"duration_min": 430, "source": "manual"}
    finally:
        conn.close()


def test_oura_ingest_upserts_activity_metrics(client, db_module_fixture):
    payload = {
        "activity": [
            {"day": "2026-03-10", "active_calories": 510, "steps": 10234},
            {"day": "2026-03-10", "active_calories": 530, "steps": 10400},
        ]
    }
    response = client.post("/api/v1/ingest/oura", json=payload)
    assert response.status_code == 200
    assert response.json()["processed"]["activity"] == 4

    conn = db_module_fixture.get_db()
    try:
        rows = conn.execute(
            """SELECT metric, value
               FROM body_metrics
               WHERE recorded_date='2026-03-10' AND source='oura'
               ORDER BY metric"""
        ).fetchall()
        assert [dict(row) for row in rows] == [
            {"metric": "active_calories", "value": 530.0},
            {"metric": "steps", "value": 10400.0},
        ]
    finally:
        conn.close()
