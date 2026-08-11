"""Environment-driven settings shared by DAGs, the FastAPI service, and tests.

Everything here is read from the environment (populated from `.env` in local
dev, or real container env vars in Docker Compose / CI) -- nothing is
hardcoded, and no credential ever has a default value that looks like it
could be mistaken for a real one.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated once and cached for the process lifetime."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"

    s3_bucket: str = "clinical-trial-supply-chain-anomaly-detection"
    s3_warehouse_prefix: str = "warehouse"

    iceberg_catalog_name: str = "clinical_trials"
    iceberg_rest_uri: str = "http://iceberg-rest:8181"

    spark_master_url: str = "spark://spark-master:7077"

    api_key: str = "dev-local-anomaly-api-key"

    cold_chain_breach_minutes: int = 30
    dosing_window_days: int = 3

    @property
    def warehouse_path(self) -> str:
        """The S3 URI Iceberg tables are written under."""
        return f"s3://{self.s3_bucket}/{self.s3_warehouse_prefix}"

    @property
    def catalog_properties(self) -> dict[str, str]:
        """Properties for `pyiceberg.catalog.load_catalog(**properties)`."""
        props = {
            "type": "rest",
            "uri": self.iceberg_rest_uri,
            "warehouse": self.warehouse_path,
            "s3.region": self.aws_region,
        }
        if self.aws_access_key_id and self.aws_secret_access_key:
            props["s3.access-key-id"] = self.aws_access_key_id
            props["s3.secret-access-key"] = self.aws_secret_access_key
        return props


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached settings instance."""
    return Settings()
