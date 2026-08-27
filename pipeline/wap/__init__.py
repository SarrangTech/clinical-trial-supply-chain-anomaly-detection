"""Write-audit-publish helpers built on Iceberg's native branch support.

Real mechanism, not a simulated staging-table copy: a batch is written onto
an isolated branch (`write.wap.enabled=true` + `spark.wap.branch`), audited
there, and only then either fast-forwarded into `main` or rejected. See
`write_audit_publish.py` for the full flow.
"""
