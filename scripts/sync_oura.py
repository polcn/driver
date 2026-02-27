#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

OURA_API_BASE = os.getenv("OURA_API_BASE", "https://api.ouraring.com")
DRIVER_API_BASE = os.getenv("DRIVER_API_BASE", "http://localhost:8100")


@dataclass
class SyncConfig:
    oura_api_base: str
    oura_api_token: str
    driver_api_base: str
    driver_api_token: str | None
    start_date: str
    end_date: str
    timeout_seconds: float = 30.0
    dry_run: bool = False


def default_dates(days_back: int) -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(days_back - 1, 0))
    return start.isoformat(), end.isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Oura data into Driver ingest API."
    )
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD).")
    parser.add_argument(
        "--days-back",
        type=int,
        default=2,
        help="Fallback window when start/end are omitted. Defaults to 2 days.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print payload without posting."
    )
    return parser.parse_args()


def resolve_config(args: argparse.Namespace) -> SyncConfig:
    oura_api_token = os.getenv("OURA_API_TOKEN", "").strip()
    if not oura_api_token:
        raise ValueError("OURA_API_TOKEN is required.")

    driver_api_token = os.getenv("DRIVER_API_TOKEN")
    start_date, end_date = default_dates(args.days_back)
    if args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
    elif args.start_date or args.end_date:
        raise ValueError("Both --start-date and --end-date must be provided together.")

    return SyncConfig(
        oura_api_base=OURA_API_BASE.rstrip("/"),
        oura_api_token=oura_api_token,
        driver_api_base=DRIVER_API_BASE.rstrip("/"),
        driver_api_token=driver_api_token.strip() if driver_api_token else None,
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
    )


def fetch_oura_collection(
    client: httpx.Client,
    *,
    api_base: str,
    token: str,
    endpoint: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_token: str | None = None

    while True:
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if next_token:
            params["next_token"] = next_token
        response = client.get(
            f"{api_base}/v2/usercollection/{endpoint}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        payload = response.json()
        records.extend(payload.get("data") or [])
        next_token = payload.get("next_token")
        if not next_token:
            break

    return records


def _nested_value(entry: dict[str, Any], *path: str) -> Any:
    current: Any = entry
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_readiness_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "day": entry.get("day") or entry.get("date"),
        "score": entry.get("score"),
        "average_hrv": (
            entry.get("average_hrv")
            or _nested_value(entry, "contributors", "hrv_balance", "value")
            or _nested_value(entry, "contributors", "hrv", "value")
        ),
        "resting_heart_rate": (
            entry.get("resting_heart_rate")
            or _nested_value(entry, "contributors", "resting_heart_rate", "value")
        ),
    }


def build_ingest_payload(
    sleep: list[dict[str, Any]],
    readiness: list[dict[str, Any]],
    activity: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "sleep": sleep,
        "readiness": [normalize_readiness_entry(entry) for entry in readiness],
        "activity": activity,
    }


def post_driver_ingest(
    client: httpx.Client,
    *,
    api_base: str,
    token: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = client.post(
        f"{api_base}/api/v1/ingest/oura",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def run_sync(config: SyncConfig, *, client: httpx.Client) -> dict[str, Any]:
    sleep = fetch_oura_collection(
        client,
        api_base=config.oura_api_base,
        token=config.oura_api_token,
        endpoint="sleep",
        start_date=config.start_date,
        end_date=config.end_date,
    )
    readiness = fetch_oura_collection(
        client,
        api_base=config.oura_api_base,
        token=config.oura_api_token,
        endpoint="daily_readiness",
        start_date=config.start_date,
        end_date=config.end_date,
    )
    activity = fetch_oura_collection(
        client,
        api_base=config.oura_api_base,
        token=config.oura_api_token,
        endpoint="daily_activity",
        start_date=config.start_date,
        end_date=config.end_date,
    )
    payload = build_ingest_payload(sleep, readiness, activity)

    if config.dry_run:
        print(json.dumps(payload, indent=2))
        return {
            "status": "dry_run",
            "processed": {
                "sleep": len(sleep),
                "readiness": len(readiness),
                "activity": len(activity),
                "skipped": 0,
            },
        }

    return post_driver_ingest(
        client,
        api_base=config.driver_api_base,
        token=config.driver_api_token,
        payload=payload,
    )


def main() -> int:
    try:
        args = parse_args()
        config = resolve_config(args)
        with httpx.Client(timeout=config.timeout_seconds) as client:
            result = run_sync(config, client=client)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, httpx.HTTPError) as exc:
        print(f"sync_oura failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
