"""Cold chain break detection.

Rule: a shipment breaches cold chain if it has a *contiguous* run of
temperature readings outside `required_temp_range` spanning more than
`breach_minutes_threshold` minutes (default 30). A single isolated
out-of-range reading, with in-range readings immediately before and after
it, is not treated as a sustained breach -- there is no evidence it
persisted rather than being one noisy sensor sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_BREACH_MINUTES_THRESHOLD = 30


@dataclass(frozen=True)
class ColdChainResult:
    """Outcome of evaluating one shipment's temperature log."""

    is_breach: bool
    breach_duration_minutes: float
    max_excursion_c: float
    severity: str
    breach_start: str | None
    breach_end: str | None


def _parse_timestamp(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _excursion(temp_c: float, lo: float, hi: float) -> float:
    """How far outside [lo, hi] `temp_c` is; 0.0 if inside."""
    if temp_c < lo:
        return lo - temp_c
    if temp_c > hi:
        return temp_c - hi
    return 0.0


def _severity(duration_minutes: float, max_excursion_c: float, threshold_minutes: int) -> str:
    if duration_minutes < threshold_minutes:
        return "none"
    if duration_minutes >= threshold_minutes * 2 or max_excursion_c >= 5.0:
        return "critical"
    if duration_minutes >= threshold_minutes * 1.5 or max_excursion_c >= 3.0:
        return "high"
    return "medium"


def detect_cold_chain_breach(
    temperature_log: list[dict],
    required_temp_range: tuple[float, float] | list[float],
    breach_minutes_threshold: int = DEFAULT_BREACH_MINUTES_THRESHOLD,
) -> ColdChainResult:
    """Evaluate a single shipment's temperature log for a sustained cold-chain break.

    Args:
        temperature_log: List of `{"timestamp": iso-str, "temp_c": float}`
            readings, in any order (sorted internally by timestamp). Readings
            with a missing/null `temp_c` are skipped -- they carry no
            evidence either way.
        required_temp_range: `(min_c, max_c)` the shipment must stay within.
        breach_minutes_threshold: Minimum duration an out-of-range run must
            span to count as a breach.

    Returns:
        A `ColdChainResult` describing the longest qualifying breach run, if
        any. `severity` is `"none"` when `is_breach` is `False`.
    """
    lo, hi = required_temp_range
    readings = [
        (_parse_timestamp(r["timestamp"]), r["temp_c"])
        for r in temperature_log
        if r.get("temp_c") is not None
    ]
    readings.sort(key=lambda r: r[0])

    best_duration = 0.0
    best_excursion = 0.0
    best_start: datetime | None = None
    best_end: datetime | None = None

    run_start: datetime | None = None
    run_end: datetime | None = None
    run_max_excursion = 0.0

    def flush_run() -> None:
        nonlocal best_duration, best_excursion, best_start, best_end
        if run_start is None or run_end is None:
            return
        duration = (run_end - run_start).total_seconds() / 60
        if duration > best_duration:
            best_duration = duration
            best_excursion = run_max_excursion
            best_start = run_start
            best_end = run_end

    for timestamp, temp_c in readings:
        excursion = _excursion(temp_c, lo, hi)
        if excursion > 0:
            if run_start is None:
                run_start = timestamp
            run_end = timestamp
            run_max_excursion = max(run_max_excursion, excursion)
        else:
            flush_run()
            run_start, run_end, run_max_excursion = None, None, 0.0
    flush_run()

    is_breach = best_duration >= breach_minutes_threshold
    severity = _severity(best_duration, best_excursion, breach_minutes_threshold) if is_breach else "none"

    return ColdChainResult(
        is_breach=is_breach,
        breach_duration_minutes=round(best_duration, 1),
        max_excursion_c=round(best_excursion, 2) if is_breach else 0.0,
        severity=severity,
        breach_start=best_start.isoformat() if is_breach and best_start else None,
        breach_end=best_end.isoformat() if is_breach and best_end else None,
    )
