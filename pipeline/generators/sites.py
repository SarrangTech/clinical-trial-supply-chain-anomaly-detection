"""Synthetic clinical trial site generator.

Sites are generated first because shipments and dosing events both reference
a site's `site_id`/`trial_id` pair to stay referentially consistent -- see
`pipeline.generators.shipments` and `pipeline.generators.dosing_events`.
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta

logger = logging.getLogger(__name__)

COUNTRIES = [
    "United States",
    "Germany",
    "France",
    "United Kingdom",
    "Spain",
    "Italy",
    "Poland",
    "Japan",
    "South Korea",
    "Brazil",
    "Canada",
    "Australia",
]

# Fraction of sites deliberately generated with a pace that will miss their
# enrollment deadline -- the ground truth `pipeline.anomaly.enrollment_risk`
# is expected to catch.
DEFAULT_AT_RISK_RATE = 0.15

# Fraction of sites with a deliberately invalid `enrollment_actual` -- a
# data-quality defect for `pipeline.validation` to quarantine, distinct from
# (and independent of) being behind enrollment pace, which is a legitimate
# business condition, not a data defect.
DEFAULT_DATA_QUALITY_DEFECT_RATE = 0.01


def generate_sites(
    n_sites: int = 300,
    n_trials: int = 20,
    seed: int = 42,
    at_risk_rate: float = DEFAULT_AT_RISK_RATE,
    data_quality_defect_rate: float = DEFAULT_DATA_QUALITY_DEFECT_RATE,
    as_of: date | None = None,
) -> list[dict]:
    """Generate synthetic clinical trial sites.

    Args:
        n_sites: Total number of sites to generate.
        n_trials: Number of distinct trials sites are distributed across.
        seed: RNG seed; the same seed always produces the same sites.
        at_risk_rate: Fraction of sites deliberately given a pace that will
            miss `enrollment_deadline` under a linear projection.
        data_quality_defect_rate: Fraction of sites given an invalid negative
            `enrollment_actual` -- a data-quality defect for
            `pipeline.validation` to quarantine.
        as_of: "Today" for the purposes of computing elapsed enrollment
            pace. Defaults to the real current date.

    Returns:
        One dict per site with keys: site_id, trial_id, country,
        enrollment_target, enrollment_actual, enrollment_deadline,
        enrollment_start_date, _ground_truth_at_risk, _ground_truth_data_defect.
    """
    rng = random.Random(seed)
    as_of = as_of or date.today()
    trial_ids = [f"TRIAL-{i:04d}" for i in range(1, n_trials + 1)]

    sites: list[dict] = []
    for i in range(1, n_sites + 1):
        site_id = f"SITE-{i:05d}"
        trial_id = rng.choice(trial_ids)
        country = rng.choice(COUNTRIES)

        enrollment_start_date = as_of - timedelta(days=rng.randint(60, 540))
        days_elapsed = max((as_of - enrollment_start_date).days, 1)
        enrollment_deadline = enrollment_start_date + timedelta(days=rng.randint(365, 900))
        enrollment_target = rng.randint(20, 200)

        is_at_risk = rng.random() < at_risk_rate
        days_total = max((enrollment_deadline - enrollment_start_date).days, 1)
        on_pace_fraction = days_elapsed / days_total
        if is_at_risk:
            # Enrolled well below the pace needed to hit the deadline.
            actual_fraction = on_pace_fraction * rng.uniform(0.2, 0.55)
        else:
            actual_fraction = on_pace_fraction * rng.uniform(0.85, 1.25)
        enrollment_actual = min(
            enrollment_target, max(0, round(enrollment_target * actual_fraction))
        )

        inject_defect = rng.random() < data_quality_defect_rate
        if inject_defect:
            enrollment_actual = -1

        sites.append(
            {
                "site_id": site_id,
                "trial_id": trial_id,
                "country": country,
                "enrollment_target": enrollment_target,
                "enrollment_actual": enrollment_actual,
                "enrollment_deadline": enrollment_deadline.isoformat(),
                "enrollment_start_date": enrollment_start_date.isoformat(),
                "_ground_truth_at_risk": is_at_risk,
                "_ground_truth_data_defect": inject_defect,
            }
        )

    logger.info(
        "Generated %d sites across %d trials (%d flagged at-risk, %d with an injected"
        " data-quality defect)",
        len(sites),
        n_trials,
        sum(1 for s in sites if s["_ground_truth_at_risk"]),
        sum(1 for s in sites if s["_ground_truth_data_defect"]),
    )
    return sites
