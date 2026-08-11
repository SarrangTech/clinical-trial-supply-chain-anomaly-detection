# data/

Synthetic data only. Nothing in this repository is real patient, site, or
shipment data -- see `pipeline/generators/` for how it's produced and
`scripts/run_generators.py` for how to regenerate it. Generated CSVs land
here transiently before `ingest_dag` lands them in the bronze Iceberg tables;
they are gitignored (see `.gitignore`).
