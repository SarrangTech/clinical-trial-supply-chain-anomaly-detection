"""Dosing protocol deviation detection.

Rule: a dose is a protocol deviation if `actual_date` falls outside an
`window_days`-day window of `scheduled_date`, OR the upstream
`protocol_deviation_flag` was already set. The two signals are independent --
site staff don't catch every deviation, and occasionally over-flag -- so
`source` reports which one(s) actually fired.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

DEFAULT_WINDOW_DAYS = 3

SOURCE_NONE = "none"
SOURCE_DATE_WINDOW = "date_window"
SOURCE_FLAG = "flag"
SOURCE_BOTH = "both"


@dataclass(frozen=True)
class DosingDeviationResult:
    """Outcome of evaluating one dosing event."""

    is_deviation: bool
    delta_days: float
    severity: str
    source: str


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _severity(abs_delta_days: float, window_days: int) -> str:
    if abs_delta_days <= window_days:
        return "none"
    if abs_delta_days >= window_days * 3:
        return "critical"
    if abs_delta_days >= window_days * 2:
        return "high"
    return "medium"


def detect_dosing_deviation(
    scheduled_date: str | date,
    actual_date: str | date,
    protocol_deviation_flag: bool = False,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> DosingDeviationResult:
    """Evaluate a single dosing event for a protocol deviation.

    Args:
        scheduled_date: The protocol-specified dosing date.
        actual_date: The date dosing actually occurred.
        protocol_deviation_flag: The upstream (possibly noisy) site-reported flag.
        window_days: Days of slack around `scheduled_date` considered acceptable.

    Returns:
        A `DosingDeviationResult`. `source` is `"date_window"` if only the
        date math triggered, `"flag"` if only the upstream flag did,
        `"both"` if both did, and `"none"` if neither did.
    """
    scheduled = _parse_date(scheduled_date)
    actual = _parse_date(actual_date)
    delta_days = (actual - scheduled).days
    date_window_triggered = abs(delta_days) > window_days

    is_deviation = date_window_triggered or protocol_deviation_flag
    if date_window_triggered and protocol_deviation_flag:
        source = SOURCE_BOTH
    elif date_window_triggered:
        source = SOURCE_DATE_WINDOW
    elif protocol_deviation_flag:
        source = SOURCE_FLAG
    else:
        source = SOURCE_NONE

    severity = _severity(abs(delta_days), window_days) if is_deviation else "none"
    if is_deviation and severity == "none":
        # Flag-only deviations (delta within window) still get a floor severity.
        severity = "medium"

    return DosingDeviationResult(
        is_deviation=is_deviation,
        delta_days=float(delta_days),
        severity=severity,
        source=source,
    )
