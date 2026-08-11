"""CSV serialization for generated records.

Kept separate from the generator functions themselves so
`pipeline/generators/{shipments,sites,dosing_events}.py` stay pure functions
returning plain Python data -- easy to unit test without touching disk.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GROUND_TRUTH_PREFIX = "_ground_truth_"


def write_records_csv(records: list[dict], path: Path, id_field: str) -> None:
    """Write `records` to `path` as CSV, dropping ground-truth-only fields.

    List/dict-valued fields (e.g. shipments' `temperature_log`) are
    JSON-encoded as strings -- CSV has no native nested-type support, and
    `ingest_dag` parses them back out with `pyspark.sql.functions.from_json`
    when landing bronze, matching how real telemetry payloads are commonly
    shipped as JSON blobs inside otherwise-tabular source extracts.

    Args:
        records: Generator output (may contain `_ground_truth_*` keys).
        path: Destination CSV path; parent directories are created if needed.
        id_field: The record's identifier field, used only for the log line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    official_fields = [k for k in records[0] if not k.startswith(GROUND_TRUTH_PREFIX)]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=official_fields)
        writer.writeheader()
        for record in records:
            row = {}
            for field in official_fields:
                value = record[field]
                row[field] = json.dumps(value) if isinstance(value, list | dict) else value
            writer.writerow(row)

    logger.info("Wrote %d records (keyed by %s) to %s", len(records), id_field, path)


def write_ground_truth_json(records: list[dict], id_field: str, path: Path) -> None:
    """Write a `{id: {ground_truth_field: value, ...}}` sidecar for evaluation.

    Used only by the evidence-collection step (comparing detected anomalies
    against what was deliberately injected) -- never landed into bronze.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ground_truth = {
        record[id_field]: {
            k[len(GROUND_TRUTH_PREFIX) :]: v
            for k, v in record.items()
            if k.startswith(GROUND_TRUTH_PREFIX)
        }
        for record in records
    }
    path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    logger.info("Wrote ground truth for %d records to %s", len(ground_truth), path)
