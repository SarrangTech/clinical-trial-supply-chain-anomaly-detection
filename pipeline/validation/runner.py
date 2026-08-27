"""Runs a Great Expectations suite against a Spark DataFrame batch and
splits it into valid/invalid rows for `pipeline.wap.write_audit_publish`.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.expectations.expectation_configuration import ExpectationConfiguration
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationOutcome:
    """Row-level result of validating one table's batch against one suite."""

    success: bool
    total_rows: int
    failed_ids: set[str]
    failure_reasons: dict[str, list[str]] = field(default_factory=dict)
    expectation_pass_count: int = 0
    expectation_fail_count: int = 0


def _expectation_label(expectation_config: ExpectationConfiguration) -> str:
    column = expectation_config.kwargs.get("column")
    return f"{expectation_config.type}({column})" if column else expectation_config.type


def validate_dataframe(
    df: DataFrame,
    suite: ExpectationSuite,
    id_column: str,
) -> ValidationOutcome:
    """Validate `df` against `suite`, attributing failures back to `id_column`.

    Only expectations whose result includes a row-level `unexpected_index_list`
    (true of every column-map-style expectation used in `pipeline.validation.suites`)
    contribute to `failed_ids` -- a suite built from anything else would need
    a different, table-level failure path, which this project doesn't use.

    Args:
        df: The WAP branch batch to validate.
        suite: One of the suites in `pipeline.validation.suites`.
        id_column: The row identifier column results are keyed by.

    Returns:
        A `ValidationOutcome` with the set of failing ids and, for each, the
        human-readable expectation(s) that failed on it.
    """
    context = gx.get_context(mode="ephemeral")
    datasource = context.data_sources.add_spark(name=f"spark_ds_{uuid.uuid4().hex}")
    asset = datasource.add_dataframe_asset(name="batch_asset")
    batch_definition = asset.add_batch_definition_whole_dataframe(f"batch_def_{uuid.uuid4().hex}")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    result = batch.validate(
        suite,
        result_format={
            "result_format": "COMPLETE",
            "unexpected_index_column_names": [id_column],
        },
    )

    failure_reasons: dict[str, list[str]] = {}
    pass_count = 0
    fail_count = 0
    for expectation_result in result.results:
        if expectation_result.success:
            pass_count += 1
            continue
        fail_count += 1
        label = _expectation_label(expectation_result.expectation_config)
        unexpected_index_list = expectation_result.result.get("unexpected_index_list") or []
        for row in unexpected_index_list:
            row_id = row[id_column]
            if row_id is None:
                # A null id can't be attributed back via a join/isin (SQL
                # NULL never equals anything) -- split_valid_invalid handles
                # every null-id row as invalid unconditionally instead.
                continue
            failure_reasons.setdefault(str(row_id), []).append(label)

    total_rows = df.count()
    logger.info(
        "Validated %d rows against suite '%s': %d expectations passed, %d failed,"
        " %d distinct rows implicated",
        total_rows,
        suite.name,
        pass_count,
        fail_count,
        len(failure_reasons),
    )

    return ValidationOutcome(
        success=result.success,
        total_rows=total_rows,
        failed_ids=set(failure_reasons.keys()),
        failure_reasons=failure_reasons,
        expectation_pass_count=pass_count,
        expectation_fail_count=fail_count,
    )


def split_valid_invalid(
    spark: SparkSession,
    df: DataFrame,
    id_column: str,
    outcome: ValidationOutcome,
) -> tuple[DataFrame, DataFrame]:
    """Split `df` into (valid_df, invalid_df) using `outcome.failed_ids`.

    `invalid_df` gains a `failure_reason` column (the joined list of failed
    expectation labels for that row). Rows with a null `id_column` are
    always treated as invalid -- a SQL `NULL` never matches an `isin(...)`
    or join, so they can't be attributed via `outcome.failed_ids` and are
    handled separately here instead.
    """
    null_id_invalid = df.filter(F.col(id_column).isNull()).withColumn(
        "failure_reason", F.lit(f"{id_column} is null")
    )
    non_null_df = df.filter(F.col(id_column).isNotNull())

    if not outcome.failed_ids:
        empty_invalid = non_null_df.limit(0).withColumn(
            "failure_reason", F.lit(None).cast(StringType())
        )
        return non_null_df, empty_invalid.unionByName(null_id_invalid)

    reasons_schema = StructType(
        [
            StructField(id_column, StringType(), False),
            StructField("failure_reason", StringType(), False),
        ]
    )
    reasons_rows = [
        (row_id, "; ".join(reasons)) for row_id, reasons in outcome.failure_reasons.items()
    ]
    reasons_df = spark.createDataFrame(reasons_rows, schema=reasons_schema)

    id_col_str = F.col(id_column).cast(StringType())
    ge_flagged_invalid = non_null_df.filter(id_col_str.isin(list(outcome.failed_ids))).join(
        reasons_df, on=id_column, how="inner"
    )
    valid_df = non_null_df.filter(~id_col_str.isin(list(outcome.failed_ids)))
    invalid_df = ge_flagged_invalid.unionByName(null_id_invalid)
    return valid_df, invalid_df
