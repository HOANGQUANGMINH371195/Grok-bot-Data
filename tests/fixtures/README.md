# Versioned R1 fixtures

Fixtures are synthetic and safe to commit. The CSVs exercise UTF-8, quoted multiline
fields, nulls, Decimal-as-string conversion, PII classification and adversarial text.
Expected JSON is canonical test output, not a runtime data source. A pinned Parquet
fixture is still required before M0-04 can be marked PASS; it must use the same
fixture-version and SHA-256 convention.
