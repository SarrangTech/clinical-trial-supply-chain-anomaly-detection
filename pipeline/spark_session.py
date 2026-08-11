"""Builds a SparkSession wired to the Iceberg REST catalog.

Used two ways:
- DAGs (`transform_dag`, `ingest_dag`) call `build_spark_session()` with no
  overrides, which submits to the standalone Spark cluster and the real
  REST-catalog-backed S3 warehouse defined in `pipeline.config`.
- `tests/conftest.py` calls it with `master_url="local[2]"` and a SQLite-backed
  catalog pointed at a pytest `tmp_path`, so the unit test suite never needs
  the live Spark cluster or real S3 credentials.
"""

from __future__ import annotations

import logging

from pyspark.sql import SparkSession

from pipeline.config import Settings, get_settings

logger = logging.getLogger(__name__)

ICEBERG_VERSION = "1.6.1"
_SPARK_ICEBERG_PACKAGES = (
    f"org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:{ICEBERG_VERSION},"
    f"org.apache.iceberg:iceberg-aws-bundle:{ICEBERG_VERSION}"
)


def build_spark_session(
    app_name: str = "clinical-trial-supply-chain",
    settings: Settings | None = None,
    master_url: str | None = None,
    extra_conf: dict[str, str] | None = None,
) -> SparkSession:
    """Build a SparkSession with the Iceberg catalog named in `settings` registered.

    Args:
        app_name: Spark application name, shown in the Spark UI.
        settings: Defaults to `pipeline.config.get_settings()`.
        master_url: Overrides `settings.spark_master_url` (tests use `local[*]`).
        extra_conf: Additional/overriding Spark confs, applied last -- lets
            tests swap in a SQLite catalog + local warehouse instead of the
            REST catalog + S3.

    Returns:
        A configured, not-yet-started-any-job SparkSession.
    """
    settings = settings or get_settings()
    catalog_name = settings.iceberg_catalog_name

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master_url or settings.spark_master_url)
        .config("spark.jars.packages", _SPARK_ICEBERG_PACKAGES)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(f"spark.sql.catalog.{catalog_name}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog_name}.type", "rest")
        .config(f"spark.sql.catalog.{catalog_name}.uri", settings.iceberg_rest_uri)
        .config(f"spark.sql.catalog.{catalog_name}.warehouse", settings.warehouse_path)
        .config(
            f"spark.sql.catalog.{catalog_name}.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO",
        )
        .config(f"spark.sql.catalog.{catalog_name}.s3.region", settings.aws_region)
        .config("spark.sql.defaultCatalog", catalog_name)
    )

    for key, value in (extra_conf or {}).items():
        builder = builder.config(key, value)

    logger.info(
        "Building SparkSession app_name=%s master=%s catalog=%s warehouse=%s",
        app_name,
        master_url or settings.spark_master_url,
        catalog_name,
        settings.warehouse_path,
    )
    return builder.getOrCreate()
