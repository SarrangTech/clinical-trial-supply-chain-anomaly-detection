"""Synthetic clinical trial data generators.

Each generator returns a list of plain-dict records with real (non-`_`
prefixed) keys matching the bronze schema, plus a `_ground_truth_*` key
tracking whether an anomaly was deliberately injected into that record. The
ground-truth key is for tests and the evidence-collection script (see
`scripts/run_generators.py`) only -- it is never written to the CSVs that get
landed into the bronze Iceberg tables, since it isn't a real-world field.
"""
