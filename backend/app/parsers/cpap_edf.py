"""Parse ResMed STR.edf files into nightly CPAP summary records.

The STR.edf (Settings/Therapy/Results) file contains one sample per day
across 78 signals. pyedflib returns physical (already-scaled) values.
Sentinel values of -1 or small negatives (e.g. -0.1, -0.02) indicate
"no data" for that day — we treat any value <= 0 as missing.

Key signals used:
  - "Date"          ordinal dates (e.g. 19963 = 2024-08-28)
  - "AHI"           events/hour (already scaled)
  - "Duration"      usage in minutes (convert to hours)
  - "Leak.95"       95th percentile leak in L/s
  - "MaskPress.50"  median mask pressure in cmH2O
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pyedflib


def _get_signal(signals: dict[str, list[float]], *names: str) -> list[float]:
    """Return the first matching signal by label, or empty list."""
    for name in names:
        if name in signals:
            return signals[name]
    return []


def _positive_or_none(value: float | None) -> float | None:
    """Return value if positive, else None. Filters sentinels (-1, -0.1, etc)."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN check
        return None
    return v if v > 0 else None


def parse_cpap_edf(path: str | Path) -> list[dict[str, Any]]:
    """Parse a ResMed STR.edf file and return a list of nightly CPAP records."""
    reader = pyedflib.EdfReader(str(path))
    try:
        signal_count = reader.signals_in_file
        labels = [reader.getLabel(i).strip() for i in range(signal_count)]
        signals: dict[str, list[float]] = {}
        for idx, label in enumerate(labels):
            values = reader.readSignal(idx)
            signals[label] = (
                values.tolist() if hasattr(values, "tolist") else list(values)
            )

        # Date signal contains ordinal day numbers
        date_signal = _get_signal(signals, "Date")
        # AHI is already in events/hour
        ahi_signal = _get_signal(signals, "AHI")
        # Duration is in minutes
        duration_signal = _get_signal(signals, "Duration")
        # Leak 95th percentile in L/s
        leak_signal = _get_signal(signals, "Leak.95")
        # Mask pressure median in cmH2O
        pressure_signal = _get_signal(signals, "MaskPress.50")

        length = max(len(date_signal), len(ahi_signal), len(duration_signal))
        if length == 0:
            return []

        start = reader.getStartdatetime().date()

        nights: list[dict[str, Any]] = []
        for idx in range(length):
            # Determine the date for this record
            raw_date = date_signal[idx] if idx < len(date_signal) else None
            if raw_date is not None and float(raw_date) > 0:
                try:
                    # ResMed Date signal is days since Unix epoch (1970-01-01)
                    recorded_date = date(1970, 1, 1) + timedelta(
                        days=int(round(float(raw_date)))
                    )
                except (OverflowError, ValueError):
                    recorded_date = start + timedelta(days=idx)
            else:
                recorded_date = start + timedelta(days=idx)

            ahi = _positive_or_none(ahi_signal[idx] if idx < len(ahi_signal) else None)
            duration_min = _positive_or_none(
                duration_signal[idx] if idx < len(duration_signal) else None
            )
            leak = _positive_or_none(
                leak_signal[idx] if idx < len(leak_signal) else None
            )
            pressure = _positive_or_none(
                pressure_signal[idx] if idx < len(pressure_signal) else None
            )

            # Skip days with no usable data (machine not used)
            if ahi is None and duration_min is None:
                continue

            hours = round(duration_min / 60, 2) if duration_min is not None else None

            nights.append(
                {
                    "recorded_date": recorded_date.isoformat(),
                    "cpap_used": 1,
                    "cpap_ahi": round(ahi, 2) if ahi is not None else None,
                    "cpap_hours": hours,
                    "cpap_leak_95": round(leak, 2) if leak is not None else None,
                    "cpap_pressure_avg": round(pressure, 2)
                    if pressure is not None
                    else None,
                }
            )

        return nights
    finally:
        reader.close()
