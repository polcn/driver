from datetime import datetime
from pathlib import Path


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

    monkeypatch.setattr(
        "app.parsers.cpap_edf.parse_cpap_edf",
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
    # Point CPAP_DATA_DIR to a temp dir with a dummy file
    tmp = Path("/tmp/test-cpap")
    tmp.mkdir(exist_ok=True)
    (tmp / "STR.edf").touch()
    monkeypatch.setattr("app.routers.ingest.CPAP_DATA_DIR", tmp)

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
    monkeypatch.setattr(
        "app.parsers.cpap_edf.parse_cpap_edf",
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
    tmp = Path("/tmp/test-cpap")
    tmp.mkdir(exist_ok=True)
    (tmp / "STR.edf").touch()
    monkeypatch.setattr("app.routers.ingest.CPAP_DATA_DIR", tmp)

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


def test_ingest_cpap_returns_error_when_file_missing(client, monkeypatch):
    tmp = Path("/tmp/test-cpap-empty")
    tmp.mkdir(exist_ok=True)
    # Ensure no STR.edf exists
    edf = tmp / "STR.edf"
    if edf.exists():
        edf.unlink()
    monkeypatch.setattr("app.routers.ingest.CPAP_DATA_DIR", tmp)

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "STR.edf not found" in response.json()["detail"]


def test_ingest_cpap_returns_error_when_parser_fails(client, monkeypatch):
    def parse_fail(_):
        raise ValueError("corrupt edf")

    monkeypatch.setattr("app.parsers.cpap_edf.parse_cpap_edf", parse_fail)
    tmp = Path("/tmp/test-cpap")
    tmp.mkdir(exist_ok=True)
    (tmp / "STR.edf").touch()
    monkeypatch.setattr("app.routers.ingest.CPAP_DATA_DIR", tmp)

    response = client.post("/api/v1/ingest/cpap")
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "Failed to parse EDF" in response.json()["detail"]


def test_cpap_parser_reads_resmed_str_edf_format(monkeypatch):
    """Test parser with realistic ResMed STR.edf signal names and physical values."""
    from datetime import date

    day0 = (date(2026, 3, 1) - date(1970, 1, 1)).days
    day1 = day0 + 1

    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.signals_in_file = 5

        def getLabel(self, idx):
            return ["Date", "AHI", "Duration", "Leak.95", "MaskPress.50"][idx]

        def readSignal(self, idx):
            rows = [
                [day0, day1],
                [2.5, 1.8],
                [420, 480],
                [0.32, 0.18],
                [9.4, 10.2],
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
            "cpap_ahi": 2.5,
            "cpap_hours": 7.0,
            "cpap_leak_95": 0.32,
            "cpap_pressure_avg": 9.4,
        },
        {
            "recorded_date": "2026-03-02",
            "cpap_used": 1,
            "cpap_ahi": 1.8,
            "cpap_hours": 8.0,
            "cpap_leak_95": 0.18,
            "cpap_pressure_avg": 10.2,
        },
    ]
