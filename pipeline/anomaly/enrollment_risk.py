"""Enrollment risk assessment via simple linear pace projection.

Rule: `pace = enrollment_actual / days_elapsed_since_start`; the site is
`AT_RISK` if `enrollment_actual + pace * days_remaining < enrollment_target`
before `enrollment_deadline`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

STATUS_COMPLETE = "COMPLETE"
STATUS_ON_TRACK = "ON_TRACK"
STATUS_AT_RISK = "AT_RISK"
STATUS_MISSED = "MISSED"


@dataclass(frozen=True)
class EnrollmentRiskResult:
    """Outcome of projecting one site's enrollment pace forward."""

    status: str
    pace_per_day: float
    projected_final: float
    days_remaining: int
    risk_score: float


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def assess_enrollment_risk(
    enrollment_target: int,
    enrollment_actual: int,
    enrollment_start_date: str | date,
    enrollment_deadline: str | date,
    as_of: str | date | None = None,
) -> EnrollmentRiskResult:
    """Project a site's enrollment pace forward and classify its risk.

    Args:
        enrollment_target: Total patients the site needs to enroll.
        enrollment_actual: Patients enrolled so far.
        enrollment_start_date: When the site began enrolling.
        enrollment_deadline: The date `enrollment_target` must be hit by.
        as_of: "Today" for the projection. Defaults to the real current date.

    Returns:
        An `EnrollmentRiskResult`. `risk_score` is `0.0` for `COMPLETE` and
        `ON_TRACK`, and in `(0.0, 1.0]` for `AT_RISK`/`MISSED`, scaled by how
        far short of target the linear projection lands.
    """
    start = _parse_date(enrollment_start_date)
    deadline = _parse_date(enrollment_deadline)
    today = _parse_date(as_of) if as_of is not None else date.today()

    if enrollment_actual >= enrollment_target:
        return EnrollmentRiskResult(STATUS_COMPLETE, 0.0, float(enrollment_actual), 0, 0.0)

    days_elapsed = (today - start).days
    pace_per_day = enrollment_actual / days_elapsed if days_elapsed > 0 else 0.0
    days_remaining = max((deadline - today).days, 0)
    projected_final = enrollment_actual + pace_per_day * days_remaining

    if today >= deadline:
        status = STATUS_MISSED
    elif projected_final < enrollment_target:
        status = STATUS_AT_RISK
    else:
        status = STATUS_ON_TRACK

    risk_score = 0.0
    if status in (STATUS_AT_RISK, STATUS_MISSED):
        risk_score = round(
            max(0.0, min(1.0, (enrollment_target - projected_final) / enrollment_target)), 4
        )

    return EnrollmentRiskResult(
        status=status,
        pace_per_day=round(pace_per_day, 4),
        projected_final=round(projected_final, 2),
        days_remaining=days_remaining,
        risk_score=risk_score,
    )
