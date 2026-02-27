from datetime import date

import httpx

from scripts.sync_oura import (
    SyncConfig,
    build_ingest_payload,
    default_dates,
    fetch_oura_collection,
    normalize_readiness_entry,
    post_driver_ingest,
    run_sync,
)


def test_default_dates_returns_expected_window(monkeypatch):
    class MockDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 3, 12)

    monkeypatch.setattr("scripts.sync_oura.date", MockDate)
    start, end = default_dates(days_back=3)
    assert start == "2026-03-09"
    assert end == "2026-03-11"


def test_fetch_oura_collection_handles_pagination():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            assert request.url.path.endswith("/v2/usercollection/daily_activity")
            assert request.url.params["start_date"] == "2026-03-01"
            assert request.url.params["end_date"] == "2026-03-02"
            return httpx.Response(
                status_code=200,
                json={
                    "data": [{"day": "2026-03-01", "steps": 9000}],
                    "next_token": "token-2",
                },
            )
        assert request.url.params["next_token"] == "token-2"
        return httpx.Response(
            status_code=200,
            json={"data": [{"day": "2026-03-02", "steps": 10000}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        rows = fetch_oura_collection(
            client,
            api_base="https://api.ouraring.com",
            token="token",
            endpoint="daily_activity",
            start_date="2026-03-01",
            end_date="2026-03-02",
        )
    finally:
        client.close()

    assert rows == [
        {"day": "2026-03-01", "steps": 9000},
        {"day": "2026-03-02", "steps": 10000},
    ]


def test_normalize_readiness_entry_supports_nested_contributors():
    normalized = normalize_readiness_entry(
        {
            "day": "2026-03-04",
            "score": 79,
            "contributors": {
                "hrv_balance": {"value": 41.3},
                "resting_heart_rate": {"value": 54},
            },
        }
    )
    assert normalized == {
        "day": "2026-03-04",
        "score": 79,
        "average_hrv": 41.3,
        "resting_heart_rate": 54,
    }


def test_build_ingest_payload_normalizes_readiness():
    payload = build_ingest_payload(
        sleep=[{"day": "2026-03-05"}],
        readiness=[{"day": "2026-03-05", "score": 70, "average_hrv": 35.0}],
        activity=[{"day": "2026-03-05", "steps": 8000}],
    )
    assert payload["sleep"] == [{"day": "2026-03-05"}]
    assert payload["readiness"] == [
        {
            "day": "2026-03-05",
            "score": 70,
            "average_hrv": 35.0,
            "resting_heart_rate": None,
        }
    ]
    assert payload["activity"] == [{"day": "2026-03-05", "steps": 8000}]


def test_post_driver_ingest_sends_bearer_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/ingest/oura"
        assert request.headers["Authorization"] == "Bearer driver-token"
        return httpx.Response(status_code=200, json={"status": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = post_driver_ingest(
            client,
            api_base="http://localhost:8100",
            token="driver-token",
            payload={"sleep": [], "readiness": [], "activity": []},
        )
    finally:
        client.close()
    assert result == {"status": "ok"}


def test_run_sync_posts_compound_payload():
    responses = {
        "/v2/usercollection/sleep": {"data": [{"day": "2026-03-06", "score": 81}]},
        "/v2/usercollection/daily_readiness": {
            "data": [{"day": "2026-03-06", "score": 78}]
        },
        "/v2/usercollection/daily_activity": {
            "data": [{"day": "2026-03-06", "steps": 11111}]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(status_code=200, json=responses[request.url.path])
        assert request.url.path == "/api/v1/ingest/oura"
        payload = request.content.decode("utf-8")
        assert '"sleep"' in payload
        assert '"readiness"' in payload
        assert '"activity"' in payload
        return httpx.Response(
            status_code=200,
            json={
                "status": "ok",
                "processed": {"sleep": 1, "readiness": 1, "activity": 1, "skipped": 0},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = run_sync(
            SyncConfig(
                oura_api_base="https://api.ouraring.com",
                oura_api_token="oura-token",
                driver_api_base="http://localhost:8100",
                driver_api_token=None,
                start_date="2026-03-06",
                end_date="2026-03-06",
            ),
            client=client,
        )
    finally:
        client.close()

    assert result["status"] == "ok"
