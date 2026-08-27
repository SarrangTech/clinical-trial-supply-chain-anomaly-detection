"""Write-audit-publish over Iceberg branches.

Flow, per table, per run:

1. `ensure_wap_table` -- create the table (if missing) with
   `write.wap.enabled=true`.
2. `land_to_wap_branch` -- append the new batch with `spark.wap.branch` set.
   Iceberg auto-creates the branch and the write lands there, invisible on
   `main`, because the table has WAP enabled.
3. Caller reads the branch back with `read_wap_branch` and runs the GE suite
   against it (see `pipeline.validation.runner`), producing a valid/invalid
   row split.
4. `publish_or_quarantine` -- invalid rows are written to `<table>_quarantine`
   with a failure reason; valid rows are published to `main` (either by
   fast-forwarding the whole branch, when nothing failed, or by appending
   the clean subset directly, when some rows had to be split out). A branch
   that failed validation is *never* fast-forwarded -- bad data never reaches
   `main`, which is the property this whole module exists to guarantee.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)

QUARANTINE_SUFFIX = "_quarantine"


@dataclass(frozen=True)
class WapOutcome:
    """What happened to a single table's WAP batch."""

    table_name: str
    branch_name: str
    published_count: int
    quarantined_count: int
    fast_forwarded: bool


def ensure_wap_table(spark: SparkSession, table_name: str, schema_df: DataFrame) -> None:
    """Create `table_name` with WAP enabled if it doesn't already exist.

    Args:
        spark: An active SparkSession with the Iceberg catalog registered.
        table_name: `<namespace>.<table>`, resolved against the default catalog.
        schema_df: A DataFrame whose schema (not data -- `limit(0)` is used)
            defines the table's columns.
    """
    if spark.catalog.tableExists(table_name):
        return
    logger.info("Creating WAP-enabled table %s", table_name)
    (
        schema_df.limit(0)
        .writeTo(table_name)
        .using("iceberg")
        .tableProperty("write.wap.enabled", "true")
        .create()
    )


def land_to_wap_branch(
    spark: SparkSession, table_name: str, df: DataFrame, branch_name: str
) -> None:
    """Append `df` to `table_name`, isolated on `branch_name`.

    Requires `table_name` to already have `write.wap.enabled=true` (see
    `ensure_wap_table`) -- otherwise this would land directly on `main`.
    """
    spark.conf.set("spark.wap.branch", branch_name)
    try:
        row_count = df.count()
        df.writeTo(table_name).append()
        logger.info(
            "Landed %d rows to %s on branch %s (not yet on main)",
            row_count,
            table_name,
            branch_name,
        )
    finally:
        spark.conf.unset("spark.wap.branch")


def read_wap_branch(spark: SparkSession, table_name: str, branch_name: str) -> DataFrame:
    """Read the isolated batch from `branch_name`, not `main`."""
    return spark.read.option("branch", branch_name).table(table_name)


def _quarantine_table_name(table_name: str) -> str:
    return f"{table_name}{QUARANTINE_SUFFIX}"


def publish_or_quarantine(
    spark: SparkSession,
    table_name: str,
    branch_name: str,
    valid_df: DataFrame,
    invalid_df: DataFrame,
    catalog_name: str,
) -> WapOutcome:
    """Publish the valid rows from a WAP branch and quarantine the rest.

    Args:
        spark: An active SparkSession.
        table_name: The table the branch belongs to (`<namespace>.<table>`).
        branch_name: The branch that was audited.
        valid_df: Rows from the branch that passed validation.
        invalid_df: Rows from the branch that failed validation, with a
            `failure_reason` column already attached (see
            `pipeline.validation.runner`).
        catalog_name: The Iceberg catalog `table_name` lives in, needed for
            the `system.fast_forward` stored procedure call.

    Returns:
        A `WapOutcome` describing what was published vs. quarantined.
    """
    quarantine_count = invalid_df.count()
    valid_count = valid_df.count()

    if quarantine_count > 0:
        quarantine_table = _quarantine_table_name(table_name)
        invalid_with_run_info = invalid_df.withColumn("_quarantined_from_branch", F.lit(branch_name))
        ensure_wap_table(spark, quarantine_table, invalid_with_run_info)
        invalid_with_run_info.writeTo(quarantine_table).append()
        logger.warning(
            "Quarantined %d rows from %s (branch %s) into %s",
            quarantine_count,
            table_name,
            branch_name,
            quarantine_table,
        )

    fast_forwarded = False
    if valid_count > 0:
        if quarantine_count == 0:
            spark.sql(f"CALL {catalog_name}.system.fast_forward('{table_name}', 'main', '{branch_name}')")
            fast_forwarded = True
            logger.info(
                "Fast-forwarded %s main to branch %s (%d rows, 0 quarantined)",
                table_name,
                branch_name,
                valid_count,
            )
        else:
            valid_df.writeTo(table_name).append()
            logger.info(
                "Appended %d validated rows directly to %s main (branch %s kept as a"
                " rejected-batch audit record, not fast-forwarded)",
                valid_count,
                table_name,
                branch_name,
            )
    else:
        logger.warning(
            "No valid rows in branch %s for %s -- main left untouched", branch_name, table_name
        )

    return WapOutcome(
        table_name=table_name,
        branch_name=branch_name,
        published_count=valid_count,
        quarantined_count=quarantine_count,
        fast_forwarded=fast_forwarded,
    )
