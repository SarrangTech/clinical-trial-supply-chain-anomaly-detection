"""Anomaly detection rules.

Each rule is a pure function over plain Python types (no Spark, no Iceberg)
so it can be unit tested directly. `pipeline/transform/gold.py` wraps each
one as a Spark UDF to apply it at scale over the silver layer.
"""
