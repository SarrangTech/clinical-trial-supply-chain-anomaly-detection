"""Synthetic dosing event generator, with injected protocol deviations.

`protocol_deviation_flag` is generated as a *noisy* signal deliberately --
sites don't catch every deviation, and occasionally flag a dose that was
actually within window (data entry error). This gives
`pipeline.anomaly.dosing_deviation`'s independent date-math check something
real to add on top of the raw flag, rather than the flag alone being a
perfect oracle.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_DEVIATION_RATE = 0.12
PATIENTS_PER_SITE = 25
# Fraction of true deviations the site actually flags, and the false-positive
# rate on doses that were within window but get flagged anyway.
FLAG_TRUE_POSITIVE_RATE = 0.8
FLAG_FALSE_POSITIVE_RATE = 0.02


def generate_dosing_events(
    sites: list[dict],
    n_events: int = 10_000,
    seed: int = 42,
    deviation_rate: float = DEFAULT_DEVIATION_RATE,
    window_days: int = 3,
    as_of: datetime | None = None,
    lookback_days: int = 365,
) -> list[dict]:
    """Generate synthetic dosing events.

    Args:
        sites: Output of `pipeline.generators.sites.generate_sites` -- each
            event belongs to a `(trial_id, site_id)` drawn from it.
        n_events: Total number of dosing events to generate.
        seed: RNG seed; the same seed always produces the same events.
        deviation_rate: Fraction of events with a deliberately injected
            `actual_date` more than `window_days` from `scheduled_date`.
        window_days: The acceptable scheduled-vs-actual window; also the
            default used by `pipeline.anomaly.dosing_deviation`.
        as_of: "Today" for the purposes of the scheduling lookback window.
        lookback_days: Scheduled dates are spread across the `lookback_days`
            days before `as_of`.

    Returns:
        One dict per event with keys: event_id, patient_id, trial_id,
        scheduled_date, actual_date, protocol_deviation_flag,
        _ground_truth_deviation.
    """
    if not sites:
        raise ValueError("generate_dosing_events requires at least one site")

    rng = random.Random(seed)
    as_of = as_of or datetime.now(UTC)

    events: list[dict] = []
    for i in range(1, n_events + 1):
        event_id = f"EVT-{i:07d}"
        site = rng.choice(sites)
        trial_id = site["trial_id"]
        patient_num = rng.randint(1, PATIENTS_PER_SITE)
        patient_id = f"PT-{site['site_id']}-{patient_num:04d}"

        scheduled_date = as_of - timedelta(days=rng.uniform(0, lookback_days))
        is_deviation = rng.random() < deviation_rate
        if is_deviation:
            delta_days = window_days + rng.uniform(1, 14)
            if rng.random() < 0.5:
                delta_days = -delta_days
        else:
            delta_days = rng.gauss(0, 0.5)
            delta_days = max(-window_days + 0.1, min(window_days - 0.1, delta_days))
        actual_date = scheduled_date + timedelta(days=delta_days)

        if is_deviation:
            protocol_deviation_flag = rng.random() < FLAG_TRUE_POSITIVE_RATE
        else:
            protocol_deviation_flag = rng.random() < FLAG_FALSE_POSITIVE_RATE

        events.append(
            {
                "event_id": event_id,
                "patient_id": patient_id,
                "trial_id": trial_id,
                "scheduled_date": scheduled_date.date().isoformat(),
                "actual_date": actual_date.date().isoformat(),
                "protocol_deviation_flag": protocol_deviation_flag,
                "_ground_truth_deviation": is_deviation,
            }
        )

    logger.info(
        "Generated %d dosing events (%d with an injected protocol deviation)",
        len(events),
        sum(1 for e in events if e["_ground_truth_deviation"]),
    )
    return events
