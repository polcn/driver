from datetime import datetime


def test_ingest_cpap_merges_onto_existing_oura_row_without_overwrite(
    client, db_module_fixture, monkeypatch
):
    create_sleep = client.post(
        "/api/v1/sleep",
        json={
            "recorded_date": "2026-03-01",
            "duration_min": 430,
            "sleep_score": 77,
            "source": "oura",
        },
    )
    assert create_sleep.status_code == 201

    monkeypatch.setattr("app.routers.ingest._drive_service", lambda: object())
    monkeypatch.setattr(
        "app.routers.ingest._download_str_edf_to_temp",
        lambda service: __import__("pathlib").Path("/tmp/fake-cpap.edf"),
    )
    monkeypatch.setattr(
        "app.routers.ingest.parse_cpap_edf",
        lambda _: [
            {
                "recorded_date": "2026-03-01",
                "cpap_used": 1,
                "cpap_ahi": 2.1,
                "cpap_hours": 6.8,
                "cpap_leak_95": 0.22,
                "cpap_pressure_avg": 9.4,
            }
        ],
    )

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["nights_imported"] == 1

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT source, duration_min, sleep_score, cpap_used, cpap_ahi, cpap_hours, cpap_leak_95, cpap_pressure_avg
               FROM sleep_records
               WHERE recorded_date='2026-03-01'"""
        ).fetchone()
        assert dict(row) == {
            "source": "oura",
            "duration_min": 430,
            "sleep_score": 77,
            "cpap_used": 1,
            "cpap_ahi": 2.1,
            "cpap_hours": 6.8,
            "cpap_leak_95": 0.22,
            "cpap_pressure_avg": 9.4,
        }
    finally:
        conn.close()


def test_ingest_cpap_creates_new_cpap_row_when_no_sleep_row_exists(
    client, db_module_fixture, monkeypatch
):
    monkeypatch.setattr("app.routers.ingest._drive_service", lambda: object())
    monkeypatch.setattr(
        "app.routers.ingest._download_str_edf_to_temp",
        lambda service: __import__("pathlib").Path("/tmp/fake-cpap.edf"),
    )
    monkeypatch.setattr(
        "app.routers.ingest.parse_cpap_edf",
        lambda _: [
            {
                "recorded_date": "2026-03-02",
                "cpap_used": 1,
                "cpap_ahi": 1.4,
                "cpap_hours": 7.3,
                "cpap_leak_95": 0.18,
                "cpap_pressure_avg": 8.9,
            }
        ],
    )

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200

    conn = db_module_fixture.get_db()
    try:
        row = conn.execute(
            """SELECT source, cpap_used, cpap_ahi, cpap_hours
               FROM sleep_records
               WHERE recorded_date='2026-03-02'"""
        ).fetchone()
        assert dict(row) == {
            "source": "cpap",
            "cpap_used": 1,
            "cpap_ahi": 1.4,
            "cpap_hours": 7.3,
        }
    finally:
        conn.close()


def test_ingest_cpap_returns_error_when_drive_file_missing(client, monkeypatch):
    monkeypatch.setattr("app.routers.ingest._drive_service", lambda: object())

    def raise_not_found(service):
        raise FileNotFoundError("STR.edf not found in mcgrupp/resmed/")

    monkeypatch.setattr("app.routers.ingest._download_str_edf_to_temp", raise_not_found)

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "detail": "STR.edf not found in mcgrupp/resmed/",
    }


def test_ingest_cpap_returns_error_when_parser_fails(client, monkeypatch):
    monkeypatch.setattr("app.routers.ingest._drive_service", lambda: object())
    monkeypatch.setattr(
        "app.routers.ingest._download_str_edf_to_temp",
        lambda service: __import__("pathlib").Path("/tmp/fake-cpap.edf"),
    )

    def parse_fail(_):
        raise ValueError("corrupt edf")

    monkeypatch.setattr("app.routers.ingest.parse_cpap_edf", parse_fail)

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "Failed to parse EDF" in response.json()["detail"]


def test_cpap_parser_scales_values_and_builds_dates(monkeypatch):
    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.signals_in_file = 4

        def getLabel(self, idx):
            return ["AHI", "Usage Hours", "Leak 95", "Pressure Avg"][idx]

        def readSignal(self, idx):
            rows = [
                [15, 10],  # ahi raw
                [7.5, 8.0],  # hours
                [11, 12],  # leak raw
                [500, 525],  # pressure raw
            ]
            return rows[idx]

        def getStartdatetime(self):
            return datetime(2026, 3, 1, 22, 0, 0)

        def close(self):
            return None

    monkeypatch.setattr("app.parsers.cpap_edf.pyedflib.EdfReader", FakeReader)
    from app.parsers.cpap_edf import parse_cpap_edf

    nights = parse_cpap_edf("/tmp/fake.edf")
    assert nights == [
        {
            "recorded_date": "2026-03-01",
            "cpap_used": 1,
            "cpap_ahi": 1.5,
            "cpap_hours": 7.5,
            "cpap_leak_95": 0.22,
            "cpap_pressure_avg": 10.0,
        },
        {
            "recorded_date": "2026-03-02",
            "cpap_used": 1,
            "cpap_ahi": 1.0,
            "cpap_hours": 8.0,
            "cpap_leak_95": 0.24,
            "cpap_pressure_avg": 10.5,
        },
    ]
