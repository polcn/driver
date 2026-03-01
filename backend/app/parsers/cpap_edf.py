from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyedflib


def _clean_label(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _is_valid_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number  # filters NaN


def _pick_value(series: list[float], index: int) -> float | None:
    if index < 0 or index >= len(series):
        return None
    value = series[index]
    if _is_valid_number(value):
        return float(value)
    return None


def _extract_date_series(signals: dict[str, list[float]], length: int) -> list[date | None]:
    date_signal = signals.get("date") or signals.get("session_date") or []
    result: list[date | None] = []
    for idx in range(length):
        raw = _pick_value(date_signal, idx)
        if raw is None:
            result.append(None)
            continue
        ordinal = int(round(raw))
        try:
            result.append(datetime.fromordinal(ordinal).date())
        except (OverflowError, ValueError):
            result.append(None)
    return result


def _derive_length(signals: dict[str, list[float]]) -> int:
    return max((len(values) for values in signals.values()), default=0)


def parse_cpap_edf(path: str | Path) -> list[dict[str, Any]]:
    reader = pyedflib.EdfReader(str(path))
    try:
        signal_count = reader.signals_in_file
        labels = [_clean_label(reader.getLabel(i)) for i in range(signal_count)]
        signals: dict[str, list[float]] = {}
        for idx, label in enumerate(labels):
            values = reader.readSignal(idx)
            signals[label] = values.tolist() if hasattr(values, "tolist") else list(values)

        length = _derive_length(signals)
        if length == 0:
            return []

        start = reader.getStartdatetime().date()
        date_series = _extract_date_series(signals, length)

        ahi_series = (
            signals.get("ahi")
            or signals.get("cpap_ahi")
            or signals.get("apnea_hypopnea_index")
            or []
        )
        hours_series = (
            signals.get("usage_hours")
            or signals.get("hours")
            or signals.get("cpap_hours")
            or []
        )
        leak_series = (
            signals.get("leak_95")
            or signals.get("95th_percentile_leak")
            or signals.get("cpap_leak_95")
            or []
        )
        pressure_series = (
            signals.get("pressure_avg")
            or signals.get("average_pressure")
            or signals.get("cpap_pressure_avg")
            or []
        )

        nights: list[dict[str, Any]] = []
        for idx in range(length):
            recorded_date = date_series[idx] or (start + timedelta(days=idx))

            ahi_raw = _pick_value(ahi_series, idx)
            hours_raw = _pick_value(hours_series, idx)
            leak_raw = _pick_value(leak_series, idx)
            pressure_raw = _pick_value(pressure_series, idx)

            if ahi_raw is None and hours_raw is None and leak_raw is None and pressure_raw is None:
                continue

            nights.append(
                {
                    "recorded_date": recorded_date.isoformat(),
                    "cpap_used": 1,
                    "cpap_ahi": round(ahi_raw * 0.1, 2) if ahi_raw is not None else None,
                    "cpap_hours": round(hours_raw, 2) if hours_raw is not None else None,
                    "cpap_leak_95": round(leak_raw * 0.02, 2) if leak_raw is not None else None,
                    "cpap_pressure_avg": round(pressure_raw * 0.02, 2)
                    if pressure_raw is not None
                    else None,
                }
            )

        return nights
    finally:
        reader.close()
