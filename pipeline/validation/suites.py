"""Great Expectations suites for the bronze layer.

Deliberately structural/data-quality checks only (nulls, uniqueness,
controlled vocabularies, physically-plausible bounds, temporal sanity) --
never the business rules `pipeline.anomaly` implements. A shipment sitting
outside `required_temp_range`, a site behind enrollment pace, or a dose
outside its window are real-world conditions the gold layer exists to
surface, not data defects to quarantine before anyone sees them. See
`pipeline/anomaly/` for those rules.
"""

from __future__ import annotations

import great_expectations as gx
import great_expectations.expectations as gxe
from great_expectations.core.expectation_suite import ExpectationSuite
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from pipeline.generators.shipments import CARRIERS

# Any reading outside this range indicates a malfunctioning sensor, not a
# real (if extreme) shipment condition -- the widest of the three temperature
# profiles is (-25, 25), so +/-50 leaves comfortable headroom before treating
# a reading as physically implausible.
PLAUSIBLE_SENSOR_MIN_C = -50.0
PLAUSIBLE_SENSOR_MAX_C = 50.0


def _ensure_context() -> None:
    """Ensure a Great Expectations data context is active.

    `ExpectationSuite.add_expectation` unconditionally checks for a
    process-wide active context (to know whether/where the suite would be
    persisted), even for a suite that's only ever used in-memory the way
    `pipeline.validation.runner` uses these. Calling this first avoids a
    `DataContextRequiredError` regardless of whether `runner.py` has already
    created its own (ephemeral) context by the time these run.
    """
    gx.get_context(mode="ephemeral")


def prepare_shipments_for_validation(df: DataFrame) -> DataFrame:
    """Add `has_implausible_reading`, derived from `temperature_log`.

    Great Expectations validates flat columns; this derives a shipment-grain
    boolean from the nested `temperature_log` array so the plausibility check
    can run as an ordinary column expectation in `shipments_suite()`, without
    needing to explode the array into its own batch.
    """
    return df.withColumn(
        "has_implausible_reading",
        F.exists(
            "temperature_log",
            lambda reading: (reading["temp_c"] < PLAUSIBLE_SENSOR_MIN_C)
            | (reading["temp_c"] > PLAUSIBLE_SENSOR_MAX_C),
        ),
    )


def shipments_suite() -> ExpectationSuite:
    """Structural checks for the bronze shipments batch (grain: shipment_id).

    Requires `prepare_shipments_for_validation` to have been applied first.
    """
    _ensure_context()
    suite = gx.ExpectationSuite(name="shipments_suite")
    for column in (
        "shipment_id",
        "trial_id",
        "origin_site",
        "destination_site",
        "carrier",
        "ship_timestamp",
        "expected_arrival",
        "actual_arrival",
    ):
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="shipment_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(column="carrier", value_set=CARRIERS))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column="has_implausible_reading", value_set=[False])
    )
    suite.add_expectation(
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="actual_arrival", column_B="ship_timestamp"
        )
    )
    return suite


def sites_suite() -> ExpectationSuite:
    """Structural checks for the bronze sites batch (grain: site_id)."""
    _ensure_context()
    suite = gx.ExpectationSuite(name="sites_suite")
    for column in (
        "site_id",
        "trial_id",
        "country",
        "enrollment_deadline",
        "enrollment_start_date",
    ):
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="site_id"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="enrollment_actual", min_value=0)
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="enrollment_target", min_value=1)
    )
    suite.add_expectation(
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="enrollment_deadline", column_B="enrollment_start_date"
        )
    )
    return suite


def dosing_events_suite() -> ExpectationSuite:
    """Structural checks for the bronze dosing_events batch (grain: event_id)."""
    _ensure_context()
    suite = gx.ExpectationSuite(name="dosing_events_suite")
    for column in (
        "event_id",
        "patient_id",
        "trial_id",
        "scheduled_date",
        "actual_date",
        "protocol_deviation_flag",
    ):
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="event_id"))
    return suite
