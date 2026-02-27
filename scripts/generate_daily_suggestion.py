#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import date

import httpx

DRIVER_API_BASE = os.getenv("DRIVER_API_BASE", "http://localhost:8100").rstrip("/")
DRIVER_API_TOKEN = os.getenv("DRIVER_API_TOKEN")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate daily training suggestion in Driver."
    )
    parser.add_argument("--date", dest="target_date", help="Target date (YYYY-MM-DD).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    headers: dict[str, str] = {}
    if DRIVER_API_TOKEN:
        headers["Authorization"] = f"Bearer {DRIVER_API_TOKEN}"

    params = {"target_date": args.target_date} if args.target_date else None
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{DRIVER_API_BASE}/api/v1/training/suggestions/generate",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            print(json.dumps(response.json(), indent=2))
        return 0
    except httpx.HTTPError as exc:
        target = args.target_date or date.today().isoformat()
        print(f"generate_daily_suggestion failed for {target}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
