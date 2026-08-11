#!/usr/bin/env python
"""CLI: generate synthetic sites/shipments/dosing_events and land them as CSVs.

Usage (from repo root, so `pipeline` is importable):
    python -m scripts.run_generators --seed 42 --n-shipments 50000 --n-dosing-events 10000

`ingest_dag` picks these CSVs up from `data/` and lands them into the bronze
Iceberg tables; the `_ground_truth_*` sidecar files are for the evidence
metric ("percent of anomalies correctly flagged") only.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from pipeline.generators.dosing_events import generate_dosing_events
from pipeline.generators.io import write_ground_truth_json, write_records_csv
from pipeline.generators.shipments import generate_shipments
from pipeline.generators.sites import generate_sites

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-sites", type=int, default=300)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--n-shipments", type=int, default=50_000)
    parser.add_argument("--n-dosing-events", type=int, default=10_000)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    sites = generate_sites(n_sites=args.n_sites, n_trials=args.n_trials, seed=args.seed)
    shipments = generate_shipments(sites, n_shipments=args.n_shipments, seed=args.seed)
    dosing_events = generate_dosing_events(
        sites, n_events=args.n_dosing_events, seed=args.seed
    )

    write_records_csv(sites, args.output_dir / "sites.csv", id_field="site_id")
    write_records_csv(shipments, args.output_dir / "shipments.csv", id_field="shipment_id")
    write_records_csv(
        dosing_events, args.output_dir / "dosing_events.csv", id_field="event_id"
    )

    write_ground_truth_json(
        sites, id_field="site_id", path=args.output_dir / "ground_truth" / "sites.json"
    )
    write_ground_truth_json(
        shipments,
        id_field="shipment_id",
        path=args.output_dir / "ground_truth" / "shipments.json",
    )
    write_ground_truth_json(
        dosing_events,
        id_field="event_id",
        path=args.output_dir / "ground_truth" / "dosing_events.json",
    )

    logger.info(
        "Generated %d sites, %d shipments, %d dosing events into %s",
        len(sites),
        len(shipments),
        len(dosing_events),
        args.output_dir,
    )


if __name__ == "__main__":
    main()
